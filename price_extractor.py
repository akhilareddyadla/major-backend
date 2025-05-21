from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import re
import time
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': UserAgent().random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Initialize Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'user-agent={UserAgent().random}')
        
        # Initialize Chrome driver
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def __del__(self):
        """Cleanup when the object is destroyed"""
        if hasattr(self, 'driver'):
            self.driver.quit()
        
    def get_product_details(self, url: str) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Get product details including price and title from the given URL
        """
        try:
            # Identify the platform and potentially product ID
            # Although product ID is extracted, we primarily rely on title for cross-platform search
            initial_platform, initial_product_id = self.identify_platform_and_product_id(url)

            if not initial_platform:
                logger.error(f"Unsupported or invalid website URL: {url}")
                return {'amazon': 'Invalid URL', 'flipkart': 'Invalid URL', 'reliancedigital': 'Invalid URL'}

            # Fetch details from the initial URL to get the title and price
            initial_title = None
            initial_price = None

            if initial_platform == 'amazon':
                initial_title, initial_price = self._get_amazon_details(url)
            elif initial_platform == 'flipkart':
                initial_title, initial_price = self._get_flipkart_details(url)
            elif initial_platform == 'reliancedigital':
                initial_title, initial_price = self._get_reliance_digital_details(url)

            if not initial_title:
                logger.error(f"Could not fetch product title from initial URL: {url}")
                # Attempt to get title from other platforms if initial fetch failed
                if initial_platform != 'amazon':
                     amazon_search_price = self._search_amazon(product_title=url) # Using URL as a fallback search term
                     if amazon_search_price:
                         initial_title = f"Product found on Amazon search (from {initial_platform} URL)"
                if initial_platform != 'flipkart' and not initial_title:
                     flipkart_search_price = self._search_flipkart(product_title=url) # Using URL as a fallback search term
                     if flipkart_search_price:
                         initial_title = f"Product found on Flipkart search (from {initial_platform} URL)"
                if initial_platform != 'reliancedigital' and not initial_title:
                     reliance_digital_search_price = self._search_reliance_digital(product_title=url) # Using URL as a fallback search term
                     if reliance_digital_search_price:
                         initial_title = f"Product found on Reliance Digital search (from {initial_platform} URL)"

                if not initial_title:
                    logger.error("Failed to determine product title from initial URL or cross-platform search.")
                    return {'amazon': 'Not found', 'flipkart': 'Not found', 'reliancedigital': 'Not found'}

            # Now, search for the product on the other two platforms using the fetched title
            prices = {
                'amazon': initial_price if initial_platform == 'amazon' else self._search_amazon(product_title=initial_title),
                'flipkart': initial_price if initial_platform == 'flipkart' else self._search_flipkart(product_title=initial_title),
                'reliancedigital': initial_price if initial_platform == 'reliancedigital' else self._search_reliance_digital(product_title=initial_title)
            }

            # Format the results
            formatted_results = {}
            for platform, price in prices.items():
                if price is not None:
                    formatted_results[platform] = price
                else:
                    formatted_results[platform] = 'Not found'

            return formatted_results

        except Exception as e:
            logger.error(f"An error occurred while processing URL {url}: {e}")
            return {'amazon': 'Error', 'flipkart': 'Error', 'reliancedigital': 'Error'}

    def _get_amazon_details(self, url: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract title and price from Amazon using Selenium
        """
        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Get title
            title = None
            title_selectors = [
                '#productTitle',
                'h1#title',
                'span#productTitle',
                'h1.a-size-large'
            ]
            
            for selector in title_selectors:
                try:
                    title_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    title = title_element.text.strip()
                    break
                except:
                    continue
            
            # Get price
            price = None
            price_selectors = [
                'span.a-price-whole',
                'span.a-offscreen',
                'span.a-price',
                '#priceblock_dealprice',
                '#priceblock_ourprice'
            ]
            
            for selector in price_selectors:
                try:
                    price_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    price_text = price_element.text.strip()
                    price = float(re.sub(r'[^\d.]', '', price_text))
                    break
                except:
                    continue
            
            return title, price
        except Exception as e:
            logger.error(f"Error extracting Amazon details: {str(e)}")
            return None, None

    def _get_flipkart_details(self, url: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract title and price from Flipkart
        """
        try:
            # Use the class's requests session
            response = self.session.get(url)
            response.raise_for_status() # Raise an exception for bad status codes

            soup = BeautifulSoup(response.content, 'html.parser')

            # This is a common class for price on Flipkart as of late 2023
            price_element = soup.select_one('div._30jeq3._16Jk6d')
            
            price = None
            if price_element:
                price_text = price_element.text.strip()
                # Clean up the price string (remove currency symbols, commas)
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                try:
                    price = float(cleaned_price)
                except ValueError:
                    logger.error(f"Could not convert Flipkart price to float: {cleaned_price}")
                    price = None
            else:
                 logger.warning("Flipkart price element not found")
                 price = None

            # Get title - Reusing existing logic from original _get_flipkart_details
            title = None
            title_element = soup.select_one('span.B_NuCI')
            if title_element:
                title = title_element.text.strip()
            else:
                logger.warning("Flipkart title element not found")
                title = None

            return title, price

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Flipkart page: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing Flipkart page: {e}")
            return None, None

    def _get_reliance_digital_details(self, url: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract title and price from Reliance Digital
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes

            soup = BeautifulSoup(response.content, 'html.parser')

            # Selector for the product title
            title_element = soup.select_one('h1')
            title = title_element.text.strip() if title_element else None
            if not title:
                logger.warning(f"Reliance Digital title element not found for {url}")

            # Selector for the price (based on inspection of a product page)
            # This selector might need adjustment if the website structure changes
            price_element = soup.select_one('span.Amount-sc-1gl24l-0')

            price = None
            if price_element:
                price_text = price_element.text.strip()
                # Clean up the price string (remove currency symbols, commas)
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                try:
                    price = float(cleaned_price)
                except ValueError:
                    logger.error(f"Could not convert Reliance Digital price to float: {cleaned_price}")
                    price = None
            else:
                logger.warning(f"Reliance Digital price element not found for {url}")
                price = None

            return title, price

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Reliance Digital page {url}: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing Reliance Digital page {url}: {e}")
            return None, None

    def _search_amazon(self, title: str) -> Dict[str, Optional[float]]:
        """
        Search for product on Amazon using Selenium
        """
        if not title:
            return {'price': None, 'title': None}
        
        try:
            # Clean the title for better search results
            search_title = re.sub(r'[^\w\s]', ' ', title)
            search_title = ' '.join(search_title.split()[:5])  # Use first 5 words
            
            search_url = f"https://www.amazon.in/s?k={quote_plus(search_title)}"
            self.driver.get(search_url)
            time.sleep(3)  # Wait for page to load
            
            # Get first product result
            try:
                product = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
                )
                product_title = product.find_element(By.CSS_SELECTOR, 'h2 a span')
                price_element = product.find_element(By.CSS_SELECTOR, 'span.a-price-whole')
                
                return {
                    'price': float(re.sub(r'[^\d.]', '', price_element.text.strip())),
                    'title': product_title.text.strip()
                }
            except:
                return {'price': None, 'title': None}
            
        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}")
            return {'price': None, 'title': None}

    def _search_flipkart(self, title: str) -> Dict[str, Optional[float]]:
        """
        Search for product on Flipkart using Selenium
        """
        if not title:
            return {'price': None, 'title': None}
        
        try:
            # Clean the title for better search results
            search_title = re.sub(r'[^\w\s]', ' ', title)
            search_title = ' '.join(search_title.split()[:5])  # Use first 5 words
            
            search_url = f"https://www.flipkart.com/search?q={quote_plus(search_title)}"
            self.driver.get(search_url)
            time.sleep(3)  # Wait for page to load
            
            # Get first product result
            try:
                product = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div._1AtVbE'))
                )
                product_title = product.find_element(By.CSS_SELECTOR, 'div._4rR01T')
                price_element = product.find_element(By.CSS_SELECTOR, 'div._30jeq3')
                
                return {
                    'price': float(re.sub(r'[^\d.]', '', price_element.text.strip())),
                    'title': product_title.text.strip()
                }
            except:
                return {'price': None, 'title': None}
            
        except Exception as e:
            logger.error(f"Error searching Flipkart: {str(e)}")
            return {'price': None, 'title': None}

    def _search_reliance_digital(self, product_title: str) -> Optional[float]:
        """
        Searches Reliance Digital for a product and returns its price.
        """
        search_url = f"https://www.reliancedigital.in/search?q={requests.utils.quote(product_title)}"
        logger.info(f"Searching Reliance Digital for '{product_title}' at {search_url}")

        try:
            response = self.session.get(search_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # *** Placeholder selectors - requires manual inspection of search results page ***
            # Assuming product items are in divs with class 'product-item'
            product_items = soup.select('div.product-item')

            for item in product_items:
                # Assuming title is in an h3 or h4 within the item
                title_element = item.select_one('h3, h4')
                item_title = title_element.text.strip() if title_element else ''

                # Basic title matching (can be improved)
                if product_title.lower() in item_title.lower():
                    # Assuming price is in a span or div with a price-related class
                    price_element = item.select_one('span.Amount-sc-1gl24l-0, div.price') # Reusing price class from product page, adding a generic 'div.price'
                    if price_element:
                        price_text = price_element.text.strip()
                        cleaned_price = re.sub(r'[^\d.]', '', price_text)
                        try:
                            price = float(cleaned_price)
                            logger.info(f"Found matching product '{item_title}' with price {price} on Reliance Digital search.")
                            return price
                        except ValueError:
                            logger.warning(f"Could not convert Reliance Digital search result price to float: {cleaned_price}")

            logger.info(f"No matching product found on Reliance Digital search for '{product_title}'")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Reliance Digital search page {search_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Reliance Digital search page {search_url}: {e}")
            return None

    def identify_platform_and_product_id(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Identifies the e-commerce platform and extracts the product ID from a given URL.
        """
        if "amazon." in url:
            # Logic to extract Amazon product ID (ASIN)
            # Example: https://www.amazon.in/dp/B0CDY53B3Y or https://www.amazon.in/Haier-Direct-Refrigerator-HRD-2203BS-Brushline/dp/B08KH7VF4Q
            match = re.search(r'/dp/([A-Z0-9]{10})', url)
            if match:
                return "amazon", match.group(1)
        elif "flipkart.com" in url:
            # Logic to extract Flipkart product ID
            # Example: https://www.flipkart.com/product/p/itme?pid=MOBGPFV63J7G96QW
            match = re.search(r'pid=([^&]+)', url)
            if match:
                return "flipkart", match.group(1)
        elif "reliancedigital.in" in url:
            # Logic to extract Reliance Digital product ID
            # Example: https://www.reliancedigital.in/product-category/product-name/p/product-id
            match = re.search(r'/p/([^/]+)$', url)
            if match:
                return "reliance_digital", match.group(1)
        # Remove Meesho identification
        # elif "meesho.com" in url:
        #     # Logic to extract Meesho product ID
        #     # Example: https://www.meesho.com/stylish-urban-shirts/p/123456789
        #     import re
        #     match = re.search(r'/p/(\d+)', url)
        #     if match:
        #          return "meesho", match.group(1)
        return None, None

# Create a singleton instance
price_extractor = PriceExtractor()

# Example usage
if __name__ == "__main__":
    test_urls = [
        "https://www.amazon.in/Sennheiser-Momentum-Wireless-Headphones-Designed/dp/B0CCRZPKR1",
        # "https://www.flipkart.com/product/p/itm123", # Commenting out example URLs that won't work without real product IDs
        # "https://www.meesho.com/product/123"
    ]
    
    # Add example usage for Flipkart and Meesho with real URLs if available for testing
    # For demonstration, let's add a placeholder
    print("\nNote: Add real Flipkart and Reliance Digital URLs to test the extraction.")
    
    for url in test_urls:
        print(f"\nAnalyzing URL: {url}")
        results = price_extractor.get_product_details(url)
        
        for platform, price in results.items():
            print(f"\n{platform.replace('reliancedigital', 'Reliance Digital').upper()}:")
            # Check if price is a number before formatting
            price_display = f"₹{price}" if isinstance(price, (int, float)) else price
            print(f"Price: {price_display}")
        print("\n" + "="*50) 