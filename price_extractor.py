from bs4 import BeautifulSoup
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import re
import time
import logging
import random
from typing import Dict, Optional, Tuple, List, Set
from urllib.parse import quote_plus
import difflib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': UserAgent().random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.driver = None
        self._initialize_driver()

    def _initialize_driver(self):
        if self.driver is not None:
            logger.debug("WebDriver already initialized.")
            return

        try:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
            chrome_options.add_argument('--page-load-timeout=45')
            chrome_options.add_argument('--script-timeout=45')

            logger.info("Attempting to initialize WebDriver...")
            self.driver = uc.Chrome(
                options=chrome_options,
                version_main=137,
                suppress_welcome=True,
                use_subprocess=False
            )
            self.driver.set_page_load_timeout(45)
            self.driver.set_script_timeout(45)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            self.driver = None
            raise

    def _del_(self):
        self.cleanup()

    def cleanup(self):
        if self.driver is not None:
            logger.info("Closing WebDriver...")
            try:
                self.driver.quit()
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Error closing browser: {str(e)}")
            finally:
                self.driver = None
                logger.info("WebDriver closed.")

    def get_product_details(self, url: str) -> Tuple[str, Dict[str, str]]:
        initial_product_name_for_display = "Unknown Product (could not fetch initial title)"
        search_title_base = None

        try:
            if self.driver is None:
                self._initialize_driver()
                if self.driver is None:
                    error_msg = "WebDriver could not be initialized."
                    return error_msg, {'amazon': error_msg, 'flipkart': error_msg, 'reliancedigital': error_msg}

            logger.info(f"Fetching product details for URL: {url}")
            initial_platform, product_id = self.identify_platform_and_product_id(url)

            if not initial_platform:
                logger.error(f"Unsupported or invalid URL: {url}")
                return "Invalid URL", {'amazon': 'Invalid URL', 'flipkart': 'Invalid URL', 'reliancedigital': 'Invalid URL'}

            results = {'amazon': 'Not found', 'flipkart': 'Not found', 'reliancedigital': 'Not found'}

            # First get the product title from the source platform
            if initial_platform == 'amazon':
                amazon_title, amazon_price, amazon_error = self._get_amazon_details(url)
                if amazon_title:
                    initial_product_name_for_display = amazon_title
                    search_title_base = amazon_title
                    logger.info(f"Got title from Amazon: {search_title_base}")
                if amazon_price is not None:
                    results['amazon'] = str(amazon_price)
                elif amazon_error:
                    results['amazon'] = amazon_error

            elif initial_platform == 'flipkart':
                flipkart_title, flipkart_price, flipkart_error = self._get_flipkart_details(url)
                if flipkart_title:
                    initial_product_name_for_display = flipkart_title
                    search_title_base = flipkart_title
                    logger.info(f"Got title from Flipkart: {search_title_base}")
                if flipkart_price is not None:
                    results['flipkart'] = str(flipkart_price)
                elif flipkart_error:
                    results['flipkart'] = flipkart_error

            elif initial_platform == 'reliancedigital':
                reliance_title, reliance_price, reliance_error = self._get_reliance_digital_details(url)
                if reliance_title:
                    initial_product_name_for_display = reliance_title
                    search_title_base = reliance_title
                    logger.info(f"Got title from Reliance Digital: {search_title_base}")
                if reliance_price is not None:
                    results['reliancedigital'] = str(reliance_price)
                elif reliance_error:
                    results['reliancedigital'] = reliance_error

            if search_title_base:
                # Clean the search term
                cleaned_search_term = self._clean_title_for_search(search_title_base, url)
                logger.info(f"Original title: '{search_title_base}'")
                logger.info(f"Cleaned search term: '{cleaned_search_term}'")

                # Search other platforms
                if initial_platform != 'amazon':
                    logger.info(f"Searching Amazon with term: '{cleaned_search_term}'")
                    results['amazon'] = self._search_amazon(cleaned_search_term) or 'Not found'

                if initial_platform != 'flipkart':
                    logger.info(f"Searching Flipkart with term: '{cleaned_search_term}'")
                    results['flipkart'] = self._search_flipkart(cleaned_search_term) or 'Not found'

                if initial_platform != 'reliancedigital':
                    logger.info(f"Searching Reliance Digital with term: '{cleaned_search_term}'")
                    results['reliancedigital'] = self._search_reliance_digital(cleaned_search_term, url) or 'Not found'
            else:
                logger.warning(f"Could not obtain a base title from {url} to search other platforms.")

            logger.info(f"Final results for {url}: {results}")
            return initial_product_name_for_display, results

        except Exception as e:
            logger.error(f"Error in get_product_details: {str(e)}", exc_info=True)
            return "Error during processing", {'amazon': 'Error', 'flipkart': 'Error', 'reliancedigital': 'Error'}

    def _clean_title_for_search(self, title: str, url: str = None) -> str:
        """Clean the product title for search, aiming to keep model and key specs."""
        logger.debug(f"_clean_title_for_search: Starting cleaning for title: '{title}'")

        lower_title = title.lower()

        # Remove accessory keywords first, as these definitely indicate a mismatch
        accessory_keywords = ['guard', 'protector', 'case', 'cover', 'tempered glass', 'screen protector', 'skin', 'film', 'sticker', 'pouch', 'adapter', 'charger', 'cable', 'earphone', 'headphone', 'combo', 'pack', 'stand', 'mount']
        for keyword in accessory_keywords:
            lower_title = lower_title.replace(keyword, '')

        # Remove specific phrases that are noise but might contain numbers/colors, using word boundaries
        noise_phrases_regex = r'\b(?:locked with airtel prepaid|ethereal blue|mystical green|desert gold|cool blue|power black|satin black|mint green|graphite black|ice silver|ocean blue|lavender frost|olive twilight|diamond dust black|misty lavender)\b'
        cleaned_title = re.sub(noise_phrases_regex, '', lower_title)
        
        # Retain numbers followed by GB or TB, and words that seem like model names or key features
        # This regex tries to keep sequences of letters/numbers, and specific spec patterns
        meaningful_parts = re.findall(r'\b[a-z0-9]+\b(?:\s*(?:gb|tb|ram|inch|hz))?|\b(?:poco|redmi|iphone|galaxy|pixel)\b', cleaned_title)
        
        # Reconstruct the search query from meaningful parts
        search_query_parts = []
        brand_added = False
        
        # Prioritize brand and model at the beginning
        brands_priority = ['poco', 'redmi', 'iphone', 'galaxy', 'pixel']
        for brand in brands_priority:
            if brand in meaningful_parts:
                search_query_parts.append(brand)
                meaningful_parts.remove(brand)
                brand_added = True
                break
        
        # Add other meaningful parts, ensuring uniqueness and avoiding single characters unless they are part of a spec (like 'g' in 5g)
        added_parts = set(search_query_parts)
        for part in meaningful_parts:
            # Keep parts that are longer than 1 character, or are a single digit/letter followed by a spec unit (handled by the regex above)
            if part not in added_parts and (len(part) > 1 or re.match(r'\d+[a-z]?', part)): # Simple check, can be improved
                search_query_parts.append(part)
                added_parts.add(part)

        # Join the parts, clean up extra spaces/hyphens that might result from removals
        search_query = ' '.join(search_query_parts).replace(' - ', ' ').replace('--', ' ').strip()
        search_query = re.sub(r'\s+', ' ', search_query).strip() # Final space cleanup

        # Fallback to the original title if the cleaned query is too short or empty
        if not search_query or len(search_query) < 4:
            search_query = title.strip()

        logger.info(f"_clean_title_for_search: Original title: '{title}'. Cleaned search query: '{search_query}'")
        return search_query

    def identify_platform_and_product_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        if "amazon." in url:
            match = re.search(r'/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})', url)
            return ("amazon", match.group(1) or match.group(2)) if match else (None, None)
        elif "flipkart.com" in url:
            match = re.search(r'pid=([^&]+)', url) or re.search(r'/p/([^/?&]+)', url)
            return ("flipkart", match.group(1)) if match else (None, None)
        elif "reliancedigital.in" in url:
            match = re.search(r'/(?:product|p)/([^/?&]+)', url)
            return ("reliancedigital", match.group(1).split(",")[0]) if match else (None, None)
        return None, None

    def _get_amazon_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        logger.info(f"Fetching Amazon details for URL: {url}")
        title = None
        price = None
        error_message = None

        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(random.uniform(2, 4))

            # Fetch title
            title_selectors = ['span#productTitle', 'h1#title']
            for selector in title_selectors:
                try:
                    title_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        logger.info(f"Amazon title found: {title[:50]}...")
                    break
                except Exception as e:
                    logger.debug(f"Could not find Amazon title with selector {selector}: {e}")
                    continue
            
            if not title:
                logger.warning(f"Could not find title on Amazon page: {url}")
                title = "Unknown Product"

            # Fetch price
            price_selectors = [
                '#corePrice_feature_div span.a-price-whole',
                'div[data-cy="price-recipe"] span.a-price-whole',
                'span.priceToPay span.a-price-whole',
                '#priceblock_ourprice', '#priceblock_dealprice', '#priceblock_saleprice',
                '#apex_desktop_newAccordionRow span.a-price-whole',
                'span.a-price.aok-align-center span.a-offscreen'
            ]
            price_text_found = None
            for selector in price_selectors:
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in price_elements:
                        if el.is_displayed() or "a-offscreen" in el.get_attribute("class"):
                            raw_text = el.get_attribute('textContent') or el.text
                            price_text_found = raw_text.strip()
                            if price_text_found: break
                    if price_text_found: break
                except: continue

            if price_text_found:
                cleaned_price = re.sub(r'[^\d.]', '', price_text_found.replace(',', ''))
                if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                    price = float(cleaned_price)
                    logger.info(f"Amazon price found: {price}")

            if price is None:
                logger.warning(f"Could not find price on Amazon page: {url}")
                error_message = "Price not found"

        except Exception as e:
            logger.error(f"Error extracting Amazon details: {str(e)} for url {url}", exc_info=True)
            error_message = f"Extraction error: {str(e)[:50]}"

        return title, price, error_message

    def _get_flipkart_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        logger.info(f"Fetching Flipkart details for URL: {url}")
        title = None
        price = None
        error_message = None
        max_retries = 2

        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                time.sleep(random.uniform(4, 6))

                # Close login popup
                for _ in range(2):
                    try:
                        close_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button._2KpZ6l._2doB4z, span[role='button']")))
                        if close_button and ("skip" in close_button.text.lower() or "✕" in close_button.text or "esc" in close_button.text.lower()):
                            close_button.click()
                            logger.info("Closed Flipkart login popup.")
                            time.sleep(1)
                        break
                    except Exception as e:
                        logger.debug(f"Retrying to close Flipkart popup: {e}")
                        time.sleep(1)

                title_selectors = ['span.B_NuCI', 'h1.yhB1nd', 'h1[class*="_title"]']
                for selector in title_selectors:
                    try:
                        title_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if title_element and title_element.text.strip():
                            title = title_element.text.strip()
                            logger.info(f"Flipkart title found: {title[:50]}...")
                        break
                    except: continue

                if not title:
                    try:
                        title = self.driver.title.split("|")[0].strip()
                        logger.info(f"Flipkart title (fallback from page title): {title[:50]}...")
                    except: pass

                price_selectors = ['div._30jeq3._16Jk6d', 'div._30jeq3', 'div.Nx9bqj._3_XqSL']
                price_text_found = None
                for selector in price_selectors:
                    try:
                        price_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if price_element and price_element.text.strip():
                            price_text_found = price_element.text.strip()
                        break
                    except: continue

                if price_text_found:
                    cleaned_price = re.sub(r'[^\d.]', '', price_text_found.replace(',', '').replace('₹', ''))
                    if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                        price = float(cleaned_price)
                        logger.info(f"Flipkart price found: {price}")
                        break

                if price is None and attempt < max_retries - 1:
                    logger.warning(f"Flipkart price not found on attempt {attempt + 1}, retrying...")
                    time.sleep(random.uniform(5, 8))
                elif price is None:
                    error_message = "Price not found after retries"

            except Exception as e:
                logger.error(f"Error extracting Flipkart details (attempt {attempt+1}): {str(e)} for {url}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.warning("Retrying Flipkart extraction...")
                    time.sleep(random.uniform(5, 8))
                    continue
                error_message = f"Extraction error: {str(e)[:50]}"
                break

        return title, price, error_message

    def _get_reliance_digital_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        logger.info(f"Fetching Reliance Digital details for URL: {url}")
        title = None
        price = None
        error_message = None

        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 25).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(random.uniform(4, 7))

            # Updated title selectors
            title_selectors = [
                'h1.pdp__title', 
                'div.pdp__title h1', 
                'h1[itemprop="name"]',
                'div.product-title h1',
                'h1[class*="product-title"]',
                'div[class*="ProductTeaser__Name"]',
                'div[class*="ProductName"]',
                'div[class*="ProductTitle"]',
                'div[class*="ProductTeaser__Title"]',
                'div[class*="ProductCard__Name"]',
                'div[class*="ProductItem__Name"]',
                'div[class*="plp-product-name"]',
                'div[class*="plpProductName"]',
                'div[class*="PlpProductName"]'
            ]
            for selector in title_selectors:
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        logger.info(f"Reliance Digital title found: {title[:50]}...")
                    break
                except Exception as e:
                    logger.debug(f"Could not find title with selector {selector}: {e}")
                    continue

            if not title:
                try:
                    title = self.driver.title.split("|")[0].strip()
                    logger.info(f"Reliance Digital title (fallback from page title): {title[:50]}...")
                except:
                    logger.warning(f"Could not find title on Reliance Digital page: {url}")
                    title = "Unknown Product"

            # Updated price selectors
            price_selectors = [
                'span.pdp__offerPrice', 
                'div.pdp__price--new',
                'span[class*="ScreenReaderOnly"] + span',
                'div[class*="PricingBlock"] span[class*="Price"]',
                'ul[class*="pdp__priceSection"] span[class*="kAMBxl"]',
                'div[class*="product-price"] span[class*="price"]',
                'div[class*="price"] span',
                'span[class*="price"]',
                'div[class*="Price"]',
                'span[class*="Price"]',
                'div[class*="offerPrice"]',
                'span[class*="offerPrice"]',
                'div[class*="productPrice"]',
                'span[class*="productPrice"]',
                'div[class*="amount"]',
                'span[class*="amount"]',
                'div[class*="ProductPrice"]',
                'span[class*="ProductPrice"]',
                'div[class*="PriceBlock"]',
                'span[class*="PriceBlock"]',
                'div[class*="ProductTeaser__Price"]',
                'div[class*="plp-product-price"]',
                'div[class*="plpProductPrice"]',
                'div[class*="PlpProductPrice"]',
                'div[class*="price-block"]',
                'span[class*="price-block"]'
            ]
            price_text_found = None
            for selector in price_selectors:
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in price_elements:
                        raw_text = el.get_attribute('textContent') or el.text
                        if raw_text and ('₹' in raw_text or 'Rs.' in raw_text or 'INR' in raw_text) and re.search(r'\d', raw_text):
                            price_text_found = raw_text.strip()
                            logger.info(f"Price found: {price_text_found}")
                            break
                    if price_text_found: break
                except Exception as e:
                    logger.debug(f"Could not find price with selector {selector}: {e}")
                    continue

            if price_text_found:
                # Try different price patterns
                price_patterns = [
                    r'₹\s*([\d,]+\.?\d*)',  # Standard ₹ pattern
                    r'Rs\.?\s*([\d,]+\.?\d*)',  # Rs. pattern
                    r'INR\s*([\d,]+\.?\d*)',  # INR pattern
                    r'([\d,]+\.?\d*)'  # Just numbers
                ]
                
                for pattern in price_patterns:
                    match = re.search(pattern, price_text_found)
                    if match:
                        cleaned_price_str = match.group(1).replace(',', '')
                        if cleaned_price_str.replace('.', '', 1).isdigit():
                            price = float(cleaned_price_str)
                            logger.info(f"Reliance Digital price found: {price}")
                            break
                
                if price is None:
                    logger.warning(f"Price found but not valid number: {price_text_found}")

            if price is None:
                logger.warning(f"Could not find price on Reliance Digital page: {url}")
                error_message = "Price not found"

        except Exception as e:
            logger.error(f"Error extracting Reliance Digital details: {str(e)} for url {url}", exc_info=True)
            error_message = f"Extraction error: {str(e)[:50]}"

        return title, price, error_message

    def _product_matches(self, search_term: str, result_title: str, search_ram: str, search_storage: str, search_color: str, search_model: str, threshold=0.3) -> bool:
        if not search_term or not result_title:
            logger.debug("_product_matches: search_term or result_title is empty.")
            return False

        logger.debug(f"_product_matches: Comparing search_term='{search_term}' with result_title='{result_title}'")

        # --- Accessory Exclusion: Return False immediately if keyword found ---
        accessory_keywords = ['guard', 'protector', 'case', 'cover', 'tempered glass', 'screen protector', 'skin', 'film', 'sticker', 'pouch', 'adapter', 'charger', 'cable', 'earphone', 'headphone', 'combo', 'pack', 'stand', 'mount']
        lower_result_title = result_title.lower()
        for keyword in accessory_keywords:
            if keyword in lower_result_title:
                logger.debug(f"_product_matches: Rejecting '{(result_title[:50] + '...') if len(result_title) > 50 else result_title}' due to accessory keyword: '{keyword}'.")
                return False # Return False immediately if it's an accessory
        logger.debug(f"_product_matches: Title '{(result_title[:50] + '...') if len(result_title) > 50 else result_title}' passed accessory check.")
        # --- End Accessory Exclusion ---

        # Extract specs from the search term and result title more reliably
        # Using slightly more robust regex and checking for extracted values
        def extract_specs(text):
            lower_text = text.lower()
            ram_m = re.search(r'(\d+)\s*gb\s*ram', lower_text)
            storage_m = re.search(r'(\d+)\s*gb\s*(?!ram)', lower_text)
            # Try to capture color either inside or outside parentheses, being careful not to capture GB/TB
            color_m_paren = re.search(r'(\([^,)]+\))', lower_text)
            color_m_noparen = re.search(r'\b(red|blue|green|black|white|gold|silver|grey|gray|purple|pink|yellow|orange|brown)\b', lower_text)
            
            # Simple model extraction: take words that look like model numbers (contain letters and numbers, or are known brands/series)
            # This is a heuristic and might need refinement
            model_parts = re.findall(r'\b(?:[a-z0-9]+(?:[a-z]+\d+|[a-z]+\d+[a-z]+)[a-z0-9]*|poco|redmi|iphone|galaxy|pixel|tab)\b', lower_text)
            model_part = ' '.join(model_parts) if model_parts else None

            ram = ram_m.group(1) if ram_m else None
            storage = storage_m.group(1) if storage_m else None
            color = None
            if color_m_paren:
                potential_color = color_m_paren.group(1).strip()
                # Basic check to avoid capturing specs as color
                if 'gb' not in potential_color and 'tb' not in potential_color and 'ram' not in potential_color:
                    color = potential_color
            elif color_m_noparen:
                color = color_m_noparen.group(1).strip()

            return ram, storage, color, model_part

        search_ram_e, search_storage_e, search_color_e, search_model_e = extract_specs(search_term)
        result_ram_e, result_storage_e, result_color_e, result_model_e = extract_specs(result_title)

        logger.debug(f"_product_matches: Extracted Search specs: model='{search_model_e}', ram='{search_ram_e}', storage='{search_storage_e}', color='{search_color_e}'")
        logger.debug(f"_product_matches: Extracted Result specs: model='{result_model_e}', ram='{result_ram_e}', storage='{result_storage_e}', color='{result_color_e}'")

        spec_match_score = 0

        # Score for model match (high priority)
        if search_model_e and result_model_e:
            model_similarity = self._calculate_similarity(search_model_e, result_model_e)
            logger.debug(f"_product_matches: Model similarity: {model_similarity:.2f}")
            spec_match_score += model_similarity * 10 # Scale similarity score

        # Score for RAM match
        if search_ram_e and result_ram_e and search_ram_e == result_ram_e:
            spec_match_score += 5
            logger.debug("_product_matches: RAM matched (score +5).")

        # Score for Storage match
        if search_storage_e and result_storage_e and search_storage_e == result_storage_e:
            spec_match_score += 5
            logger.debug("_product_matches: Storage matched (score +5).")

        # Score for Color match (using similarity for flexibility)
        if search_color_e and result_color_e:
            color_similarity = self._calculate_similarity(search_color_e, result_color_e)
            logger.debug(f"_product_matches: Color similarity: {color_similarity:.2f}")
            spec_match_score += color_similarity * 3 # Scale similarity score
            
        # Define a threshold for considering it a match based on the total score
        # This threshold needs tuning based on how the scoring works with real data
        # A score > 10 suggests a likely model match plus possibly other specs.
        # Adjusting this threshold is key if matches are missed or incorrect ones are included.
        match_threshold = 9.0 # Lowering the threshold slightly to see if it helps

        # Final check: If a model was extracted from the search term, require at least a moderate model similarity
        if search_model_e and (not result_model_e or self._calculate_similarity(search_model_e, result_model_e) < 0.6): # Require at least 60% model similarity if a model was identified in the search term
            logger.debug(f"_product_matches: Rejecting due to insufficient model similarity ({self._calculate_similarity(search_model_e, result_model_e):.2f}) despite overall score.")
            return False # Fail if model doesn't match reasonably well

        logger.debug(f"_product_matches: Final calculated score for '{(result_title[:50] + '...') if len(result_title) > 50 else result_title}': {spec_match_score:.2f}. Match threshold: {match_threshold}")

        return spec_match_score >= match_threshold

    def _search_amazon(self, search_term: str) -> Optional[str]:
        if not self.driver or not search_term: return "WebDriver/SearchTerm Error"
        search_url = f"https://www.amazon.in/s?k={quote_plus(search_term)}"
        logger.info(f"_search_amazon: URL: {search_url}")
        try:
            self.driver.get(search_url)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')))
            time.sleep(random.uniform(2, 4))

            products = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, 'div.s-result-item[data-asin]')

            logger.info(f"Amazon search found {len(products)} potential items.")

            for product_element in products[:7]:
                product_title, product_price = None, None
                try:
                    title_el = product_element.find_element(By.CSS_SELECTOR, 'h2 a span, span.a-size-medium.a-color-base.a-text-normal')
                    product_title = title_el.text.strip()
                except: continue

                if self._product_matches(search_term, product_title, search_ram, search_storage, search_color, search_model, threshold=0.5):  # Increased threshold
                    logger.info(f"Amazon Match: '{product_title[:50]}...' with search term '{search_term}'")
                    try:
                        price_el = product_element.find_element(By.CSS_SELECTOR, 'span.a-price-whole')
                        price_text = price_el.text.strip()
                        cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                        if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                            product_price = float(cleaned_price)
                            logger.info(f"Amazon search found matching product price: {product_price}")
                            return str(product_price)
                    except Exception as e_price:
                        logger.debug(f"Could not get price for matched Amazon item: {e_price}")
                        continue
                else:
                    logger.debug(f"Amazon No Match: '{product_title[:50]}...' vs '{search_term}'")

        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}", exc_info=True)
            return "Search Error"
        return "Not found"

    def _extract_price(self, price_text: str) -> Optional[str]:
        """Extract and clean price from text."""
        try:
            cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', '').replace('Rs.', ''))
            if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                return cleaned_price
            return None
        except Exception as e:
            logger.debug(f"Error extracting price: {str(e)}")
            return None

    def _search_flipkart(self, search_term: str) -> str:
        """Search for product price on Flipkart."""
        try:
            # Clean and prepare search terms
            search_terms = []
            base_url = "https://www.flipkart.com/search?q="
            
            # Extract key components for non-mobile products
            brand_match = re.search(r'^(whirlpool|samsung|lg|godrej|haier|bosch|panasonic|hitachi|voltas|blue star)\b', search_term, re.IGNORECASE)
            capacity_match = re.search(r'(\d+)\s*[lL](?:itre)?', search_term, re.IGNORECASE)
            model_match = re.search(r'(?:205\s*WDE\s*CLS|WDE\s*CLS\s*2S|CLS\s*2S)', search_term, re.IGNORECASE) or re.search(r'(?:\d+\s*[lL])(.*?)(?:\(|\d+gb|\d+\s*star|$)', search_term, re.IGNORECASE)
            star_match = re.search(r'(\d+)\s*star', search_term, re.IGNORECASE)
            type_match = re.search(r'(single\s*door|double\s*door|frost\s*free|direct\s*cool)', search_term, re.IGNORECASE)
            color_match = re.search(r'\(([^,]+),\s*\d+\s*[lL]\)', search_term) or re.search(r'\b(blue|black|silver|grey|red|white)\b', search_term, re.IGNORECASE)

            brand = brand_match.group(1).lower() if brand_match else None
            capacity = capacity_match.group(1) if capacity_match else None
            model = model_match.group(0).strip() if model_match else None
            star_rating = star_match.group(1) if star_match else None
            fridge_type = type_match.group(1).replace(' ', '+') if type_match else None
            color = color_match.group(1).strip().replace(' ', '+') if color_match else None

            logger.info(f"Extracted components - Brand: {brand}, Capacity: {capacity}, Model: {model}, Star: {star_rating}, Type: {fridge_type}, Color: {color}")

            # For Whirlpool refrigerators, try these specific search combinations
            if brand and brand.lower() == 'whirlpool':
                # Try exact model number first
                if model:
                    search_terms.extend([
                        f"whirlpool+{model.replace(' ', '+')}",
                        f"whirlpool+{model.replace(' ', '+')}+refrigerator",
                        f"whirlpool+{model.replace(' ', '+')}+{capacity}l",
                        f"whirlpool+{model.replace(' ', '+')}+{star_rating}+star",
                        f"whirlpool+{model.replace(' ', '+')}+{fridge_type}"
                    ])
                
                # Try combinations with capacity
                if capacity:
                    search_terms.extend([
                        f"whirlpool+{capacity}l+refrigerator",
                        f"whirlpool+{capacity}l+{star_rating}+star+refrigerator",
                        f"whirlpool+{capacity}l+{fridge_type}+refrigerator"
                    ])
                
                # Try specific combinations
                if model and capacity:
                    search_terms.extend([
                        f"whirlpool+{model.replace(' ', '+')}+{capacity}l+{star_rating}+star",
                        f"whirlpool+{model.replace(' ', '+')}+{capacity}l+{fridge_type}",
                        f"whirlpool+{model.replace(' ', '+')}+{capacity}l+{color}"
                    ])

            # Add fallback search terms
            search_terms.extend([
                search_term.replace(' ', '+'),
                f"{brand}+{capacity}l+refrigerator" if brand and capacity else None,
                f"{brand}+{model.replace(' ', '+')}" if brand and model else None
            ])
            search_terms = [term for term in search_terms if term]  # Remove None values

            logger.info(f"Generated search terms: {search_terms}")

            for search_term in set(search_terms):  # Avoid duplicate searches
                search_url = f"{base_url}{quote_plus(search_term)}"
                logger.info(f"Trying Flipkart search URL: {search_url}")
                
                try:
                    self.driver.get(search_url)
                    time.sleep(3)  # Initial wait for page load
                    
                    # Wait for page load and product elements
                    try:
                        WebDriverWait(self.driver, 30).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'div._1AtVbE, div._2kHMtA, a._1fQZEK, div[data-id]')))
                    except Exception as e:
                        logger.warning(f"Timeout waiting for product elements: {str(e)}")
                        continue

                    time.sleep(2)

                    # Handle pop-ups
                    try:
                        close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                            "button._2KpZ6l._2doB4z, span[role='button'], button[class*='close'], div[class*='close'], button[class*='Close']")
                        for button in close_buttons:
                            try:
                                if button.is_displayed():
                                    button.click()
                                    logger.info("Closed Flipkart popup.")
                                    time.sleep(1)
                            except:
                                pass
                    except:
                        logger.debug("No pop-ups found or error closing pop-ups.")

                    # Scroll to load more products
                    for i in range(5):  # Increase scroll attempts
                        logger.debug(f"Scroll attempt {i+1}/5")
                        try:
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(2)
                            self.driver.execute_script("document.querySelectorAll('div._1AtVbE').forEach(el => el.scrollIntoView());")
                            time.sleep(2)
                        except Exception as e:
                            logger.warning(f"Error during scroll attempt {i+1}: {str(e)}")

                    # Find product elements
                    product_elements = []
                    selectors = [
                        'div._1AtVbE', 'div._2kHMtA', 'a._1fQZEK', 'div[data-id]',
                        'div[class*="product"]', 'div[class*="item"]', 'div[class*="Product"]'
                    ]
                    for selector in selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                product_elements = elements
                                logger.info(f"Found {len(elements)} product elements with selector: {selector}")
                                break
                        except Exception as e:
                            logger.debug(f"Error with selector {selector}: {str(e)}")
                            continue

                    if not product_elements:
                        logger.info("No product elements found for this search term.")
                        continue

                    logger.info(f"Processing {len(product_elements)} potential items.")

                    # Process each product
                    for idx, element in enumerate(product_elements[:10]):  # Limit to top 10 results
                        try:
                            # Extract title
                            title_selectors = [
                                'div._4rR01T', 'a.s1Q9rs', 'div.KzDlHZ',
                                'div[class*="title"], div[class*="name"], a[class*="title"], a[class*="name"]'
                            ]
                            title = None
                            for selector in title_selectors:
                                try:
                                    title_element = element.find_element(By.CSS_SELECTOR, selector)
                                    title = title_element.text.strip()
                                    if title:
                                        break
                                except:
                                    continue

                            if not title:
                                logger.debug(f"[{idx}] No title found for product element.")
                                continue

                            logger.debug(f"[{idx}] Checking product title: {title}")

                            # Match product
                            title_lower = title.lower()
                            match_score = 0
                            
                            # Check for exact model match first
                            if model and model.lower() in title_lower:
                                match_score += 5
                                logger.debug(f"[{idx}] Exact model match: +5")
                            
                            if brand and brand.lower() in title_lower:
                                match_score += 2
                                logger.debug(f"[{idx}] Brand match: +2")
                            if capacity and f"{capacity}l" in title_lower:
                                match_score += 2
                                logger.debug(f"[{idx}] Capacity match: +2")
                            if star_rating and f"{star_rating} star" in title_lower:
                                match_score += 1
                                logger.debug(f"[{idx}] Star rating match: +1")
                            if fridge_type and fridge_type.replace('+', ' ').lower() in title_lower:
                                match_score += 1
                                logger.debug(f"[{idx}] Type match: +1")
                            if color and color.replace('+', ' ').lower() in title_lower:
                                match_score += 0.5
                                logger.debug(f"[{idx}] Color match: +0.5")

                            # Use difflib for additional similarity check
                            similarity = difflib.SequenceMatcher(None, search_term.lower(), title_lower).ratio()
                            match_score += similarity * 2
                            logger.debug(f"[{idx}] Similarity score: {similarity:.2f} (+{similarity*2:.2f})")

                            logger.debug(f"[{idx}] Final match score: {match_score:.2f}")

                            # Lower threshold if we have an exact model match
                            threshold = 3.5 if model and model.lower() in title_lower else 4.5
                            if match_score >= threshold or similarity >= 0.65:
                                # Extract price
                                price_selectors = [
                                    'div._30jeq3', 'div._1_WHN1', 'div[class*="price"]', 'span[class*="price"]',
                                    'div[class*="Price"]', 'span[class*="Price"]'
                                ]
                                price_text = None
                                for selector in price_selectors:
                                    try:
                                        price_element = element.find_element(By.CSS_SELECTOR, selector)
                                        price_text = price_element.text.strip()
                                        if price_text:
                                            logger.debug(f"[{idx}] Found price text: {price_text}")
                                            break
                                    except:
                                        continue

                                if price_text:
                                    price = self._extract_price(price_text)
                                    if price:
                                        logger.info(f"[{idx}] Found matching Flipkart product: {title[:50]}... Price: {price}")
                                        return price
                                    else:
                                        logger.debug(f"[{idx}] Could not extract valid price from: {price_text}")
                                else:
                                    logger.debug(f"[{idx}] No price text found for matching product")

                        except Exception as e:
                            logger.debug(f"[{idx}] Error processing product element: {str(e)}")
                            continue

                except Exception as e:
                    logger.error(f"Error processing search URL {search_url}: {str(e)}")
                    continue

            logger.info(f"Flipkart search finished for '{search_term}', price not found.")
            return "Not found"

        except Exception as e:
            logger.error(f"Error searching Flipkart: {str(e)}", exc_info=True)
            return "Search Error"

    def _search_reliance_digital(self, search_term: str, url: str) -> Optional[str]:
        processed_search_term = self._clean_title_for_search(search_term, url)
        logger.info(f"_search_reliance_digital: Received search term: '{search_term}'")
        logger.info(f"_search_reliance_digital: Using cleaned search term: '{processed_search_term}'")

        if not self.driver or not processed_search_term:
            return "WebDriver/SearchTerm Error"

        # Extract specific product details from search term
        search_terms = [processed_search_term]
        
        # Add variations of the search term
        if "poco" in processed_search_term.lower():
            search_terms.extend([
                processed_search_term.replace("POCO", "Poco"),
                processed_search_term.replace("POCO", "poco"),
                "POCO " + processed_search_term.split("POCO")[-1].strip(),
                "Poco " + processed_search_term.split("POCO")[-1].strip()
            ])
        
        # Format search URLs for Reliance Digital
        search_urls = []
        base_url = "https://www.reliancedigital.in/search?q="
        
        for term in search_terms:
            search_urls.append(f"{base_url}{quote_plus(term)}")
        
        max_retries = 3
        for attempt in range(max_retries):
            for search_url in search_urls:
                try:
                    logger.info(f"_search_reliance_digital: Trying URL: {search_url}")
                    self.driver.get(search_url)
                    
                    # Wait for initial page load
                    WebDriverWait(self.driver, 20).until(
                        lambda driver: driver.execute_script('return document.readyState') == 'complete'
                    )
                    
                    # Wait for products to load with multiple selectors
                    product_selectors = [
                        'div[class*="productCard"]',
                        'div[class*="product-item"]',
                        'div[class*="product-tile"]',
                        'div[class*="product-list"]',
                        'div[class*="search-grid"]',
                        'div[class*="product-grid"]',
                        'div[class*="product"]',
                        'div[class*="item"]',
                        'div[class*="ProductTeaser"]',
                        'div[class*="ProductCard"]',
                        'div[class*="plp-product"]',
                        'div[class*="plpProduct"]',
                        'div[class*="PlpProduct"]'
                    ]
                    
                    # Try each selector until we find products
                    product_elements = []
                    for selector in product_selectors:
                        try:
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                product_elements = elements
                                logger.info(f"Found {len(elements)} product elements with selector: {selector}")
                                break
                        except Exception as e:
                            continue
                    
                    if not product_elements:
                        logger.warning(f"No product containers found for URL: {search_url}")
                        continue

                    # Scroll to trigger lazy loading
                    for _ in range(3):
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                        time.sleep(1)
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1)

                    # Process each product
                    for product_element in product_elements[:10]:
                        try:
                            # Get product title
                            title_selectors = [
                                'div[class*="productName"]',
                                'div[class*="product-title"]',
                                'h2[class*="productName"]',
                                'p[class*="productName"]',
                                'div[class*="ProductTeaser__Name"]',
                                'a[title]',
                                'div[class*="name"]',
                                'h2', 'h3', 'p',
                                'div[class*="ProductName"]',
                                'div[class*="ProductTitle"]',
                                'div[class*="ProductTeaser__Title"]',
                                'div[class*="ProductCard__Name"]',
                                'div[class*="ProductItem__Name"]',
                                'div[class*="plp-product-name"]',
                                'div[class*="plpProductName"]',
                                'div[class*="PlpProductName"]'
                            ]
                            
                            product_title = None
                            for title_sel in title_selectors:
                                try:
                                    title_el = product_element.find_element(By.CSS_SELECTOR, title_sel)
                                    if title_el and title_el.text.strip():
                                        product_title = title_el.text.strip()
                                        break
                                except:
                                    continue

                            if not product_title:
                                continue

                            # Check if product matches search term
                            if self._calculate_similarity(processed_search_term.lower(), product_title.lower()) > 0.6:
                                logger.info(f"Found matching product: {product_title}")
                                
                                # Get product price
                                price_selectors = [
                                    'div[class*="price"] span',
                                    'span[class*="price"]',
                                    'div[class*="Price"]',
                                    'span[class*="Price"]',
                                    'div[class*="offerPrice"]',
                                    'span[class*="offerPrice"]',
                                    'div[class*="productPrice"]',
                                    'span[class*="productPrice"]',
                                    'div[class*="amount"]',
                                    'span[class*="amount"]',
                                    'div[class*="ProductPrice"]',
                                    'span[class*="ProductPrice"]',
                                    'div[class*="PriceBlock"]',
                                    'span[class*="PriceBlock"]',
                                    'div[class*="ProductTeaser__Price"]',
                                    'div[class*="plp-product-price"]',
                                    'div[class*="plpProductPrice"]',
                                    'div[class*="PlpProductPrice"]',
                                    'div[class*="price-block"]',
                                    'span[class*="price-block"]'
                                ]
                                
                                for price_sel in price_selectors:
                                    try:
                                        price_el = product_element.find_element(By.CSS_SELECTOR, price_sel)
                                        if price_el and price_el.text.strip():
                                            price_text = price_el.text.strip()
                                            
                                            # Extract price using multiple patterns
                                            price_patterns = [
                                                r'₹\s*([\d,]+\.?\d*)',  # Standard ₹ pattern
                                                r'Rs\.?\s*([\d,]+\.?\d*)',  # Rs. pattern
                                                r'INR\s*([\d,]+\.?\d*)',  # INR pattern
                                                r'([\d,]+\.?\d*)'  # Just numbers
                                            ]
                                            
                                            for pattern in price_patterns:
                                                match = re.search(pattern, price_text)
                                                if match:
                                                    cleaned_price_str = match.group(1).replace(',', '')
                                                    if cleaned_price_str.replace('.', '', 1).isdigit():
                                                        product_price = float(cleaned_price_str)
                                                        logger.info(f"Found matching product price: {product_price}")
                                                        return str(product_price)
                                    except Exception as e:
                                        continue
                                        
                        except Exception as e:
                            logger.debug(f"Error processing product element: {str(e)}")
                            continue

                except Exception as e:
                    logger.error(f"Error searching Reliance Digital (attempt {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(3, 5))
                        continue
                    break

        logger.info(f"Reliance Digital search finished for '{processed_search_term}', price not found.")
        return "Not found"

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein distance.
        Returns a float between 0 and 1, where 1 means identical strings.
        """
        if not str1 or not str2:
            return 0.0
            
        # Convert to lowercase for case-insensitive comparison
        str1 = str1.lower()
        str2 = str2.lower()
        
        # Calculate Levenshtein distance
        if len(str1) < len(str2):
            str1, str2 = str2, str1
            
        if len(str2) == 0:
            return 0.0
            
        previous_row = range(len(str2) + 1)
        for i, c1 in enumerate(str1):
            current_row = [i + 1]
            for j, c2 in enumerate(str2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
            
        # Calculate similarity ratio
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 1.0
        return 1.0 - (previous_row[-1] / max_len)

if __name__ == "__main__":
    url = input("Enter the product URL (Amazon, Flipkart, or Reliance Digital): ").strip()

    if not url:
        print("No URL provided. Exiting.")
        exit(1)

    print(f"\n{'='*50}")
    print(f"Analyzing URL: {url}")

    price_extractor = None
    try:
        price_extractor = PriceExtractor()
        product_name, results = price_extractor.get_product_details(url)

        print(f"\nProduct Identified: {product_name}")
        print(f"{'-'*30}")

        for platform, price_str in results.items():
            platform_name = platform.upper()
            if platform == 'reliancedigital':
                platform_name = 'RELIANCE DIGITAL'

            price_display = price_str
            try:
                price_val = float(price_str)
                price_display = f"₹{price_val:,.2f}"
            except (ValueError, TypeError):
                pass

            print(f"{platform_name:<20}: {price_display}")

    except KeyboardInterrupt:
        print("\nScript interrupted by user. Cleaning up...")
    except Exception as e:
        logger.error(f"An critical error occurred during main execution: {str(e)}", exc_info=True)
        print(f"An critical error occurred: {str(e)}")
    finally:
        if price_extractor:
            try:
                price_extractor.cleanup()
            except Exception as e:
                logger.error(f"Error during final cleanup: {str(e)}")
                print(f"Error during final cleanup: {str(e)}")
    print(f"{'='*50}\n")