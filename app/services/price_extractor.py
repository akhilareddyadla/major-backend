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
import asyncio
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
import selenium.webdriver as webdriver
from selenium.common.exceptions import TimeoutException

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PriceExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': UserAgent().random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.driver = None
        self.logger = logging.getLogger(__name__)

    def _initialize_driver(self):
        if self.driver is not None:
            logger.debug("WebDriver already initialized.")
            return

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                chrome_options = uc.ChromeOptions()
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--enable-system-font-check')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                chrome_options.add_argument('--page-load-timeout=60')
                chrome_options.add_argument('--script-timeout=60')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-browser-side-navigation')
                chrome_options.add_argument('--disable-site-isolation-trials')
                chrome_options.add_argument('--disable-logging')
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument('--silent')
                chrome_options.add_argument('--disable-background-networking')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                chrome_options.add_argument('--disable-breakpad')
                chrome_options.add_argument('--disable-component-extensions-with-background-pages')
                chrome_options.add_argument('--disable-features=TranslateUI')
                chrome_options.add_argument('--disable-ipc-flooding-protection')
                chrome_options.add_argument('--disable-renderer-backgrounding')
                chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
                chrome_options.add_argument('--force-color-profile=srgb')
                chrome_options.add_argument('--metrics-recording-only')
                chrome_options.add_argument('--mute-audio')
                chrome_options.add_argument('--incognito')
                chrome_options.add_argument('--no-proxy-server')
                chrome_options.add_argument('--disable-features=EnableEphemeralFlashPermission')
                chrome_options.add_argument('--disable-infobars')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--ignore-certificate-errors')
                chrome_options.add_argument('--allow-running-insecure-content')

                logger.info(f"Attempting to initialize WebDriver with enhanced stealth (attempt {attempt + 1}/{max_retries})...")
                self.driver = uc.Chrome(
                    options=chrome_options,
                    version_main=137,
                    suppress_welcome=True,
                    use_subprocess=True,
                )

                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                          get: () => undefined
                        })
                    """
                })

                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        window.chrome = {
                          runtime: {},
                        };
                    """
                })

                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'languages', {
                          get: () => ['en-US', 'en']
                        });
                        Object.defineProperty(navigator, 'plugins', {
                          get: () => []
                        });
                        Object.defineProperty(navigator, 'mimeTypes', {
                          get: () => []
                        });
                        Object.defineProperty(navigator, 'deviceMemory', {
                          get: () => 8
                        });
                        Object.defineProperty(navigator, 'hardwareConcurrency', {
                          get: () => 8
                        });
                        Object.defineProperty(screen, 'width', { get: () => 1920 });
                        Object.defineProperty(screen, 'height', { get: () => 1080 });
                        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
                        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
                        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
                        Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
                    """
                })

                logger.info("WebDriver initialized successfully with enhanced anti-bot measures")
                return

            except Exception as e:
                logger.error(f"Failed to initialize WebDriver (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if self.driver is not None:
                    try:
                        self.driver.quit()
                    except:
                        pass
                self.driver = None

                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("Max retries reached. Could not initialize WebDriver.")
                    raise

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"Error while closing WebDriver: {str(e)}")
                finally:
                    self.driver = None
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            logger.info("Cleanup completed")

    async def get_product_details(self, url: str) -> Tuple[str, Dict[str, str]]:
        initial_product_name_for_display = "Unknown Product (could not fetch initial title)"
        search_title_base = None

        try:
            logger.info(f"Fetching product details for URL: {url}")
            initial_platform, product_id = self.identify_platform_and_product_id(url)

            if not initial_platform:
                logger.error(f"Unsupported or invalid URL: {url}")
                return "Invalid URL", {'amazon': 'Invalid URL', 'flipkart': 'Invalid URL', 'reliancedigital': 'Invalid URL'}

            results = {'amazon': 'Not found', 'flipkart': 'Not found', 'reliancedigital': 'Not found'}

            try:
                self._initialize_driver()
            except Exception as e:
                error_msg = f"Failed to initialize Selenium WebDriver: {str(e)}"
                logger.error(error_msg)
                return error_msg, {'amazon': error_msg, 'flipkart': error_msg, 'reliancedigital': error_msg}

            if initial_platform == 'amazon':
                amazon_title, amazon_price, amazon_error = self._get_amazon_details(url)
                initial_product_name_for_display = amazon_title if amazon_title else initial_product_name_for_display
                if amazon_price is not None:
                    results['amazon'] = str(amazon_price)
                elif amazon_error:
                    results['amazon'] = amazon_error
                search_title_base = amazon_title if amazon_title and amazon_title != "Unknown Product" else None

            elif initial_platform == 'flipkart':
                logger.info(f"Fetching Flipkart details for URL: {url}")
                flipkart_title, flipkart_price, flipkart_error = self._get_flipkart_details(url)
                initial_product_name_for_display = flipkart_title if flipkart_title else initial_product_name_for_display
                if flipkart_price is not None:
                    results['flipkart'] = str(flipkart_price)
                elif flipkart_error:
                    results['flipkart'] = flipkart_error
                search_title_base = flipkart_title if flipkart_title and flipkart_title != "Unknown Product" else None

            elif initial_platform == 'reliancedigital':
                reliance_title, reliance_price, reliance_error = self._get_reliance_digital_details(url)
                initial_product_name_for_display = reliance_title if reliance_title else initial_product_name_for_display
                if reliance_price is not None:
                    results['reliancedigital'] = str(reliance_price)
                elif reliance_error:
                    results['reliancedigital'] = reliance_error
                search_title_base = reliance_title if reliance_title and reliance_title != "Unknown Product" else None

            if search_title_base:
                cleaned_search_term = self._clean_title_for_search(search_title_base, url)
                logger.info(f"Original title: '{search_title_base}'")
                logger.info(f"Cleaned search term: '{cleaned_search_term}'")

                if initial_platform != 'flipkart':
                    logger.info(f"Searching Flipkart with term: '{cleaned_search_term}'")
                    try:
                        flipkart_search_title, flipkart_search_price, flipkart_search_error = self._search_flipkart(cleaned_search_term)
                    except InvalidSessionIdException:
                        logger.warning("Flipkart search failed due to invalid session id. Re-initializing driver...")
                        self.cleanup() # Ensure driver is fully closed
                        self._initialize_driver() # Re-initialize
                        flipkart_search_title, flipkart_search_price, flipkart_search_error = self._search_flipkart(cleaned_search_term)
                    if flipkart_search_price is not None:
                        results['flipkart'] = str(flipkart_search_price)
                    elif flipkart_search_error:
                        results['flipkart'] = flipkart_search_error

                if initial_platform != 'amazon':
                    logger.info(f"Searching Amazon with term: '{cleaned_search_term}'")
                    try:
                        amazon_search_result = self._search_amazon(cleaned_search_term)
                    except InvalidSessionIdException:
                        logger.warning("Amazon search failed due to invalid session id. Re-initializing driver...")
                        self.cleanup() # Ensure driver is fully closed
                        self._initialize_driver() # Re-initialize
                        amazon_search_result = self._search_amazon(cleaned_search_term)
                    if amazon_search_result and results['amazon'] == 'Not found':
                        results['amazon'] = amazon_search_result

                if initial_platform != 'reliancedigital':
                    logger.info(f"Searching Reliance Digital with term: '{cleaned_search_term}'")
                    try:
                        reliance_search_result = await self._search_reliance_digital(cleaned_search_term)
                    except InvalidSessionIdException:
                        logger.warning("Reliance Digital search failed due to invalid session id. Re-initializing driver...")
                        self.cleanup() # Ensure driver is fully closed
                        self._initialize_driver() # Re-initialize
                        reliance_search_result = await self._search_reliance_digital(cleaned_search_term)
                    if reliance_search_result and results['reliancedigital'] == 'Not found':
                        results['reliancedigital'] = reliance_search_result

            logger.info(f"Final results for {url}: {results}")
            return initial_product_name_for_display, results

        except Exception as e:
            logger.error(f"Critical error in get_product_details: {str(e)}", exc_info=True)
            self.cleanup()
            return "Error during processing", {'amazon': 'Error', 'flipkart': 'Error', 'reliancedigital': 'Error'}

    def _clean_title_for_search(self, title: str, url: str = None) -> str:
        logger.debug(f"_clean_title_for_search: Starting cleaning for title: '{title}'")
        lower_title = title.lower()

        brands = [
            'apple iphone', 'apple watch', 'apple mac', 'apple ipad', 'apple airpods', 'apple',
            'samsung galaxy s', 'samsung galaxy a', 'samsung galaxy m', 'samsung galaxy f', 'samsung',
            'motorola moto g', 'motorola moto e', 'motorola edge', 'motorola',
            'xiaomi redmi', 'xiaomi mi', 'xiaomi poco', 'xiaomi',
            'oneplus', 'realme', 'oppo', 'vivo', 'nokia', 'google pixel', 'iqoo', 'infinix', 'tecno',
            'sony', 'lg', 'whirlpool', 'haier', 'godrej', 'bosch', 'panasonic', 'hitachi', 'voltas', 'blue star', 'ifb',
            'dell', 'hp', 'lenovo', 'acer', 'asus',
            'canon', 'nikon', 'fujifilm',
            'boat', 'jbl', 'bose', 'sennheiser',
            'fitbit', 'garmin'
        ]

        extracted_brand = None
        sorted_brands = sorted(brands, key=len, reverse=True)

        for b_norm in sorted_brands:
            if re.search(r'\b' + re.escape(b_norm).replace(' ', '[-\s]?') + r'\b', lower_title):
                extracted_brand = b_norm
                logger.debug(f"_clean_title_for_search: Extracted brand: {extracted_brand}")
                break

        search_parts = []
        if extracted_brand:
            search_parts.append(extracted_brand)

        model_identifier = None
        if extracted_brand:
            identifier_match = re.search(re.escape(extracted_brand).replace(' ', '[-\s]?') + r'[-\s]?((?:[a-zA-Z0-9]+[-\/\s]?){1,5})', lower_title)
            if identifier_match:
                model_identifier = identifier_match.group(1).strip(' -/')
                logger.debug(f"_clean_title_for_search: Extracted model identifier after brand: {model_identifier}")
                model_parts = re.split(r'[-\/\s]', model_identifier)
                generic_filter = ['mobile', 'phone', 'watch', 'laptop', 'tv', 'refrigerator', 'washing', 'machine']
                filtered_model_parts = [p for p in model_parts if p not in generic_filter]
                search_parts.extend(filtered_model_parts)

        if not model_identifier:
            prominent_alphanum_phrases = re.findall(r'\b([a-zA-Z]*[0-9]+[a-zA-Z0-9-]*(\s+[a-zA-Z0-9-]{1,10}){0,3})\b|\b([a-zA-Z]{1,5}[-\/][0-9]{2,}[a-zA-Z0-9-]*)\b|\b([0-9]+[a-zA-Z]+)\b', lower_title)
            candidates = []
            for phrase_tuple in prominent_alphanum_phrases:
                for phrase_part in phrase_tuple:
                    if phrase_part:
                        phrase_part_cleaned = phrase_part.strip()
                        if not re.fullmatch(r'\d+\s*(gb|mah|hz|inch|mp|w|ltr|kg|star|tb|°)\b', phrase_part_cleaned.replace(" ", ""), re.IGNORECASE) and len(phrase_part_cleaned) > 2:
                            candidates.append(phrase_part_cleaned)

            candidates = sorted(list(set(candidates)), key=len, reverse=True)
            if candidates:
                fallback_model_parts = re.split(r'[-\/\s]', candidates[0])[:4]
                existing_parts_lower = {p.lower() for p in search_parts}
                for part in fallback_model_parts:
                    if part.lower() not in existing_parts_lower:
                        search_parts.append(part)
                        existing_parts_lower.add(part.lower())

        specs_to_add = []
        capacity_match = re.findall(r'\b(\d+)\s*(gb|tb|mah|l|litre|ml|kg|g|w|wh|mp|hz)\b', lower_title)
        for val, unit in capacity_match:
            specs_to_add.append(f"{val}{unit}")

        star_match = re.search(r'(\d+)\s*star\b', lower_title)
        if star_match:
            specs_to_add.append(f"{star_match.group(1)} star")

        key_features = ['5g', 'pro', 'ultra', 'max', 'plus']
        for feature in key_features:
            if feature in lower_title and feature not in {p.lower() for p in search_parts} and feature not in {s.lower() for s in specs_to_add}:
                if re.search(r'\b' + feature + r'\b', lower_title):
                    specs_to_add.append(feature)

        color_keywords = ['black', 'white', 'blue', 'red', 'green', 'silver', 'gold', 'gray', 'grey', 'purple', 'pink', 'orange', 'yellow', 'brown', 'bronze', 'aqua', 'marine', 'sky', 'midnight', 'space', 'rose', 'graphite', 'sierra', 'alpine', 'wine', 'solid']
        color_match = re.search(r'\b((?:[a-zA-Z]+\s){0,2}(?:' + '|'.join(color_keywords) + r'))\b(?![^()]*\))', lower_title)
        if color_match:
            color_candidate = color_match.group(1).strip()
            if len(color_candidate.split()) <= 3 and len(color_candidate) > 2:
                specs_to_add.append(color_candidate)

        existing_parts_lower = {p.lower() for p in search_parts}
        for spec_item in specs_to_add:
            spec_item_lower = spec_item.lower()
            if spec_item_lower not in existing_parts_lower:
                is_sub_part = False
                for existing in existing_parts_lower:
                    if spec_item_lower in existing and len(spec_item_lower) < len(existing):
                        is_sub_part = True
                        break
                if not is_sub_part:
                    search_parts.append(spec_item)
                    existing_parts_lower.add(spec_item_lower)

        final_search_parts = []
        final_common_noise = {'and', 'with', 'for', 'the', 'new', 'os', 'windows', 'android', 'in', 'on', 'of', 'at', 'by', 'to', 'from', 'a', 'an', 'is', 'it', 'this', 'that', 'segment', 'buy', 'now', 'get', 'best', 'price', 'offers', 'deals', 'sale', 'discount', 'mobile', 'phone', 'watch', 'laptop', 'tv', 'refrigerator', 'washing', 'machine'}
        seen = set()
        for part in search_parts:
            part_lower = part.lower()
            if part_lower not in seen and part_lower not in final_common_noise:
                is_substring_of_added = False
                for added_part in final_search_parts:
                    if part_lower in added_part.lower() and len(part_lower) < len(added_part.lower()):
                        is_substring_of_added = True
                        break
                if not is_substring_of_added:
                    final_search_parts.append(part)
                    seen.add(part_lower)

        prioritized_query_parts = []
        if extracted_brand:
            prioritized_query_parts.append(extracted_brand)
        if model_identifier:
            model_parts = re.split(r'[-\/\s]', model_identifier)
            prioritized_query_parts.extend(model_parts)

        prioritized_lower = {p.lower() for p in prioritized_query_parts}
        for part in final_search_parts:
            if part.lower() not in prioritized_lower:
                prioritized_query_parts.append(part)

        search_query = ' '.join(dict.fromkeys(prioritized_query_parts).keys()).strip()

        if not search_query or len(search_query.split()) < 2 and extracted_brand not in search_query.lower():
            words = re.findall(r'\b\w+\b', lower_title)
            essential_words = [word for word in words if word not in final_common_noise and len(word) > 1 and not word.isdigit()]
            fallback_query = ' '.join(essential_words[:6])
            if fallback_query:
                search_query = fallback_query
            elif extracted_brand:
                search_query = extracted_brand
            else:
                search_query = title

        logger.info(f"_clean_title_for_search: Original: '{title[:60]}...'. Cleaned Search Query: '{search_query}'")
        return search_query

    def identify_platform_and_product_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        if "amazon." in url:
            match = re.search(r'/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})', url)
            return ("amazon", match.group(1) or match.group(2)) if match else (None, None)
        elif "flipkart.com" in url:
            match = re.search(r'/p/([^/?&]+)', url) or re.search(r'pid=([^&]+)', url)
            return ("flipkart", match.group(1)) if match else (None, None)
        elif "reliancedigital.in" in url:
            match = re.search(r'/(?:product|p)/([^/?&]+)', url) or re.search(r'sku=([^&]+)', url)
            return ("reliancedigital", match.group(1).split(",")[0]) if match else (None, None)
        return None, None

    def _get_amazon_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """Get product details from Amazon using Selenium."""
        try:
            if not self.driver:
                self._initialize_driver()

            logger.info(f"Fetching Amazon details for URL: {url}")
            time.sleep(random.uniform(2, 4))
            self.driver.get(url)

            WebDriverWait(self.driver, 45).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(random.uniform(5, 8))

            logger.debug("Scrolling page to trigger lazy loading...")
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_steps = 5
            for i in range(scroll_steps):
                self.driver.execute_script(f"window.scrollTo(0, (document.body.scrollHeight / {scroll_steps}) * {(i+1)});")
                time.sleep(random.uniform(1, 2))
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(1, 2))

            page_source = self.driver.page_source
            if "captcha" in page_source.lower() or "unusual traffic" in page_source.lower() or "verify you are human" in page_source.lower() or "access to this page has been denied" in page_source.lower():
                error_msg = "Blocked by Amazon anti-bot detection."
                logger.warning(f"{error_msg} for URL: {url}")
                return None, None, error_msg

            title = None
            title_selectors = [
                "#productTitle",
                "#title",
                "h1.a-size-large",
                "h1.a-size-medium",
                "span#productTitle",
                "h1[data-cy='product-title']",
                "h1[data-cy='title']",
                "h1[class*='product-title']",
                "h1[class*='title']",
                "#titleSection #productTitle",
                "#title_feature_div #productTitle",
                "span.a-text-bold[id='productTitle']",
                "div#title span#productTitle",
                "h1 span#productTitle",
                "span#aiv-content-title"
            ]

            logger.info("Attempting to extract title...")
            for selector in title_selectors:
                try:
                    title_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        logger.info(f"Found title with selector {selector}: {title[:70]}...")
                        break
                except Exception as e:
                    logger.debug(f"Could not find title with selector {selector}: {str(e)}")
                    continue

            if not title:
                logger.info("Attempting title extraction using JavaScript fallback...")
                try:
                    title = self.driver.execute_script("""
                        return document.querySelector('#productTitle')?.textContent?.trim() ||
                               document.querySelector('h1#title')?.textContent?.trim() ||
                               document.querySelector('span#productTitle')?.textContent?.trim() ||
                               document.querySelector('h1.a-size-large')?.textContent?.trim() ||
                               document.title.split('|')[0]?.trim();
                    """)
                    if title and title.lower() != 'amazon.in':
                        logger.info(f"Found title using JavaScript: {title[:70]}...")
                    else:
                        title = None
                except Exception as e:
                    logger.debug(f"JavaScript title extraction failed: {str(e)}")

                if not title:
                    title = "Unknown Product"
                    logger.warning(f"Could not find product title on Amazon page {url} using any method.")

            price = None
            price_selectors = [
                "span.a-price span.a-offscreen",
                "span.a-price-whole",
                "span.a-color-price",
                "span.a-price[data-a-color='price'] span.a-offscreen",
                "span.a-price[data-a-color='secondary'] span.a-offscreen",
                "span.a-price[data-a-color='base'] span.a-offscreen",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                "#priceblock_saleprice",
                ".a-price .a-offscreen",
                ".a-price-whole",
                ".a-color-price",
                "div[data-cy='price-recipe'] span.a-price-whole",
                "span.priceToPay span.a-price-whole",
                "#apex_desktop_newAccordionRow span.a-price-whole",
                "span.a-price.aok-align-center span.a-offscreen",
                "div[data-cy='price-block'] span.a-offscreen",
                "div[data-cy='price'] span.a-offscreen",
                "div[data-cy='price-block'] span.a-price-whole",
                "div[data-cy='price'] span.a-price-whole",
                "#corePriceDisplay_feature_div span.a-price-whole",
                "#buybox span.a-price-whole",
                ".offer-price", ".selling-price", ".deal-price",
                "span[data-a-color='price'] span.a-text-price",
                "span.reinventPricePriceToPayMargin span.a-price-whole",
                "span[aria-label^='Current price'] span.a-offscreen",
                "div[id^='corePrice'] span.a-price-whole"
            ]

            logger.info("Attempting to extract price...")
            price_text_found = None
            for selector in price_selectors:
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.debug(f"Selector {selector} found {len(price_elements)} elements.")
                    for price_element in price_elements:
                        try:
                            if price_element.is_displayed() or "a-offscreen" in price_element.get_attribute("class"):
                                price_text_found = price_element.get_attribute('textContent') or price_element.text
                                if price_text_found and price_text_found.strip():
                                    price_text_found = price_text_found.strip()
                                    logger.debug(f"Found potential price text '{price_text_found}' with selector {selector}.")
                                    cleaned_price = re.sub(r'[^\d.]', '', price_text_found.replace(',', '').replace('₹', ''))
                                    if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                                        price = float(cleaned_price)
                                        logger.info(f"Amazon found price: {price} using selector: {selector}")
                                        return title, price, None
                                    else:
                                        logger.debug(f"Price text '{price_text_found}' is not a valid number after cleaning.")
                                else:
                                    logger.debug("Price element text was empty or whitespace.")
                            else:
                                logger.debug("Price element is not displayed and not off-screen.")
                        except Exception as elem_e:
                            logger.debug(f"Error processing price element with selector {selector}: {elem_e}")
                            continue
                except Exception as sel_e:
                    logger.debug(f"Could not find price with selector {selector}: {str(sel_e)}")
                    continue

            if not price:
                logger.info("Attempting price extraction using JavaScript fallback...")
                try:
                    price_text = self.driver.execute_script("""
                        return document.querySelector('span.a-price-whole')?.textContent?.trim() ||
                               document.querySelector('span.a-offscreen')?.textContent?.trim() ||
                               document.querySelector('span.a-color-price')?.textContent?.trim() ||
                               document.querySelector('#priceblock_dealprice')?.textContent?.trim() ||
                               document.querySelector('#priceblock_ourprice')?.textContent?.trim() ||
                               document.querySelector('.offer-price')?.textContent?.trim();
                    """)
                    if price_text:
                        cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', ''))
                        if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                            price = float(cleaned_price)
                            logger.info(f"Found price using JavaScript fallback: {price}")
                except Exception as e:
                    logger.debug(f"JavaScript price extraction failed: {str(e)}")

            if not price:
                logger.warning(f"Could not find price on Amazon page: {url}")
                return title, None, "Price not found"

            return title, price, None

        except Exception as e:
            error_msg = f"Error fetching Amazon details for {url}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "Unknown Product", None, error_msg

    def _get_reliance_digital_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        logger.info(f"Fetching Reliance Digital details for URL: {url} using Selenium.")
        title = None
        price = None
        error_message = None

        if self.driver is None:
            logger.warning("_get_reliance_digital_details called without driver.")
            return None, None, "Selenium driver not initialized."

        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(random.uniform(4, 7))

            # Log page source immediately after load for debugging with more specific error handling
            logger.debug("Attempting to retrieve page source after initial load.")
            try:
                initial_page_source_snippet = self.driver.page_source[:15000] # Log first 15000 characters
                logger.debug(f"Initial page source snippet after load: {initial_page_source_snippet}...")
            except Exception as e:
                logger.debug(f"Could not get initial page source for logging: {str(e)}")

            title_selectors = [
                'h1.product-name',
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
                'div[class*="PlpProductName"]',
                'h1',
                'h2'
            ]
            for selector in title_selectors:
                try:
                    title_element = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        logger.info(f"Reliance Digital title found: {title[:50]}...")
                        break
                except Exception as e:
                    logger.debug(f"Could not find title with selector {selector}: {e}")
                    continue

            if not title:
                try:
                    page_title = self.driver.title.split("|")[0].strip()
                    if page_title and page_title.lower() != 'reliance digital':
                        title = page_title
                        logger.info(f"Reliance Digital title (fallback from page title): {title[:50]}...")
                    elif not title:
                        title = "Unknown Product"
                        logger.warning(f"Could not find title on Reliance Digital page: {url}")
                except:
                    if not title:
                        title = "Unknown Product"
                    logger.warning(f"Could not find title on Reliance Digital page: {url}")

            price_selectors = [
                # Prioritizing Deal Price selectors based on screenshot
                'div.product-price span.deal-price-text',
                'span.pdp__offerPrice', # This selector also appeared near the price in the screenshot
                'div.pdp__price--new',
                'div.product-price span',
                'div.product-price',
                # Existing selectors (reordered for prioritization)
                'div.product-price span.deal-offer-price',
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
                'div[class*="search-product-price"]',
                'div[class*="product-listing-price"]',
                'div[class*="product-grid-price"]',
                'div[class*="product-item-price"]',
                'div[class*="product-card-price"]',
                'div[class*="ProductCard__Content"] span[class*="price"]',
                'div[class*="ProductItem__Content"] span[class*="price"]',
                'div[class*="ProductTeaser__Content"] span[class*="price"]',
                'div[class*="plp-product-content"] span[class*="price"]',
                'div[class*="search-product-content"] span[class*="price"]',
                'div[class*="product-listing-content"] span[class*="price"]',
                'div[class*="product-grid-content"] span[class*="price"]',
                'div[class*="product-item-content"] span[class*="price"]',
                'div[class*="product-card-content"] span[class*="price"]',
                '.final-price',
                '.offer-price',
                '.sell-price',
                'div.pdp-price-section span.final-price',
                'span[data-testid="currentprice"]',
                'div[data-price]',
                'span[itemprop="price"]',
                'meta[property="product:price:amount"]',
            ]
            price_text_found = None
            for selector in price_selectors:
                logger.debug(f"Attempting to find price with selector: {selector}")
                try:
                    # Increased wait time for price element
                    price_element = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # Check if the element is visible or contains price-like text
                    if price_element.is_displayed() or \
                       ('price' in (price_element.get_attribute('class') or '').lower()) or \
                       ('amount' in (price_element.get_attribute('class') or '').lower()) or \
                       ('₹' in price_element.text or 'Rs.' in price_element.text or 'INR' in price_element.text or re.search(r'\d', price_element.text)):

                        # Attempt to get text content, handling potential attributes
                        raw_text = price_element.get_attribute('textContent') or price_element.text

                        # For meta tags, get the content attribute
                        if price_element.tag_name == 'meta' and price_element.get_attribute('property') == 'product:price:amount':
                            raw_text = price_element.get_attribute('content')
                            logger.debug(f"Extracted price from meta tag: {raw_text}")

                        if raw_text and ('₹' in raw_text or 'Rs.' in raw_text or 'INR' in raw_text or re.search(r'\d', raw_text)):
                            price_text_found = raw_text.strip()
                            logger.debug(f"Price found with selector {selector}: {price_text_found[:50]}...")
                            break
                        else:
                             logger.debug(f"Selector {selector} found element, but text '{raw_text[:50]}...' does not contain price indicators.")

                except Exception as e:
                    logger.debug(f"Could not find price with selector {selector}: {e}")
                    continue

            if price_text_found:
                price_patterns = [
                    r'₹\s*([\d,]+\.?\d*)',
                    r'Rs\.?\s*([\d,]+\.?\d*)',
                    r'INR\s*([\d,]+\.?\d*)',
                    r'([\d,]+\.?\d*)'
                ]

                for pattern in price_patterns:
                    match = re.search(pattern, price_text_found)
                    if match:
                        cleaned_price_str = match.group(1).replace(',', '')
                        if cleaned_price_str.replace('.', '', 1).isdigit():
                            price = float(cleaned_price_str)
                            logger.info(f"Reliance Digital found price: {price}")
                            return title, price, None
                        else:
                            logger.debug(f"Reliance Digital price text found '{price_text_found}' but not a valid number.")
                    else:
                        logger.debug(f"Reliance Digital price text found '{price_text_found}' but no regex pattern matched.")

            if price is None:
                logger.warning(f"Could not find price on Reliance Digital page: {url}")
                return title, None, "Price not found"

            return title, price, None

        except Exception as e:
            error_msg = f"Error fetching Reliance Digital details for {url}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "Unknown Product", None, error_msg

    def _product_matches(self, search_term: str, result_title: str, threshold=0.3) -> bool:
        if not search_term or not result_title:
            logger.debug("_product_matches: Empty search term or result title")
            return False

        logger.debug(f"_product_matches: Comparing search_term='{search_term}' with result_title='{result_title}'")

        search_term_lower = search_term.lower()
        result_title_lower = result_title.lower()

        common_noise = {'and', 'with', 'for', 'the', 'new', 'in', 'on', 'of', 'at', 'by', 'to', 'from', 'a', 'an', 'is', 'it', 'this', 'that', 'buy', 'now', 'get', 'best', 'price', 'offers', 'deals', 'sale', 'discount'}
        search_words = set(re.findall(r'\b\w+\b', search_term_lower)) - common_noise
        result_words = set(re.findall(r'\b\w+\b', result_title_lower)) - common_noise

        logger.debug(f"_product_matches: Cleaned search words: {search_words}")
        logger.debug(f"_product_matches: Cleaned result words: {result_words}")

        brands = ['whirlpool', 'lg', 'samsung', 'haier', 'godrej', 'bosch', 'panasonic', 'hitachi', 'voltas', 'blue star', 'poco', 'xiaomi', 'redmi', 'apple', 'oneplus', 'realme', 'oppo', 'vivo', 'nokia', 'motorola', 'google pixel', 'iqoo', 'infinix', 'tecno']
        search_brand = next((brand for brand in brands if brand in search_term_lower), None)
        result_brand = next((brand for brand in brands if brand in result_title_lower), None)

        if search_brand and result_brand:
            logger.debug(f"_product_matches: Brand match found - Search: {search_brand}, Result: {result_brand}")
            if search_brand != result_brand:
                logger.debug("_product_matches: Different brands found, rejecting match")
                return False
        elif search_brand and not result_brand:
            logger.debug(f"_product_matches: Search has brand {search_brand} but result doesn't")
            return False

        model_pattern = r'[a-zA-Z0-9]+(?:[-/]?[a-zA-Z0-9]+)*'
        search_models = set(re.findall(model_pattern, search_term_lower))
        result_models = set(re.findall(model_pattern, result_title_lower))

        common_words = {'gb', 'ram', 'storage', 'inch', 'cm', 'mm', 'kg', 'g', 'l', 'ml', 'w', 'wh', 'mah', 'mp', 'hz', 'tb', 'mb', 'kb'}
        search_models = search_models - common_words
        result_models = result_models - common_words

        logger.debug(f"_product_matches: Search models: {search_models}")
        logger.debug(f"_product_matches: Result models: {result_models}")

        common_models = search_models.intersection(result_models)
        if common_models:
            logger.debug(f"_product_matches: Found common model numbers: {common_models}")
            return True

        spec_patterns = [
            r'\d+\s*gb(?:\s*ram)?',
            r'\d+\s*tb',
            r'\d+\s*inch',
            r'\d+\s*mp',
            r'\d+\s*mah',
            r'\d+\s*w',
            r'\d+\s*hz',
            r'\d+\s*star'
        ]

        search_specs = set()
        result_specs = set()

        for pattern in spec_patterns:
            search_specs.update(re.findall(pattern, search_term_lower))
            result_specs.update(re.findall(pattern, result_title_lower))

        logger.debug(f"_product_matches: Search specs: {search_specs}")
        logger.debug(f"_product_matches: Result specs: {result_specs}")

        if search_specs:
            common_specs = search_specs.intersection(result_specs)
            if common_specs:
                logger.debug(f"_product_matches: Found common specs: {common_specs}")
                return True
            else:
                logger.debug("_product_matches: No matching specs found")
                return False

        common_words = search_words.intersection(result_words)
        logger.debug(f"_product_matches: Common words: {common_words}")

        if not search_words:
            logger.debug("_product_matches: No search words after cleaning")
            return False

        similarity_score = len(common_words) / len(search_words)
        logger.debug(f"_product_matches: Similarity score: {similarity_score:.2f}")

        is_match = similarity_score >= threshold
        logger.debug(f"_product_matches: Final match decision: {is_match}")

        return is_match

    def _search_amazon(self, search_term: str) -> Optional[str]:
        """Search for product price on Amazon."""
        if not self.driver or not search_term:
            logger.warning("_search_amazon called without driver or search term.")
            return "WebDriver/SearchTerm Error"

        search_url = f"https://www.amazon.in/s?k={quote_plus(search_term)}"
        logger.info(f"_search_amazon: URL: {search_url} using Selenium.")

        try:
            self.driver.get(search_url)
            WebDriverWait(self.driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')))
            time.sleep(random.uniform(3, 5))

            products = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, 'div.s-result-item[data-asin], div[data-asin].sg-col-20-of-24, [data-component-type="s-search-result"] div.a-section')

            logger.info(f"Amazon search found {len(products)} potential items.")

            for product_element in products[:10]:
                product_title, product_price = None, None
                logger.debug("Processing a potential Amazon search result item.")
                try:
                    title_el = product_element.find_element(By.CSS_SELECTOR, 'h2 a span, span.a-size-medium.a-color-base.a-text-normal, .a-text-normal, a.a-link-normal.a-text-normal')
                    product_title = title_el.text.strip()
                    logger.debug(f"Extracted title from search result: {product_title[:50]}...")
                except Exception as e:
                    logger.debug(f"Could not find title for a potential Amazon search result: {e}")
                    continue

                if self._product_matches(search_term, product_title, threshold=0.5):
                    logger.info(f"Amazon Match: '{product_title[:50]}...' with search term '{search_term[:50]}...'")
                    logger.debug("Attempting to extract price from matched Amazon search result.")
                    price_selectors = [
                        'span.a-price-whole',
                        'span.a-offscreen',
                        '.a-price-current span.a-price-whole',
                        'span[data-a-color="price"] span.a-offscreen',
                        'span[data-a-color="secondary"] span.a-offscreen',
                        'span[data-a-color="base"] span.a-offscreen',
                        'div[data-cy="price-recipe"] span.a-price-whole',
                        'span.priceToPay span.a-price-whole',
                        '#apex_desktop_newAccordionRow span.a-price-whole',
                        'span.a-price.aok-align-center span.a-offscreen',
                        'div[data-cy="price-block"] span.a-offscreen',
                        'div[data-cy="price"] span.a-offscreen',
                        'div[data-cy="price-block"] span.a-price-whole',
                        'div[data-cy="price"] span.a-price-whole',
                        '#corePriceDisplay_feature_div span.a-price-whole',
                        '#buybox span.a-price-whole',
                        '.offer-price', '.selling-price', '.deal-price',
                        'span[data-a-color="price"] span.a-text-price',
                        'span.reinventPricePriceToPayMargin span.a-price-whole',
                        'span[aria-label^=\'Current price\'] span.a-offscreen',
                        'div[id^=\'corePrice\'] span.a-price-whole',
                        # Added more selectors for search results
                        'div.a-row.a-size-base.a-color-price span.a-offscreen',
                        'div.a-row.a-size-base.a-color-price span.a-price-whole',
                        'span.offscreen',
                        'span.a-price > span.a-offscreen',
                        'span.a-size-base.a-color-price',
                        'div.s-price-if-supported span.a-offscreen',
                        'div.s-price-if-supported span.a-price-whole',
                        'span[data-a-strike="true"] + span.a-offscreen', # Handle sale prices
                        'span[data-a-strike="true"] + span.a-price-whole', # Handle sale prices
                        'div[data-index] span.a-price-whole',
                        'div[data-index] span.a-offscreen'
                    ]
                    for selector in price_selectors:
                        logger.debug(f"Attempting to find price within search result item with selector: {selector}")
                        try:
                            # Use find_elements to handle multiple potential price elements
                            price_elements = product_element.find_elements(By.CSS_SELECTOR, selector)
                            logger.debug(f"Selector {selector} found {len(price_elements)} elements within search result item.")
                            for price_element in price_elements:
                                if price_element.is_displayed() or "a-offscreen" in price_element.get_attribute("class"):
                                    price_text = price_element.get_attribute('textContent') or price_element.text
                                    if price_text and price_text.strip():
                                        price_text = price_text.strip()
                                        logger.debug(f"Found potential raw price text within search result: {price_text[:50]}...")
                                        price = self._clean_price(price_text)
                                        if price:
                                            logger.info(f"Found price: {price} for product: {product_title}")
                                            return str(price)
                                        else:
                                            logger.debug(f"Cleaned price from search result '{self._clean_price(price_text)}' is not a valid number or empty.")
                                    else:
                                        logger.debug(f"Price element text for selector {selector} was empty or whitespace within search result.")
                                else:
                                    logger.debug(f"Price element with selector {selector} is not displayed and not off-screen within search result.")
                        except Exception as e:
                            logger.debug(f"Could not find price within search result with selector {selector}: {e}")
                            continue

                else:
                    logger.debug(f"Amazon No Match: '{product_title[:50]}...' vs '{search_term[:50]}...'")

        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}", exc_info=True)
            return "Search Error"
        return "Not found"

    async def _search_reliance_digital(self, product_name: str) -> Optional[str]:
        """Search for product price on Reliance Digital."""
        try:
            # Initialize WebDriver with increased timeouts
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(120)  # Increased timeout
            
            try:
                # Improved search URL construction with multiple attempts
                search_terms = product_name.split()
                search_attempts = []
                
                # First attempt: Full search term with spaces replaced by +
                search_attempts.append('+'.join(search_terms))
                
                # Second attempt: Remove common words and numbers
                filtered_terms = [term for term in search_terms if len(term) > 2 and term.lower() not in ['the', 'and', 'for', 'with']]
                search_attempts.append('+'.join(filtered_terms))
                
                # Third attempt: Brand + Model only
                brand_terms = []
                model_terms = []
                for term in search_terms:
                    if term.lower() in ['apple', 'samsung', 'xiaomi', 'oneplus', 'realme', 'oppo', 'vivo', 'motorola']:
                        brand_terms.append(term)
                    elif term.lower() not in ['gb', 'tb', 'blue', 'black', 'white', 'red', 'green', 'silver', 'gold']:
                        model_terms.append(term)
                if brand_terms and model_terms:
                    search_attempts.append('+'.join(brand_terms + model_terms))
                
                # Try each search attempt
                for search_query in search_attempts:
                    url = f'https://www.reliancedigital.in/search?q={search_query}'
                    logger.info(f"Trying Reliance Digital search with URL: {url}")
                    
                    # Load the page with retry mechanism
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            driver.get(url)
                            # Wait for initial page load
                            await asyncio.sleep(15)  # Increased wait time
                            
                            # Check if we got a "page not found" error
                            page_source = driver.page_source.lower()
                            if "page was not found" in page_source or "no results found" in page_source:
                                logger.warning(f"Reliance Digital search returned no results for: {search_query}")
                                if attempt < max_retries - 1:
                                    continue
                                break  # Try next search query
                            
                            # Scroll multiple times to load all content
                            for _ in range(8):  # Increased scroll attempts
                                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                await asyncio.sleep(4)  # Increased wait time between scrolls
                            
                            # Scroll back to top
                            driver.execute_script("window.scrollTo(0, 0);")
                            await asyncio.sleep(3)
                            
                            # Updated selectors for Reliance Digital's current structure
                            product_selectors = [
                                'div[class*="product-item"]',
                                'div[class*="product-card"]',
                                'div[class*="product-grid-item"]',
                                'div[class*="product-listing-item"]',
                                'div[class*="ProductItem"]',
                                'div[class*="ProductCard"]',
                                'div[class*="ProductGridItem"]',
                                'div[class*="ProductListingItem"]',
                                'div[class*="plp-product-item"]',
                                'div[class*="search-product-item"]',
                                'div[class*="product"]',
                                'div[class*="Product"]',
                                'div[class*="item"]',
                                'div[class*="card"]',
                                'div[class*="sp__product"]',  # Added new selector
                                'div[class*="product-list"]',  # Added new selector
                                'div[data-testid="product-card"]',  # Added new selector
                                'div[data-ecommerce-id]'  # Added new selector
                            ]
                            
                            name_selectors = [
                                'div[class*="product-title"]',
                                'div[class*="product-name"]',
                                'h2[class*="product-title"]',
                                'h2[class*="product-name"]',
                                'div[class*="ProductTitle"]',
                                'div[class*="ProductName"]',
                                'div[class*="plp-product-title"]',
                                'div[class*="search-product-title"]',
                                'div[class*="product"] h2',
                                'div[class*="Product"] h2',
                                'h2',
                                'h3',
                                'div[class*="title"]',
                                'div[class*="name"]',
                                'div[class*="sp__product-name"]',  # Added new selector
                                'div[class*="product-list-name"]',  # Added new selector
                                'span[class*="product-name"]'  # Added new selector
                            ]
                            
                            price_selectors = [
                                'div[class*="product-price"]',
                                'div[class*="product-amount"]',
                                'span[class*="product-price"]',
                                'span[class*="product-amount"]',
                                'div[class*="ProductPrice"]',
                                'div[class*="ProductAmount"]',
                                'span[class*="ProductPrice"]',
                                'span[class*="ProductAmount"]',
                                'div[class*="plp-product-price"]',
                                'div[class*="search-product-price"]',
                                'div[class*="product"] span[class*="price"]',
                                'div[class*="Product"] span[class*="price"]',
                                'span[class*="price"]',
                                'div[class*="price"]',
                                'span[class*="amount"]',
                                'div[class*="amount"]',
                                'span[data-testid="price"]',  # Added new selector
                                'div[class*="sp__product-price"]',  # Added new selector
                                'div[class*="product-list-price"]',  # Added new selector
                                'span[class*="product-price"]',  # Added new selector
                                'div.Nx9bqj'  # This selector worked for the direct URL
                            ]
                            
                            # Find all product elements
                            product_elements = []
                            for selector in product_selectors:
                                try:
                                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                    if elements:
                                        product_elements.extend(elements)
                                        logger.info(f"Found {len(elements)} product elements with selector: {selector}")
                                except Exception as e:
                                    logger.debug(f"Could not find elements with selector {selector}: {e}")
                                    continue
                            
                            if not product_elements:
                                logger.warning(f"No product elements found for: {search_query}")
                                if attempt < max_retries - 1:
                                    continue
                                break  # Try next search query
                            
                            # Find matching product
                            for product_element in product_elements:
                                # Get product name
                                product_name_element = None
                                for selector in name_selectors:
                                    try:
                                        name_element = product_element.find_element(By.CSS_SELECTOR, selector)
                                        if name_element and name_element.text.strip():
                                            product_name_element = name_element
                                            break
                                    except Exception:
                                        continue
                                
                                if not product_name_element:
                                    continue
                                
                                product_title = product_name_element.text.strip()
                                logger.debug(f"Found product title: {product_title}") # Log the found product title
                                
                                # Check if product matches
                                if self._product_matches(product_name, product_title, threshold=0.3): # Pass threshold here as well
                                    logger.info(f"Found matching product: {product_title}")
                                    
                                    # Get price
                                    for selector in price_selectors:
                                        try:
                                            price_element = product_element.find_element(By.CSS_SELECTOR, selector)
                                            if price_element and price_element.text.strip():
                                                price_text = price_element.text.strip()
                                                price = self._clean_price(price_text)
                                                if price:
                                                    logger.info(f"Found price: {price} for product: {product_title}")
                                                    return price
                                        except Exception as e:
                                            logger.debug(f"Could not find price with selector {selector}: {e}")
                                            continue

                        except TimeoutException:
                            if attempt < max_retries - 1:
                                logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                                await asyncio.sleep(5)
                                continue
                            else:
                                logger.error(f"Timeout after {max_retries} attempts")
                                break  # Try next search query
                        except Exception as e:
                            logger.error(f"Error during search attempt {attempt + 1}: {str(e)}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(5)
                                continue
                            else:
                                break  # Try next search query
                
            finally:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Error while closing WebDriver: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in _search_reliance_digital: {str(e)}")
            return None
        
        return None

    def _clean_price(self, price_text: str) -> Optional[str]:
        """Clean and validate price text."""
        try:
            # Remove currency symbols and other non-numeric characters
            cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
            
            # Validate the cleaned price
            if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                return cleaned_price
            return None
        except Exception as e:
            logger.error(f"Error cleaning price text: {str(e)}")
            return None

    def _search_flipkart(self, search_term: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """Search for product on Flipkart and return price."""
        if not self.driver:
            logger.warning("_search_flipkart called without driver.")
            return None, None, "WebDriver Error"

        try:
            search_url = f"https://www.flipkart.com/search?q={quote_plus(search_term)}"
            logger.info(f"Searching Flipkart with URL: {search_url}")

            self.driver.get(search_url)
            time.sleep(random.uniform(4, 6))

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

            product_listing_selectors = [
                'div._1AtVbE',
                'div._2kHMtA',
                'div[class*="product-listing"] > div',
                'div[class*="product-grid"] > div',
                'div[class*="product-item"] > div',
                'div[data-id]'
            ]

            found_price = None
            found_title = None

            for listing_selector in product_listing_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, listing_selector)))

                    product_listings = self.driver.find_elements(By.CSS_SELECTOR, listing_selector)
                    logger.info(f"Found {len(product_listings)} potential product listings with selector {listing_selector}.")

                    if not product_listings:
                        continue

                    for product_element in product_listings:
                        listing_title, listing_price = None, None

                        title_selectors = [
                            'div._4rR01T',
                            'a.s1Q9rs',
                            'div.KzDlHZ',
                            'div[class*="product-title"] a',
                            'a[title]'
                        ]
                        for title_sel in title_selectors:
                            try:
                                title_element = product_element.find_element(By.CSS_SELECTOR, title_sel)
                                if title_element and title_element.text.strip():
                                    listing_title = title_element.text.strip()
                                    break
                            except:
                                continue

                        if not listing_title:
                            logger.debug("Could not find title in listing.")
                            continue

                        if not self._product_matches(search_term, listing_title, threshold=0.5):
                            logger.debug(f"Listing title '{listing_title[:50]}...' does not match search term '{search_term[:50]}...'")
                            continue

                        logger.info(f"Found potentially matching listing: '{listing_title[:50]}...'")

                        price_selectors = [
                            'div._30jeq3._1_WHN1',
                            'div._30jeq3',
                            'div._1_WHN1',
                            'div.Nx9bqj._3_XqSL',
                            'div._16Jk6d',
                            'div._25b18c',
                            'div._3qQ9m1',
                            'div[class*="product-price"] div',
                            'div[class*="Price"] div',
                            '.col-5-12 div._30jeq3',
                            '.col-5-12 div._1_WHN1',
                            '.col-5-12 div._16Jk6d',
                            '.col-5-12 div._25b18c',
                            '.col-5-12 div._3qQ9m1',
                            '.col-5-12 span._30jeq3',
                            '.col-5-12 span._1_WHN1',
                            '.col-5-12 span._16Jk6d',
                            '.col-5-12 span._25b18c',
                            '.col-5-12 span._3qQ9m1',
                            'div[data-id] div[class*="price"] div',
                            'div[data-id] span[class*="price"]',
                            'div[data-id] div[class*="Price"] span',
                            'div[data-id] span[class*="Price"] div',
                            'span:contains("₹")',
                            'div:contains("₹")',
                            'span:has(> div._30jeq3)',
                            'div:has(> span._30jeq3)',
                            '._30jeq3',
                            '._1_WHN1',
                            '._16Jk6d',
                            '._25b18c',
                            '._3qQ9m1',
                            '[class*="price"]:not([class*="old"]):not([class*="strike"])',
                            '[class*="Price"]:not([class*="old"]):not([class*="strike"])',
                            'div._30jeq3',
                            'div._1_WHN1',
                            'div.Nx9bqj',
                            'div[class*="currentPrice"]',
                            'div[class*="sellingPrice"]',
                            'div[class*="finalPrice"]',
                            'span[class*="currentPrice"]',
                            'span[class*="sellingPrice"]',
                            'span[class*="finalPrice"]',
                            'div[class*="priceRow"] span',
                            'div[class*="price"] span',
                            'div[class*="PriceBlock"] span'
                        ]
                        for price_sel in price_selectors:
                            try:
                                price_element = product_element.find_element(By.CSS_SELECTOR, price_sel)
                                if price_element and price_element.text.strip():
                                    price_text = price_element.text.strip()
                                    cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', ''))
                                    if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                                        listing_price = float(cleaned_price)
                                        logger.info(f"Found price {listing_price} in listing using selector {price_sel}.")
                                        return listing_title, listing_price, None
                                    else:
                                        logger.debug(f"Cleaned price from listing '{cleaned_price}' is not a valid number.")
                                break
                            except:
                                continue

                        if not listing_price:
                            logger.debug("Could not find price in matching listing.")

                except Exception as e:
                    logger.debug(f"Error with listing selector {listing_selector}: {e}")
                    continue

            logger.info("No price found directly in listings, attempting to click first product.")
            product_link_selectors = [
                'a._1fQZEK',
                'a.s1Q9rs',
                'a._2UzuFa',
                'a._3fP5Ro',
                'div._2kHMtA a',
                'div._1AtVbE a',
                'div[class*="product"] a',
                'div[class*="Product"] a'
            ]

            for selector in product_link_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

                    product_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if product_links:
                        logger.info(f"Clicking first product link with selector {selector}.")
                        product_links[0].click()
                        time.sleep(random.uniform(3, 5))
                        return self._get_flipkart_details(self.driver.current_url)
                except Exception as e:
                    logger.debug(f"Error clicking product link with selector {selector}: {e}")
                    continue

            logger.warning(f"No matching product or clickable link found on Flipkart after search for '{search_term}'")
            return None, None, "Product or price not found"

        except Exception as e:
            logger.error(f"Error searching Flipkart: {str(e)}", exc_info=True)
            return None, None, f"Search error: {str(e)[:50]}"

price_extractor = PriceExtractor()

if __name__ == "__main__":
    async def main():
        url = input("Enter the product URL (Amazon, Flipkart, or Reliance Digital): ").strip()

        if not url:
            print("No URL provided. Exiting.")
            exit(1)

        print(f"\n{'='*50}")
        print(f"Analyzing URL: {url}")

        try:
            product_name, results = await price_extractor.get_product_details(url)

            print(f"\nProduct Identified: {product_name}")
            print(f"{'-'*50}")

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
                    logger.error(f"Error during final Selenium cleanup: {str(e)}")
                    print(f"Error during final Selenium cleanup: {str(e)}")
        print(f"{'='*50}\n")

    asyncio.run(main())