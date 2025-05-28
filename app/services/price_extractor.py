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
                # Keep headless for background operation, but some anti-bots detect headless
                # If issues persist, running non-headless might be necessary (requires display)
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--enable-system-font-check') # Added to potentially help with DNS resolution issues
                # Removed --disable-gpu as it might be needed in new headless
                # chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                # Using UserAgent().random is good, keep this.
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                chrome_options.add_argument('--page-load-timeout=60') # Increased timeout again
                chrome_options.add_argument('--script-timeout=60') # Increased timeout again

                # Add or refine additional options to bypass detection
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-browser-side-navigation')
                chrome_options.add_argument('--disable-site-isolation-trials')
                # Kept logging/silent options
                chrome_options.add_argument('--disable-logging')
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument('--silent')

                # Kept stability options
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

                # Added specific arguments recommended for undetected_chromedriver (kept and refined)
                chrome_options.add_argument('--incognito') # Good for isolating sessions
                # chrome_options.add_argument('--disable-settings-window') # Less impactful for bot detection
                # chrome_options.add_argument('--disable-spellchecking') # Less impactful
                # chrome_options.add_argument('--disable-web-security') # Might cause issues
                chrome_options.add_argument('--no-proxy-server') # Ensure no default proxy is used
                # chrome_options.add_argument('--enable-automation') # Leave this to undetected_chromedriver

                # Additional stealth options based on common practices
                chrome_options.add_argument('--disable-features=EnableEphemeralFlashPermission')
                chrome_options.add_argument('--disable-infobars') # Still useful sometimes
                chrome_options.add_argument('--disable-notifications') # Can trigger popups
                chrome_options.add_argument('--disable-popup-blocking') # Can trigger popups
                chrome_options.add_argument('--ignore-certificate-errors') # Not directly for botting but avoids SSL issues
                chrome_options.add_argument('--allow-running-insecure-content')
                # Prevent infobars again just in case
                # REMOVE THIS LINE: chrome_options.add_experimental_option("useAutomationExtension", False)

                logger.info(f"Attempting to initialize WebDriver with enhanced stealth (attempt {attempt + 1}/{max_retries})...")
                # Use a more recent version for better compatibility if available (kept user's version)
                self.driver = uc.Chrome(
                    options=chrome_options,
                    version_main=137, # Use the user's detected Chrome version
                    suppress_welcome=True,
                    use_subprocess=True,
                    # Added browser_executable_path if chrome is not in default location
                    # browser_executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe' # Example path, user might need to adjust
                )

                # Set additional properties after initialization using CDP
                # Use CDP to remove navigator.webdriver property - key for evading detection (kept)
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                          get: () => undefined
                        })
                    """
                })

                # Use CDP to mask Chrome automation flags (kept)
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        window.chrome = {
                          runtime: {},
                          // etc.
                        };
                    """
                })
                
                # Added CDP to spoof navigator.languages and other properties
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
                          get: () => 8 // Spoof a common value
                        });
                        Object.defineProperty(navigator, 'hardwareConcurrency', {
                          get: () => 8 // Spoof a common value
                        });
                        // Spoof screen size properties
                        Object.defineProperty(screen, 'width', { get: () => 1920 });
                        Object.defineProperty(screen, 'height', { get: () => 1080 });
                        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
                        Object.defineProperty(screen, 'availHeight', { get: () => 1040 }); // Account for taskbar
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
            
            # Initialize Selenium driver for all platforms
            try:
                self._initialize_driver()
            except Exception as e:
                error_msg = f"Failed to initialize Selenium WebDriver: {str(e)}"
                logger.error(error_msg)
                return error_msg, {'amazon': error_msg, 'flipkart': error_msg, 'reliancedigital': error_msg}
            
            if initial_platform == 'amazon':
                amazon_title, amazon_price, amazon_error = self._get_amazon_details(url)
                initial_product_name_for_display = amazon_title if amazon_title else initial_product_name_for_display
                if amazon_price is not None: results['amazon'] = str(amazon_price)
                elif amazon_error: results['amazon'] = amazon_error
                search_title_base = amazon_title if amazon_title and amazon_title != "Unknown Product" else None

            elif initial_platform == 'flipkart':
                logger.info(f"Fetching Flipkart details for URL: {url}")
                flipkart_title, flipkart_price, flipkart_error = self._get_flipkart_details(url)
                initial_product_name_for_display = flipkart_title if flipkart_title else initial_product_name_for_display
                if flipkart_price is not None: results['flipkart'] = str(flipkart_price)
                elif flipkart_error: results['flipkart'] = flipkart_error
                search_title_base = flipkart_title if flipkart_title and flipkart_title != "Unknown Product" else None

            elif initial_platform == 'reliancedigital':
                reliance_title, reliance_price, reliance_error = self._get_reliance_digital_details(url)
                initial_product_name_for_display = reliance_title if reliance_title else initial_product_name_for_display
                if reliance_price is not None: results['reliancedigital'] = str(reliance_price)
                elif reliance_error: results['reliancedigital'] = reliance_error
                search_title_base = reliance_title if reliance_title and reliance_title != "Unknown Product" else None

            if search_title_base:
                cleaned_search_term = self._clean_title_for_search(search_title_base, url)
                logger.info(f"Original title: '{search_title_base}'")
                logger.info(f"Cleaned search term: '{cleaned_search_term}'")

                # Search Flipkart if initial platform wasn't Flipkart
                if initial_platform != 'flipkart':
                    logger.info(f"Searching Flipkart with term: '{cleaned_search_term}'")
                    flipkart_search_title, flipkart_search_price, flipkart_search_error = self._search_flipkart(cleaned_search_term)
                    if flipkart_search_price is not None:
                        results['flipkart'] = str(flipkart_search_price)
                    elif flipkart_search_error:
                        results['flipkart'] = flipkart_search_error

                # Search Amazon if initial platform wasn't Amazon
                if initial_platform != 'amazon':
                    logger.info(f"Searching Amazon with term: '{cleaned_search_term}'")
                    amazon_search_result = self._search_amazon(cleaned_search_term)
                    if amazon_search_result and results['amazon'] == 'Not found':
                        results['amazon'] = amazon_search_result

                # Search Reliance Digital if initial platform wasn't Reliance Digital
                if initial_platform != 'reliancedigital':
                    logger.info(f"Searching Reliance Digital with term: '{cleaned_search_term}'")
                    reliance_search_result = self._search_reliance_digital(cleaned_search_term)
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
        
        brands = ['poco', 'xiaomi', 'redmi', 'samsung', 'apple', 'oneplus', 'realme', 'oppo', 'vivo', 'nokia', 'motorola', 'google pixel', 'iqoo', 'infinix', 'tecno',
                  'haier', 'lg', 'samsung', 'whirlpool', 'godrej', 'bosch', 'panasonic', 'hitachi', 'voltas', 'blue star', 'ifb', 'sony', 'dell', 'hp', 'lenovo', 'acer', 'asus',
                  'bajaj', 'havells', 'orient', 'usha', 'crompton', # Fans/Appliances
                  'lg', 'samsung', 'sony', 'whirlpool', 'haier', # TVs, ACs, Refrigerators, Washing Machines
                   'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', # Laptops/Computers
                  'canon', 'nikon', 'sony', 'fujifilm', # Cameras
                  'boat', 'jbl', 'sony', 'bose', 'sennheiser', # Audio
                  'mi', 'realme', 'oneplus', 'oppo', 'vivo', 'infinix', 'tecno', 'motorola', 'samsung', 'apple', 'google pixel', 'iqoo', 'infinix', 'tecno',
                  'fitbit', 'garmin', 'apple', 'samsung', 'xiaomi' # Wearables
                 ]
        extracted_brand = None
        sorted_brands = sorted(brands, key=len, reverse=True)
        for b_norm in sorted_brands:
            if re.search(r'\b' + re.escape(b_norm) + r'\b', lower_title):
                extracted_brand = b_norm
                break
        
        model_words = []
        # Attempt to extract model details (often alphanumeric sequences)
        if extracted_brand:
            try:
                # Look for model name after the brand
                after_brand_str_match = re.search(re.escape(extracted_brand) + r'\s+([a-zA-Z0-9\s\-\/]+?)(?:\(|,|with|and|gb|ram|mah|inch|hz|mp|w|ltr|kg|star|tb|°|$)', lower_title)
                if after_brand_str_match:
                    potential_model_phrase = after_brand_str_match.group(1).strip()
                    # Take up to 4-5 words for model, stopping if specs appear
                    temp_model_parts = []
                    for part in potential_model_phrase.split():
                         # Check for spec-like patterns more robustly
                        if len(temp_model_parts) < 5 and not re.match(r'\d+(\s*(gb|ram|mah|inch|hz|mp|w|ltr|kg|star|tb|°))?\b', part, re.IGNORECASE) and part not in ['with', 'and']:
                            temp_model_parts.append(part)
                        else:
                            break
                    if temp_model_parts:
                        model_words = temp_model_parts
            except Exception:
                pass # Ignore errors in model extraction

        if not model_words: # Fallback if brand-based extraction fails or is insufficient
            # Try to find prominent alphanumeric sequences anywhere in the title
            # This regex tries to capture sequences like "C75 5G", "Galaxy S23", "14 Pro Max", "HRD-2203BS"
            # It looks for words with letters and numbers, or words that are largely numbers with a few letters (like model numbers).
            # Added more patterns to capture different model number formats
            prominent_alphanum_phrases = re.findall(r'\b([a-zA-Z]*[0-9]+[a-zA-Z0-9-]*(\s+[a-zA-Z0-9-]{1,10}){0,3})\b|\b([a-zA-Z]{1,5}[-\/][0-9]{2,}[a-zA-Z0-9-]*)\b|\b([0-9]+[a-zA-Z]+)\b', lower_title)

            # Process found phrases, preferring longer ones and those with mixed alpha/numeric
            candidates = []
            for phrase_tuple in prominent_alphanum_phrases:
                for phrase_part in phrase_tuple: # Each tuple can have multiple groups from the regex OR
                    if phrase_part:
                        phrase_part_cleaned = phrase_part.strip()
                        # Filter out common spec-like patterns explicitly if they are standalone (e.g. just "4gb")
                        # Improved filtering regex
                        if not re.fullmatch(r'\d+\s*(gb|mah|hz|inch|mp|w|ltr|kg|star|tb|°)\b', phrase_part_cleaned.replace(" ", ""), re.IGNORECASE) and len(phrase_part_cleaned) > 2:
                            candidates.append(phrase_part_cleaned)

            # Sort by length and take the most promising ones, avoid simple numbers if longer phrases exist
            candidates = sorted(list(set(candidates)), key=len, reverse=True)
            if candidates:
                # Take the best candidate, up to 4 words (increased from 3)
                model_words = candidates[0].split()[:4]

        specs = []
        # RAM
        ram_match = re.search(r'\(?\b(\d+)\s*gb(?:\s*ram)?\b\)?', lower_title)
        if ram_match: specs.append(f"{ram_match.group(1)}gb ram")

        # ROM/Storage (ensure it's not the same as RAM if both are just "Xgb")
        # Find all Xgb patterns, then filter
        all_gb_matches = re.findall(r'\(?\b(\d+)\s*gb\b\)?', lower_title)
        ram_value_str = ram_match.group(1) if ram_match else None
        for gb_val_str in all_gb_matches:
            if gb_val_str != ram_value_str: # If it's different from RAM, or RAM not found
                # Check context around this gb_val_str to ensure it's not part of RAM description if RAM was already found
                 if not (ram_match and f"{gb_val_str}gb ram" in lower_title) and f"{gb_val_str}gb".lower() not in " ".join(model_words).lower():
                    specs.append(f"{gb_val_str}gb") # Could be storage
                    break # Take the first non-RAM GB value as storage

        # Star Rating (e.g., "5 Star")
        star_match = re.search(r'(\d+)\s*star\b', lower_title)
        if star_match:
            specs.append(f"{star_match.group(1)} star")

        # Capacity (e.g., "190L")
        capacity_match = re.search(r'(\d+)\s*l(?=\s|$)|\b(\d+)\s*litre', lower_title)
        if capacity_match:
             specs.append(f"{capacity_match.group(1) or capacity_match.group(2)}l")

        # Other common specs (5G, colors - refined)
        if "5g" in lower_title and "5g" not in " ".join(model_words).lower(): specs.append("5g")

        # Color: Look for common color keywords or plausible color phrases before specs or parentheses
        # Example: "Aqua Bliss (4GB" -> "Aqua Bliss"
        # Example: "Midnight Black, 128GB" -> "Midnight Black"
        color_keywords = ['black', 'white', 'blue', 'red', 'green', 'silver', 'gold', 'gray', 'grey', 'purple', 'pink', 'orange', 'yellow', 'brown', 'bronze', 'aqua', 'marine', 'sky', 'midnight', 'space', 'rose', 'graphite', 'sierra', 'alpine', 'wine', 'solid'] # Added 'wine' and 'solid'
        # Try to extract a multi-word color phrase (more flexible regex)
        color_phrase_match = re.search(r',?\s+((?:[a-zA-Z]+\s+){0,3}[a-zA-Z]+)\s*\(?(?:\d+gb|,|with|and|$|\))', lower_title) # Increased word count
        if color_phrase_match:
            color_candidate = color_phrase_match.group(1).strip().replace(',', '')
            # Check if candidate contains known color words or seems like a plausible color name
            if any(ckw in color_candidate.lower() for ckw in color_keywords) and len(color_candidate.split()) <= 4 and len(color_candidate) > 2: # Increased word count
                if not any(stopword in color_candidate.lower() for stopword in ['storage', 'memory', 'edition', 'new', 'model', 'version', 'direct cool', 'single door', 'double door', 'triple door']): # Added more stopwords
                    specs.append(color_candidate)

        search_parts = []
        if extracted_brand: search_parts.append(extracted_brand)

        # Add model words, ensuring they are not too generic if brand is also generic
        if model_words:
            # Filter out very short model words if brand is short and model word is just a number (e.g. brand "lg", model "5" -> too generic)
            filtered_model_words = [mw for mw in model_words if not (len(mw) <= 2 and mw.isdigit() and extracted_brand and len(extracted_brand) <=3)]
            search_parts.extend(filtered_model_words)

        # Add unique specs, prioritizing those with numbers or specific keywords
        final_specs_to_add = []
        processed_specs_lower = set()

        # Prioritize digit-containing specs or known important textual specs
        priority_specs = [s for s in specs if re.search(r'\d',s) or "5g" in s.lower() or any(ckw in s.lower() for ckw in color_keywords)]
        other_specs = [s for s in specs if s not in priority_specs]

        for spec_list in [priority_specs, other_specs]:
            for spec_item in spec_list:
                spec_item_lower = spec_item.lower()
                # Avoid adding redundant parts if model already contains them
                already_in_model = any(p_spec in " ".join(search_parts).lower() for p_spec in spec_item_lower.split())
                # Avoid adding redundant parts if already added as a whole word
                if not already_in_model and spec_item_lower not in processed_specs_lower:
                    final_specs_to_add.append(spec_item)
                    processed_specs_lower.add(spec_item_lower)

        search_parts.extend(final_specs_to_add)

        # Remove duplicates while preserving order as much as possible
        final_search_parts_ordered = []
        seen_parts = set()
        for part in search_parts:
            part_lower = part.lower()
            if part_lower not in seen_parts:
                 is_sub_part_present = False
                 for sp in final_search_parts_ordered:
                     if part_lower in sp.lower() and len(part_lower) < len(sp):
                         is_sub_part_present = True
                         break
                 if not is_sub_part_present:
                    final_search_parts_ordered.append(part)
                    seen_parts.add(part_lower)

        search_query = ' '.join(final_search_parts_ordered[:8]).strip() # Limit total parts to avoid too long query (increased from 7)

        if not search_query: # Absolute fallback
            words = re.findall(r'\b\w+\b', lower_title)
            common_noise = {'and', 'with', 'for', 'the', 'new', 'os', 'windows', 'android', 'in', 'on', 'of', 'at', 'by', 'to', 'from', 'a', 'an', 'is', 'it', 'this', 'that', 'segment', '(', ')', ',', '&', '-'} # Added hyphen
            essential_words = [word for word in words if word not in common_noise and len(word) > 1 and not word.isdigit()]
            search_query = ' '.join(essential_words[:6]) # Increased from 5
            if not search_query and extracted_brand:
                search_query = extracted_brand

        logger.info(f"_clean_title_for_search: Original: '{title[:60]}...'. Cleaned Search Query: '{search_query}'")
        return search_query if search_query else title.lower() # Ensure it never returns empty

    def identify_platform_and_product_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        if "amazon." in url:
            match = re.search(r'/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})', url)
            return ("amazon", match.group(1) or match.group(2)) if match else (None, None)
        elif "flipkart.com" in url:
            # More robust Flipkart ID extraction
            match = re.search(r'/p/([^/?&]+)', url) or re.search(r'pid=([^&]+)', url)
            return ("flipkart", match.group(1)) if match else (None, None)
        elif "reliancedigital.in" in url:
            # More robust Reliance Digital ID extraction
            match = re.search(r'/(?:product|p)/([^/?&]+)', url) or re.search(r'sku=([^&]+)', url)
            return ("reliancedigital", match.group(1).split(",")[0]) if match else (None, None)
        return None, None

    def _get_amazon_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """Get product details from Amazon using Selenium."""
        try:
            if not self.driver:
                self._initialize_driver()

            logger.info(f"Fetching Amazon details for URL: {url}")

            # Add random delay before accessing the page
            time.sleep(random.uniform(2, 4))

            # Navigate to the page
            self.driver.get(url)

            # Wait for the page to load completely with increased timeout
            # Also wait for a key indicator element that suggests the main content is ready
            WebDriverWait(self.driver, 45).until( # Increased overall wait
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )

            # Additional wait for dynamic content and rendering
            time.sleep(random.uniform(5, 8)) # Increased post-load wait

            # Scroll the page to trigger lazy loading of images and content
            logger.debug("Scrolling page to trigger lazy loading...")
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_steps = 5
            for i in range(scroll_steps):
                self.driver.execute_script(f"window.scrollTo(0, (document.body.scrollHeight / {scroll_steps}) * {(i+1)});")
                time.sleep(random.uniform(1, 2))
            self.driver.execute_script("window.scrollTo(0, 0);") # Scroll back to top
            time.sleep(random.uniform(1, 2))

            # Check for potential anti-bot pages or errors
            page_source = self.driver.page_source
            if "captcha" in page_source.lower() or "unusual traffic" in page_source.lower() or "verify you are human" in page_source.lower() or "access to this page has been denied" in page_source.lower():
                 error_msg = "Blocked by Amazon anti-bot detection."
                 logger.warning(f"{error_msg} for URL: {url}")
                 return None, None, error_msg

            # Try to get the title first
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
                # Added more selectors
                "#titleSection #productTitle",
                "#title_feature_div #productTitle",
                "span.a-text-bold[id='productTitle']",
                "div#title span#productTitle",
                "h1 span#productTitle",
                "span#aiv-content-title" # For digital content
            ]

            logger.info("Attempting to extract title...")
            for selector in title_selectors:
                try:
                    # Wait for element with explicit timeout
                    title_element = WebDriverWait(self.driver, 10).until( # Reduced per-selector timeout
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_element and title_element.text.strip():
                        title = title_element.text.strip()
                        logger.info(f"Found title with selector {selector}: {title[:70]}...") # Increased log preview
                        break # Found title, no need to check other selectors
                except Exception as e:
                    logger.debug(f"Could not find title with selector {selector}: {str(e)}")
                    continue # Try next selector

            if not title:
                # Try JavaScript execution as fallback
                logger.info("Attempting title extraction using JavaScript fallback...")
                try:
                    title = self.driver.execute_script("""
                        return document.querySelector('#productTitle')?.textContent?.trim() ||
                               document.querySelector('h1#title')?.textContent?.trim() ||
                               document.querySelector('span#productTitle')?.textContent?.trim() ||
                               document.querySelector('h1.a-size-large')?.textContent?.trim() ||
                               document.title.split('|')[0]?.trim(); // Fallback to page title
                    """)
                    if title and title.lower() != 'amazon.in': # Avoid generic page title
                        logger.info(f"Found title using JavaScript: {title[:70]}...")
                    else:
                        title = None # Reset if generic
                except Exception as e:
                    logger.debug(f"JavaScript title extraction failed: {str(e)}")

                if not title:
                    title = "Unknown Product"
                    logger.warning(f"Could not find product title on Amazon page {url} using any method.")

            # Try multiple price selectors with different strategies
            price = None
            price_selectors = [
                # Main price selectors
                "span.a-price span.a-offscreen",
                "span.a-price-whole",
                "span.a-color-price",
                # Deal price selectors
                "span.a-price[data-a-color='price'] span.a-offscreen",
                "span.a-price[data-a-color='secondary'] span.a-offscreen",
                "span.a-price[data-a-color='base'] span.a-offscreen", # Added another color variant
                # Alternative price selectors
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                "#priceblock_saleprice",
                ".a-price .a-offscreen",
                ".a-price-whole",
                ".a-color-price",
                # Additional selectors for different price formats
                "div[data-cy='price-recipe'] span.a-price-whole",
                "span.priceToPay span.a-price-whole",
                "#apex_desktop_newAccordionRow span.a-price-whole",
                "span.a-price.aok-align-center span.a-offscreen",
                # New selectors observed on various pages
                "div[data-cy='price-block'] span.a-offscreen",
                "div[data-cy='price'] span.a-offscreen",
                "div[data-cy='price-block'] span.a-price-whole",
                "div[data-cy='price'] span.a-price-whole",
                "#corePriceDisplay_feature_div span.a-price-whole", # Specific section
                "#buybox span.a-price-whole", # Buy box price
                ".offer-price", ".selling-price", ".deal-price", # Common price class names
                "span[data-a-color='price'] span.a-text-price", # Strikethrough price sometimes has the actual price nearby
                "span.reinventPricePriceToPayMargin span.a-price-whole", # Another common structure
                "span[aria-label^='Current price'] span.a-offscreen", # ARIA label based price
                "div[id^='corePrice'] span.a-price-whole" # More generic core price
            ]

            logger.info("Attempting to extract price...")
            price_text_found = None
            for selector in price_selectors:
                try:
                    # Find all elements matching the selector
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.debug(f"Selector {selector} found {len(price_elements)} elements.")
                    # Iterate through found elements, prioritizing visible ones
                    for price_element in price_elements:
                        # Use WebDriverWait for visibility or presence with a short timeout per element check
                        try:
                             # Check for visibility or if it's an off-screen element
                            if price_element.is_displayed() or "a-offscreen" in price_element.get_attribute("class"):
                                price_text_found = price_element.get_attribute('textContent') or price_element.text
                                if price_text_found and price_text_found.strip():
                                     price_text_found = price_text_found.strip()
                                     logger.debug(f"Found potential price text '{price_text_found}' with selector {selector}.")
                                     # Attempt to clean and parse the price immediately
                                     cleaned_price = re.sub(r'[^\d.]', '', price_text_found.replace(',', '').replace('₹', ''))
                                     if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                                         price = float(cleaned_price)
                                         logger.info(f"Amazon found price: {price} using selector: {selector}")
                                         return title, price, None # Return immediately on finding a valid price
                                     else:
                                         logger.debug(f"Price text '{price_text_found}' is not a valid number after cleaning.")
                                else:
                                    logger.debug("Price element text was empty or whitespace.")
                            else:
                                logger.debug("Price element is not displayed and not off-screen.")
                        except Exception as elem_e:
                            logger.debug(f"Error processing price element with selector {selector}: {elem_e}")
                            continue # Continue to the next element if one fails

                except Exception as sel_e:
                    logger.debug(f"Could not find price with selector {selector}: {str(sel_e)}")
                    continue # Try next selector

            # If loop finishes without finding a price, try JavaScript fallback
            if not price:
                logger.info("Attempting price extraction using JavaScript fallback...")
                try:
                    price_text = self.driver.execute_script("""
                        return document.querySelector('span.a-price-whole')?.textContent?.trim() ||
                               document.querySelector('span.a-offscreen')?.textContent?.trim() ||
                               document.querySelector('span.a-color-price')?.textContent?.trim() ||
                               document.querySelector('#priceblock_dealprice')?.textContent?.trim() ||
                               document.querySelector('#priceblock_ourprice')?.textContent?.trim() ||
                               document.querySelector('.offer-price')?.textContent?.trim() ||
                               document.querySelector('.selling-price')?.textContent?.trim(); // Added more JS selectors
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
            logger.error(error_msg, exc_info=True) # Log with traceback
            return "Unknown Product", None, error_msg

    def _get_reliance_digital_details(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        logger.info(f"Fetching Reliance Digital details for URL: {url} using Selenium.")
        title = None
        price = None
        error_message = None

        if self.driver is None:
             logger.warning("_search_reliance_digital called without driver.")
             return None, None, "Selenium driver not initialized."

        try:
            self.driver.get(url)
            # Increased wait time
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(random.uniform(4, 7)) # Added random delay

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
                'div[class*="PlpProductName"]',
                'h1', 'h2' # More general
            ]
            for selector in title_selectors:
                try:
                    # Increased wait time for title element
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
                    if not title: title = "Unknown Product" # Final fallback
                    logger.warning(f"Could not find title on Reliance Digital page: {url}")


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
                'span[class*="price-block"]',
                '.final-price', '.offer-price', '.sell-price' # Added more
            ]
            price_text_found = None
            for selector in price_selectors:
                try:
                    # Increased wait time for price element
                    price_element = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    raw_text = price_element.get_attribute('textContent') or price_element.text
                    if raw_text and ('₹' in raw_text or 'Rs.' in raw_text or 'INR' in raw_text or re.search(r'\d', raw_text)):
                        price_text_found = raw_text.strip()
                        break
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
                            logger.info(f"Reliance Digital search found matching product price: {price}")
                            return str(price) # Return price as string
                        else:
                             logger.debug(f"Reliance Digital price text found \'{price_text_found}\' but not a valid number.")
                    else:
                         logger.debug(f"Reliance Digital price text found \'{price_text_found}\' but no regex pattern matched.")


            if price is None:
                logger.debug("Could not find price for a potential Reliance Digital search result.")
                # Continue to search other products even if price not found for one
                return "Not found" # Return "Not found" if no match found

        except Exception as e:
            logger.error(f"Error in Reliance Digital search for '{product_name}\': {str(e)}", exc_info=True)
            return "Search Error" # Return a specific error message

    def _product_matches(self, search_term: str, result_title: str, threshold=0.4) -> bool:
        if not search_term or not result_title:
            return False

        logger.debug(f"_product_matches: Comparing search_term='{search_term}' with result_title='{result_title}'")
        cleaned_search_words = set(re.findall(r'\b\w+\b', search_term.lower()))
        result_words = set(re.findall(r'\b\w+\b', result_title.lower()))

        logger.debug(f"_product_matches: Cleaned search words: {cleaned_search_words}")
        logger.debug(f"_product_matches: Result words: {result_words}")

        common_noise = {'and', 'with', 'for', 'the', 'new', 'in', 'on', 'of', 'at', 'by', 'to', 'from', 'a', 'an', 'is', 'it', 'this', 'that'}

        important_search_words = cleaned_search_words - common_noise

        logger.debug(f"_product_matches: Important search words: {important_search_words}")

        if not important_search_words:
            important_search_words = set(re.findall(r'\b\w+\b', search_term.lower())) - common_noise
            if not important_search_words: return False

        # --- Enhanced Matching Logic ---

        # 1. Brand Check (Critical)
        brands = ['whirlpool', 'lg', 'samsung', 'haier', 'godrej', 'bosch', 'panasonic', 'hitachi', 'voltas', 'blue star', 'poco', 'xiaomi', 'redmi', 'apple', 'oneplus', 'realme', 'oppo', 'vivo', 'nokia', 'motorola', 'google pixel', 'iqoo', 'infinix', 'tecno']
        search_brand_match = any(brand in important_search_words for brand in brands)
        result_brand_match = any(brand in result_words for brand in brands)

        if search_brand_match and not result_brand_match:
            logger.debug("_product_matches: Brand mismatch.")
            return False # Brands must match if present in search term

        # 2. Model Number/Key Identifiers Check (Crucial)
        # Look for alphanumeric patterns or specific product identifiers
        search_identifiers = set(re.findall(r'[a-z0-9]+', search_term.lower())) - common_noise
        result_identifiers = set(re.findall(r'[a-z0-9]+', result_title.lower())) - common_noise

        common_identifiers = search_identifiers.intersection(result_identifiers)
        if not common_identifiers and len(important_search_words) > 2: # If there are important words but no common alphanumeric identifiers
             logger.debug("_product_matches: No common alphanumeric identifiers found.")
             # Allow match based on other factors if identifiers are less critical for this product type
             pass # Continue to other checks

        # 3. Spec Check (Important)
        # Look for matches in RAM, Storage, Capacity, Star Rating, 5G
        search_specs = set(re.findall(r'\d+gb|\d+l|\d+star|5g', search_term.lower()))
        result_specs = set(re.findall(r'\d+gb|\d+l|\d+star|5g', result_title.lower()))
        common_specs = search_specs.intersection(result_specs)

        # 4. Keyword Similarity (General)
        common_important_words = important_search_words.intersection(result_words)
        keyword_score = sum(2 for word in common_important_words if re.search(r'\d', word) or len(word) > 3) # Boost for numbers and longer words
        keyword_score += sum(1 for word in common_important_words if not re.search(r'\d', word) and len(word) <= 3)

        # 5. Sequence Matcher Ratio (Fallback/Refinement)
        matcher = difflib.SequenceMatcher(None, search_term.lower(), result_title.lower())
        similarity_ratio = matcher.ratio()

        # --- Decision Logic ---

        # High confidence match if brand and at least one identifier/spec match
        if search_brand_match and result_brand_match and (common_identifiers or common_specs):
            logger.debug("_product_matches: High confidence match (brand + identifier/spec).")
            return True

        # Moderate confidence match if no brand in search, but good keyword overlap and similarity
        if not search_brand_match and keyword_score > 3 and similarity_ratio > 0.6:
             logger.debug("_product_matches: Moderate confidence match (keyword overlap + similarity).")
             return True

        # Lower confidence match based on a combined score (adjusted thresholds)
        combined_score = keyword_score * 2 + len(common_identifiers) * 3 + len(common_specs) * 2 + similarity_ratio * 10
        required_score = len(important_search_words) * 3 + (5 if search_brand_match else 0) # Dynamic required score

        logger.debug(f"Match check: Search='{search_term[:50]}...', Result='{result_title[:50]}...', Combined Score={combined_score:.2f}, Required Score={required_score:.2f}, Similarity={similarity_ratio:.2f}, Keyword Score={keyword_score}, Common Identifiers={len(common_identifiers)}, Common Specs={len(common_specs)}")

        return combined_score >= required_score

    def _search_amazon(self, search_term: str) -> Optional[str]:
        if not self.driver or not search_term:
            logger.warning("_search_amazon called without driver or search term.")
            return "WebDriver/SearchTerm Error"
        search_url = f"https://www.amazon.in/s?k={quote_plus(search_term)}"
        logger.info(f"_search_amazon: URL: {search_url} using Selenium.")
        try:
            self.driver.get(search_url)
            WebDriverWait(self.driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')))
            time.sleep(random.uniform(3, 5)) # Added random delay

            products = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
            if not products:
                # Fallback selectors
                products = self.driver.find_elements(By.CSS_SELECTOR, 'div.s-result-item[data-asin], div[data-asin].sg-col-20-of-24, [data-component-type="s-search-result"] div.a-section')


            logger.info(f"Amazon search found {len(products)} potential items.")

            # Check first 10 products (increased from 7)
            for product_element in products[:10]:
                product_title, product_price = None, None
                try:
                    # More robust title selectors
                    title_el = product_element.find_element(By.CSS_SELECTOR, 'h2 a span, span.a-size-medium.a-color-base.a-text-normal, .a-text-normal, a.a-link-normal.a-text-normal')
                    product_title = title_el.text.strip()
                except:
                    logger.debug("Could not find title for a potential Amazon search result.")
                    continue # Skip this product if title not found

                # Use _product_matches for robust checking
                if self._product_matches(search_term, product_title, threshold=0.5): # Keep threshold for search results
                    logger.info(f"Amazon Match: '{product_title[:50]}...' with search term '{search_term[:50]}...'")
                    try:
                        # More robust price selectors
                        price_el = product_element.find_element(By.CSS_SELECTOR, 'span.a-price-whole, span.a-offscreen, .a-price-current span.a-price-whole, .a-spacing-mini .a-price-whole')
                        price_text = price_el.text.strip()
                        cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', ''))
                        if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                            product_price = float(cleaned_price)
                            logger.info(f"Amazon search found matching product price: {product_price}")
                            return str(product_price) # Return price as string
                    except Exception as e_price:
                        logger.debug(f"Could not get price for matched Amazon item: {e_price}")
                        # Continue searching other products even if price extraction fails for one
                        continue
                else:
                    logger.debug(f"Amazon No Match: '{product_title[:50]}...' vs '{search_term[:50]}...'")

        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}", exc_info=True)
            return "Search Error" # Return a specific error message
        return "Not found" # Return "Not found" if no match is found after checking relevant products

    def _search_reliance_digital(self, product_name: str, amazon_url: str = None) -> str:
        """Search for product on Reliance Digital and return price."""
        if not self.driver:
             logger.warning("_search_reliance_digital called without driver.")
             return "WebDriver Error"

        try:
            # Extract key features from product name for tailored search queries
            features = {
                'brand': None,
                'model': None,
                'capacity': None,
                'star_rating': None,
                'color': None
            }

            # Extract brand
            brands = ['whirlpool', 'lg', 'samsung', 'haier', 'godrej', 'bosch', 'panasonic', 'hitachi', 'voltas', 'blue star',
                      'bajaj', 'havells', 'orient', 'usha', 'crompton',
                      'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple',
                      'canon', 'nikon', 'sony', 'fujifilm',
                      'boat', 'jbl', 'sony', 'bose', 'sennheiser',
                      'mi', 'realme', 'oneplus', 'oppo', 'vivo', 'infinix', 'tecno', 'motorola', 'samsung', 'apple', 'google pixel', 'iqoo', 'infinix', 'tecno',
                      'fitbit', 'garmin', 'apple', 'samsung', 'xiaomi'
                     ]
            product_name_lower = product_name.lower()
            for brand in brands:
                if re.search(r'\b' + re.escape(brand) + r'\b', product_name_lower):
                    features['brand'] = brand
                    break

            # Extract model number (improved patterns)
            model_patterns = [
                r'(\b[a-zA-Z0-9]{2,}[-\/]?\s*[a-zA-Z0-9]{2,}\b(?:[-\/]?\s*[a-zA-Z0-9]{1,3})?)', # e.g., "205 WDE CLS 2S", "HRD-2203BS"
                r'(\b[a-zA-Z]+\d+\b)', # e.g., "GalaxyS23"
                r'(\b\d+[a-zA-Z]+\b)', # e.g., "14Pro"
                r'(\b[a-zA-Z]{2,}\d{2,}\b)', # e.g., "iPhone14"
                r'(\b\d{2,}[a-zA-Z]{2,}\b)', # e.g., "S23Ultra"
            ]
            for pattern in model_patterns:
                model_match = re.search(pattern, product_name, re.IGNORECASE)
                if model_match:
                    features['model'] = model_match.group(1).strip()
                    break

            # Extract capacity
            capacity_match = re.search(r'(\d+)\s*L(?=\s|$)|\b(\d+)\s*litre', product_name, re.IGNORECASE)
            if capacity_match:
                features['capacity'] = f"{capacity_match.group(1) or capacity_match.group(2)}L"

            # Extract star rating
            star_match = re.search(r'(\d+)\s*Star', product_name, re.IGNORECASE)
            if star_match:
                features['star_rating'] = f"{star_match.group(1)} Star"

            # Extract color
            color_keywords = ['black', 'white', 'blue', 'red', 'green', 'silver', 'gold', 'gray', 'grey', 'purple', 'pink', 'orange', 'yellow', 'brown', 'bronze', 'aqua', 'marine', 'sky', 'midnight', 'space', 'rose', 'graphite', 'sierra', 'alpine', 'wine', 'solid']
            color_match = re.search(r'\b(' + '|'.join(color_keywords) + r')\b', product_name, re.IGNORECASE)
            if color_match:
                features['color'] = color_match.group(1).capitalize() # Capitalize the matched color

            # Construct search queries
            search_queries = []

            # Query 1: Brand + Model + Capacity + Star Rating (if available)
            if features['brand'] and features['model']:
                 query = f"{features['brand']} {features['model']}"
                 if features['capacity']: query += f" {features['capacity']}"
                 if features['star_rating']: query += f" {features['star_rating']}"
                 if query not in search_queries: search_queries.append(query)

            # Query 2: Brand + Capacity + Star Rating (if available)
            if features['brand'] and features['capacity']:
                 query = f"{features['brand']} {features['capacity']}"
                 if features['star_rating']: query += f" {features['star_rating']}"
                 if query not in search_queries: search_queries.append(query)

            # Query 3: Brand + Model + Color (if available)
            if features['brand'] and features['model'] and features['color']:
                 query = f"{features['brand']} {features['model']} {features['color']}"
                 if query not in search_queries: search_queries.append(query)

            # Query 4: Full product name (as a fallback)
            if product_name not in search_queries: search_queries.append(product_name)

            # Try each search query
            for search_query in search_queries:
                try:
                    time.sleep(random.uniform(3, 6)) # Add random delay

                    search_url = f"https://www.reliancedigital.in/search?q={quote_plus(search_query)}"
                    logger.info(f"Trying Reliance Digital URL: {search_url} using Selenium.")

                    self.driver.get(search_url)
                    WebDriverWait(self.driver, 45).until( # Increased wait time
                        lambda driver: driver.execute_script('return document.readyState') == 'complete'
                    )
                    time.sleep(random.uniform(4, 7)) # Add random delay after load

                    # Try different selectors for product elements
                    product_selectors = [
                        'div[class*="productCard"]',
                        'div[class*="product-item"]',
                        'div[class*="product-grid"]',
                        'div[class*="product-list"]',
                        'div[class*="product"]',
                        'div[class*="item"]',
                        '.product_listing_RESPONSIVE .ProductCard', # Specific class
                        '.plp-product-list .ProductCard__Wrapper' # Specific class
                    ]

                    products = []
                    try:
                         # Wait for at least one product element
                        any_product_present = WebDriverWait(self.driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ", ".join(product_selectors)))
                        )
                        # Find all potential product elements after waiting
                        for selector in product_selectors:
                             elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                             products.extend(elements)
                         # Remove duplicates
                        products = list(dict.fromkeys(products))
                    except Exception as e:
                        logger.warning(f"Timeout waiting for Reliance Digital product elements or error finding them: {e}")
                        # Fallback: try finding visible divs with significant text
                        try:
                            all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                            products = [d for d in all_divs if d.is_displayed() and d.text and len(d.text) > 50]
                            logger.info(f"Reliance Digital fallback found {len(products)} visible divs.")
                        except:
                             pass # If fallback fails, products remains empty

                    if not products:
                        logger.warning(f"No product elements found after trying selectors and fallback for query: {search_query}")
                        continue # Try next query if no products found

                    logger.info(f"Found {len(products)} potential Reliance Digital products.")

                    # Check first 10 products (increased from 5)
                    for product in products[:10]:
                        try:
                            # Try different selectors for product name
                            name_selectors = [
                                'div[class*="product-name"]',
                                'div[class*="product-title"]',
                                'h1', 'h2', 'h3',
                                'a[title]',
                                'div[class*="title"]',
                                '.ProductCard__Name', '.ProductItem__Name', '.plp-product-name' # Specific classes
                            ]

                            product_name_element = None
                            for selector in name_selectors:
                                try:
                                    # Increased wait time for name element within a product card
                                    element = WebDriverWait(product, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                    )
                                    if element and element.text.strip():
                                         product_name_element = element
                                         break
                                except:
                                    continue

                            if not product_name_element:
                                logger.debug("Could not find name for a potential Reliance Digital search result.")
                                continue

                            found_name = product_name_element.text.strip()
                            logger.debug(f"Potential Reliance Digital product name: {found_name[:50]}...")

                            # Use _product_matches for robust checking
                            if not self._product_matches(product_name, found_name, threshold=0.6): # Use original product name for matching
                                 logger.debug(f"Reliance Digital product title \'{found_name[:50]}...\' does not match search query \'{product_name[:50]}...\'")
                                 continue # Skip if not a good match

                            logger.info(f"Potential Reliance Digital match found: \'{found_name[:50]}...\'")

                            # Try different selectors for price
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
                                'span[class*="price-block"]',
                                '.ProductCard__Price', '.ProductItem__Price', '.plp-product-price .price' # Specific classes
                            ]

                            price_text_found = None
                            for selector in price_selectors:
                                try:
                                    # Increased wait time for price element within a product card
                                    element = WebDriverWait(product, 10).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                    )
                                    raw_text = element.get_attribute('textContent') or element.text
                                    if raw_text and ('₹' in raw_text or 'Rs.' in raw_text or 'INR' in raw_text or re.search(r'\d', raw_text)):
                                        price_text_found = raw_text.strip()
                                        break
                                except:
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
                                            logger.info(f"Reliance Digital search found matching product price: {price}")
                                            return str(price) # Return price as string
                                        else:
                                             logger.debug(f"Reliance Digital price text found \'{price_text_found}\' but not a valid number.")
                                    else:
                                         logger.debug(f"Reliance Digital price text found \'{price_text_found}\' but no regex pattern matched.")

                            if price is None:
                                logger.debug("Could not find price for a potential Reliance Digital search result.")
                                # Continue to search other products even if price not found for one
                                continue

                        except Exception as e: # Catch any error during processing a single product
                            logger.debug(f"Error processing Reliance Digital product element: {str(e)}", exc_info=True)
                            continue # Continue to the next product if one fails

                except Exception as e: # Catch any error during processing this search query
                    logger.error(f"Error during Reliance Digital search with query '{search_query}': {str(e)}", exc_info=True)
                    continue # Try the next search query

            logger.warning(f"No matching product and price found on Reliance Digital after trying all search queries for '{product_name}'")
            return "Not found" # Return "Not found" if no match found

        except Exception as e:
            logger.error(f"Error in Reliance Digital search for '{product_name}': {str(e)}", exc_info=True)
            return "Search Error" # Return a specific error message

    def _scrape_with_playwright(self, url: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """Scrape a URL using Playwright, handling dynamic content and potential anti-bot measures."""
        title = None
        price = None
        error_message = None
        browser = None
        playwright = None

        logger.info(f"Scraping with Playwright: {url}")

        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
                executable_path=None  # Let Playwright handle the browser path
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=False,
                ignore_https_errors=True
            )
            page = context.new_page()

            page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })

            # Navigate to the page with increased timeout
            page.goto(url, wait_until='networkidle', timeout=120000)
            time.sleep(random.uniform(5, 8))

            # Handle Flipkart login popup if present
            try:
                close_button = page.wait_for_selector('button._2KpZ6l._2doB4z, span[role="button"]', timeout=5000)
                if close_button:
                    close_button.click()
                    logger.info("Closed Flipkart login popup")
                    time.sleep(1)
            except:
                pass

            # Scroll multiple times to load dynamic content
            for i in range(5):
                page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/5});")
                time.sleep(random.uniform(2, 3))

            # Extract title with more selectors
            title_selectors = [
                'span.B_NuCI',
                'h1.yhB1nd',
                'div[class*="_title"]',
                'span[class*="_title"]',
                'h1[class*="product-title"]',
                'div[class*="product-title"]',
                'div[class*="_3AsjWm"] span',
                'a[class*="s1Q9rs"]',
                'div._4rR01T',  # Flipkart search result title
                'a.s1Q9rs',     # Flipkart search result title alternative
                'div.KzDlHZ',   # Flipkart search result title alternative
                'div._2kHMtA a', # Another search result title
                'div._1AtVbE a', # Another search result title
                'title'
            ]

            for selector in title_selectors:
                try:
                    title_element = page.wait_for_selector(selector, state='visible', timeout=5000)
                    if title_element:
                        title = title_element.text_content()
                        if title:
                            title = title.strip()
                            logger.info(f"Playwright found title with selector {selector}: {title[:50]}...")
                            break
                except Exception as e:
                    continue

            # Extract price with more selectors
            price_selectors = [
                'div._30jeq3._16Jk6d',
                'div._30jeq3',
                'div.Nx9bqj._3_XqSL',
                'div[class*="_price"]',
                'span[class*="_price"]',
                'div[class*="price"]',
                'span[class*="price"]',
                'div[class*="Price"]',
                'span[class*="Price"]',
                'div._1_WHN1',  # Flipkart search result price
                'div._16Jk6d',  # Flipkart search result price alternative
                'div._25b18c',  # Flipkart search result price alternative
                'div._3qQ9m1',  # Flipkart search result price alternative
                'div._2kHMtA div._1_WHN1', # Nested price selector
                'div._1AtVbE div._1_WHN1'  # Another nested price selector
            ]

            for selector in price_selectors:
                try:
                    price_element = page.wait_for_selector(selector, state='visible', timeout=5000)
                    if price_element:
                        price_text = price_element.text_content()
                        if price_text:
                            price_text = price_text.strip()
                            cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', ''))
                            if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                                price = float(cleaned_price)
                                logger.info(f"Playwright found price: {price}")
                                break
                except Exception as e:
                    continue

            # If we're on a search page and haven't found a price, try to click the first product
            if 'flipkart.com/search' in url and not price:
                try:
                    # Try different selectors for product links
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
                            product_link = page.wait_for_selector(selector, timeout=5000)
                            if product_link:
                                product_link.click()
                                page.wait_for_load_state('networkidle')
                                time.sleep(random.uniform(3, 5))
                                
                                # Try to get price on the product page
                                for price_selector in price_selectors:
                                    try:
                                        price_element = page.wait_for_selector(price_selector, timeout=5000)
                                        if price_element:
                                            price_text = price_element.text_content()
                                            if price_text:
                                                price_text = price_text.strip()
                                                cleaned_price = re.sub(r'[^\d.]', '', price_text.replace(',', '').replace('₹', ''))
                                                if cleaned_price and cleaned_price.replace('.', '', 1).isdigit():
                                                    price = float(cleaned_price)
                                                    logger.info(f"Playwright found price after clicking product: {price}")
                                                    break
                                    except:
                                        continue
                                
                                if price:
                                    break
                        except:
                            continue
                except Exception as e:
                    logger.error(f"Error clicking product link: {str(e)}")

        except Exception as e:
            error_message = f"Playwright error: {str(e)}"
            logger.error(error_message)
        finally:
            if browser:
                browser.close()
                logger.info("Playwright browser closed.")
            if playwright:
                playwright.stop()
                logger.info("Playwright stopped.")

        if not title:
            title = "Unknown Product (Playwright)"
        if not price and not error_message:
            error_message = "Price not found"

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
                    except: 
                        continue

                if not title:
                    try:
                        title = self.driver.title.split("|")[0].strip()
                        logger.info(f"Flipkart title (fallback from page title): {title[:50]}...")
                    except: 
                        pass

                price_selectors = ['div._30jeq3._16Jk6d', 'div._30jeq3', 'div.Nx9bqj._3_XqSL']
                price_text_found = None
                for selector in price_selectors:
                    try:
                        price_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if price_element and price_element.text.strip():
                            price_text_found = price_element.text.strip()
                            break
                    except: 
                        continue

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

            # Try to find product listings and extract directly
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
                    # Wait for at least one listing element to be present
                    WebDriverWait(self.driver, 15).until(
                         EC.presence_of_element_located((By.CSS_SELECTOR, listing_selector)))

                    product_listings = self.driver.find_elements(By.CSS_SELECTOR, listing_selector)
                    logger.info(f"Found {len(product_listings)} potential product listings with selector {listing_selector}.")

                    if not product_listings: continue

                    # Iterate through listings and try to extract title and price
                    for product_element in product_listings:
                        listing_title, listing_price = None, None

                        # Try to extract title from listing
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

                        # Use _product_matches to check relevance
                        if not self._product_matches(search_term, listing_title, threshold=0.5): # Use threshold for search results
                            logger.debug(f"Listing title '{listing_title[:50]}...' does not match search term '{search_term[:50]}...'")
                            continue # Skip if not a good match

                        logger.info(f"Found potentially matching listing: '{listing_title[:50]}...'")

                        # Try to extract price from listing
                        price_selectors = [
                            # Common price selectors in listings
                            'div._30jeq3._1_WHN1',
                            'div._30jeq3',
                            'div._1_WHN1',
                            'div.Nx9bqj._3_XqSL',
                            'div._16Jk6d',
                            'div._25b18c',
                            'div._3qQ9m1',
                            'div[class*="product-price"] div',
                            'div[class*="Price"] div',
                            # More specific/nested selectors for listings
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
                            # More general selectors within a listing that might contain price
                            'span:contains("₹")',
                            'div:contains("₹")',
                            'span:has(> div._30jeq3)',
                            'div:has(> span._30jeq3)',
                            '.\_30jeq3',
                            '.\_1_WHN1',
                            '.\_16Jk6d',
                            '.\_25b18c',
                            '.\_3qQ9m1',
                            '[class*="price"]:not([class*="old"]):not([class*="strike"])',
                            '[class*="Price"]:not([class*="old"]):not([class*="strike"])',
                            # Additional specific selectors based on common Flipkart listing structure
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
                                        # Found a relevant price in a listing, return immediately
                                        return listing_title, listing_price, None
                                    else:
                                         logger.debug(f"Cleaned price from listing '{cleaned_price}' is not a valid number.")
                                break # Stop trying price selectors for this listing if one is found
                            except:
                                continue
                        
                        if not listing_price:
                             logger.debug("Could not find price in matching listing.")

                except Exception as e: # Catch any error during processing this listing selector
                    logger.debug(f"Error with listing selector {listing_selector}: {e}")
                    continue # Try the next listing selector

            # If no price found in listings, fallback to clicking the first product link
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
                    # Wait for at least one product link to be clickable
                    WebDriverWait(self.driver, 15).until(
                         EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

                    product_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if product_links:
                        # Click the first link (assuming it's the most relevant if listings failed)
                        logger.info(f"Clicking first product link with selector {selector}.")
                        product_links[0].click()
                        time.sleep(random.uniform(3, 5))

                        # Now get the price from the product page
                        return self._get_flipkart_details(self.driver.current_url)
                except Exception as e:
                    logger.debug(f"Error clicking product link with selector {selector}: {e}")
                    continue # Try next link selector

            logger.warning(f"No matching product or clickable link found on Flipkart after search for '{search_term}'")
            return None, None, "Product or price not found"

        except Exception as e:
            logger.error(f"Error searching Flipkart: {str(e)}", exc_info=True)
            return None, None, f"Search error: {str(e)[:50]}"

# Create a singleton instance of PriceExtractor
# The main application logic should handle awaiting the async methods
price_extractor = PriceExtractor()

if __name__ == "__main__":
    # This part needs to be async to run the async methods
    async def main():
        url = input("Enter the product URL (Amazon, Flipkart, or Reliance Digital): ").strip()

        if not url:
            print("No URL provided. Exiting.")
            exit(1)

        print(f"\n{'='*50}")
        print(f"Analyzing URL: {url}")

        try:
            # Await the async method
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
                    pass # Keep price_display as is if not a valid number

                print(f"{platform_name:<20}: {price_display}")

        except KeyboardInterrupt:
            print("\nScript interrupted by user. Cleaning up...")
        except Exception as e:
            logger.error(f"An critical error occurred during main execution: {str(e)}", exc_info=True)
            print(f"An critical error occurred: {str(e)}")
        finally:
            # Ensure Selenium driver is closed in the main execution block as well
            # Playwright is closed within _scrape_with_playwright
            if price_extractor:
                try:
                    price_extractor.cleanup()
                except Exception as e:
                    logger.error(f"Error during final Selenium cleanup: {str(e)}")
                    print(f"Error during final Selenium cleanup: {str(e)}")
        print(f"{'='*50}\n")

    # Run the async main function
    asyncio.run(main())