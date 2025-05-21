from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import logging
import re
import random
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PriceComparison:
    def __init__(self):
        # Initialize Chrome options
        self.chrome_options = Options()
        # Remove headless mode to avoid detection
        # self.chrome_options.add_argument('--headless=new')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--enable-unsafe-swiftshader')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set a realistic user agent
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.chrome_options.add_argument(f'user-agent={self.user_agent}')

    def _setup_driver(self):
        """Initialize and setup the Chrome driver"""
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.user_agent})
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 10
                });
            '''
        })
        return driver

    def _clean_title(self, title):
        """Clean the product title for searching"""
        # Remove special characters and extra spaces
        title = re.sub(r'[^\w\s]', ' ', title)
        # Remove extra spaces
        title = ' '.join(title.split())
        # Remove common words that might interfere with search
        common_words = ['with', 'and', 'for', 'the', 'in', 'on', 'at', 'to', 'of', 'a', 'an']
        words = [word for word in title.split() if word.lower() not in common_words]
        # Take first 7 words for better search results
        return ' '.join(words[:7])

    def get_product_details(self, url):
        """Get product details from the source URL"""
        driver = self._setup_driver()
        try:
            logger.info(f"Accessing source URL: {url}")
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            title = None
            price = None
            source = None

            if 'amazon.' in url.lower():
                source = 'Amazon'
                # Get title using JavaScript
                title = driver.execute_script("""
                    return document.querySelector('#productTitle')?.textContent?.trim() ||
                           document.querySelector('h1#title')?.textContent?.trim() ||
                           document.querySelector('span#productTitle')?.textContent?.trim() ||
                           document.querySelector('h1.a-size-large')?.textContent?.trim();
                """)
                
                # Get price using JavaScript
                price_text = driver.execute_script("""
                    return document.querySelector('span.a-price-whole')?.textContent?.trim() ||
                           document.querySelector('span.a-offscreen')?.textContent?.trim() ||
                           document.querySelector('span.a-price')?.textContent?.trim() ||
                           document.querySelector('#priceblock_dealprice')?.textContent?.trim() ||
                           document.querySelector('#priceblock_ourprice')?.textContent?.trim();
                """)
                if price_text:
                    price = float(re.sub(r'[^\d.]', '', price_text))

            elif 'flipkart.' in url.lower():
                source = 'Flipkart'
                title_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'span.B_NuCI'))
                )
                title = title_element.text.strip()
                
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div._30jeq3'))
                )
                price_text = price_element.text.strip()
                price = float(re.sub(r'[^\d.]', '', price_text))

            elif 'meesho.' in url.lower():
                source = 'Meesho'
                title_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pdp-title'))
                )
                title = title_element.text.strip()
                
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h5'))
                )
                price_text = price_element.text.strip()
                price = float(re.sub(r'[^\d.]', '', price_text))

            if title:
                # Search on other platforms
                results = {
                    source: {'title': title, 'price': price, 'url': url}
                }
                
                # Search on other platforms
                if source != 'Amazon':
                    amazon_result = self._search_amazon(title)
                    if amazon_result:
                        results['Amazon'] = amazon_result
                
                if source != 'Flipkart':
                    flipkart_result = self._search_flipkart(title)
                    if flipkart_result:
                        results['Flipkart'] = flipkart_result
                
                if source != 'Meesho':
                    meesho_result = self._search_meesho(title)
                    if meesho_result:
                        results['Meesho'] = meesho_result

                return results

        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return None
        finally:
            driver.quit()

    def _search_amazon(self, title):
        """Search for product on Amazon"""
        driver = self._setup_driver()
        try:
            search_query = self._clean_title(title)
            search_url = f"https://www.amazon.in/s?k={quote_plus(search_query)}"
            logger.info(f"Searching Amazon: {search_url}")
            
            driver.get(search_url)
            time.sleep(random.uniform(3, 5))

            # Get all products
            product_elements = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
            
            best_match = None
            best_score = 0
            
            for product_element in product_elements[:5]:  # Check first 5 results
                try:
                    # Get product title
                    product_title = product_element.find_element(By.CSS_SELECTOR, 'h2 span').text.strip()
                    
                    # Calculate similarity score
                    score = self._calculate_similarity(title, product_title)
                    
                    if score > best_score:
                        # Get product URL
                        product_url = product_element.find_element(By.CSS_SELECTOR, 'a.a-link-normal').get_attribute('href')
                        
                        # Get product price
                        try:
                            price_element = product_element.find_element(By.CSS_SELECTOR, 'span.a-price-whole')
                            price_text = price_element.text.strip()
                            price = float(re.sub(r'[^\d.]', '', price_text))
                        except:
                            price = None
                        
                        best_match = {
                            'title': product_title,
                            'price': price,
                            'url': product_url,
                            'score': score
                        }
                        best_score = score
                except Exception as e:
                    continue

            if best_match and best_score > 0.5:  # Only return if we have a good match
                return best_match
            return None

        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}")
            return None
        finally:
            driver.quit()

    def _search_flipkart(self, title):
        """Search for product on Flipkart"""
        driver = self._setup_driver()
        try:
            # Extract brand and model from title
            brand = title.split()[0].lower()
            model = ' '.join(title.split()[1:4]).lower()
            search_query = f"{brand} {model}"
            search_url = f"https://www.flipkart.com/search?q={quote_plus(search_query)}"
            logger.info(f"Searching Flipkart: {search_url}")
            
            driver.get(search_url)
            time.sleep(20)  # Increased wait time

            # Try to find products using JavaScript
            products = driver.execute_script("""
                function extractPrice(priceText) {
                    if (!priceText) return null;
                    const match = priceText.match(/[0-9,]+/);
                    return match ? match[0].replace(/,/g, '') : null;
                }

                const products = [];
                const productElements = document.querySelectorAll('div._1AtVbE, div._2kHMtA, div._1YokD2._2GoDe3, div._4rR01T, div._1xHGtK._373qXS');
                
                for (const element of productElements) {
                    try {
                        // Try different selectors for title
                        const titleSelectors = ['div._4rR01T', 'a.s1Q9rs', 'div._2WkVRV', 'span._2WkVRV', 'a._2UzuFa'];
                        let titleElement = null;
                        for (const selector of titleSelectors) {
                            titleElement = element.querySelector(selector);
                            if (titleElement) break;
                        }

                        // Try different selectors for price
                        const priceSelectors = ['div._30jeq3', 'div._25b18c', 'div._1vC4OE', 'span._1vC4OE', 'div._16Jk6d'];
                        let priceElement = null;
                        for (const selector of priceSelectors) {
                            priceElement = element.querySelector(selector);
                            if (priceElement) break;
                        }

                        // Try different selectors for URL
                        const urlSelectors = ['a._1fQZEK', 'a.s1Q9rs', 'a._2UzuFa', 'a._3fP5Ro'];
                        let urlElement = null;
                        for (const selector of urlSelectors) {
                            urlElement = element.querySelector(selector);
                            if (urlElement) break;
                        }
                        
                        if (titleElement && priceElement && urlElement) {
                            const title = titleElement.textContent.trim();
                            const priceText = priceElement.textContent.trim();
                            const price = extractPrice(priceText);
                            const url = urlElement.href;
                            
                            if (title && price && url) {
                                products.push({ title, price, url });
                            }
                        }
                    } catch (e) {
                        continue;
                    }
                }
                return products;
            """)

            if products:
                for product in products[:5]:
                    try:
                        # Calculate similarity score
                        score = self._calculate_similarity(title, product['title'])
                        logger.info(f"Flipkart match score: {score} for title: {product['title']}")
                        
                        if score > 0.2:
                            price = float(product['price'])
                            return {
                                'title': product['title'],
                                'price': price,
                                'url': product['url']
                            }
                    except Exception as e:
                        logger.error(f"Error processing Flipkart product: {str(e)}")
                        continue

            logger.warning("No good match found on Flipkart")
            return None

        except Exception as e:
            logger.error(f"Error searching Flipkart: {str(e)}")
            return None
        finally:
            driver.quit()

    def _search_meesho(self, title):
        """Search for product on Meesho"""
        driver = self._setup_driver()
        try:
            # Extract brand and model from title
            brand = title.split()[0].lower()
            model = ' '.join(title.split()[1:4]).lower()
            search_query = f"{brand} {model}"
            search_url = f"https://www.meesho.com/search?q={quote_plus(search_query)}"
            logger.info(f"Searching Meesho: {search_url}")
            
            driver.get(search_url)
            time.sleep(20)  # Increased wait time

            # Try to find products using JavaScript
            products = driver.execute_script("""
                function extractPrice(priceText) {
                    if (!priceText) return null;
                    const match = priceText.match(/[0-9,]+/);
                    return match ? match[0].replace(/,/g, '') : null;
                }

                const products = [];
                const productElements = document.querySelectorAll('div.ProductList__GridCol, div.ProductCard__CardWrapper, div.ProductCard__BaseCard, div.ProductCard__ProductCard, div.ProductCard__Card');
                
                for (const element of productElements) {
                    try {
                        // Try different selectors for title
                        const titleSelectors = ['p', 'div.ProductCard__Title', 'div.ProductCard__Name', 'span.ProductCard__Title', 'div.ProductCard__ProductName'];
                        let titleElement = null;
                        for (const selector of titleSelectors) {
                            titleElement = element.querySelector(selector);
                            if (titleElement) break;
                        }

                        // Try different selectors for price
                        const priceSelectors = ['h5', 'div.ProductCard__Price', 'div.ProductCard__PriceText', 'span.ProductCard__Price', 'div.ProductCard__PriceWrapper'];
                        let priceElement = null;
                        for (const selector of priceSelectors) {
                            priceElement = element.querySelector(selector);
                            if (priceElement) break;
                        }

                        // Try different selectors for URL
                        const urlSelectors = ['a', 'div.ProductCard__CardWrapper', 'div.ProductCard__Card'];
                        let urlElement = null;
                        for (const selector of urlSelectors) {
                            urlElement = element.querySelector(selector);
                            if (urlElement) break;
                        }
                        
                        if (titleElement && priceElement && urlElement) {
                            const title = titleElement.textContent.trim();
                            const priceText = priceElement.textContent.trim();
                            const price = extractPrice(priceText);
                            const url = urlElement.href;
                            
                            if (title && price && url) {
                                products.push({ title, price, url });
                            }
                        }
                    } catch (e) {
                        continue;
                    }
                }
                return products;
            """)

            if products:
                for product in products[:5]:
                    try:
                        # Calculate similarity score
                        score = self._calculate_similarity(title, product['title'])
                        logger.info(f"Meesho match score: {score} for title: {product['title']}")
                        
                        if score > 0.2:
                            price = float(product['price'])
                            return {
                                'title': product['title'],
                                'price': price,
                                'url': product['url']
                            }
                    except Exception as e:
                        logger.error(f"Error processing Meesho product: {str(e)}")
                        continue

            logger.warning("No good match found on Meesho")
            return None

        except Exception as e:
            logger.error(f"Error searching Meesho: {str(e)}")
            return None
        finally:
            driver.quit()

    def _calculate_similarity(self, title1, title2):
        """Calculate similarity between two titles"""
        # Convert to lowercase and split into words
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        
        # Remove common words
        common_words = {
            'with', 'and', 'for', 'the', 'in', 'on', 'at', 'to', 'of', 'a', 'an', 'by', 'from',
            'in', 'india', 'new', 'latest', 'best', 'buy', 'online', 'free', 'shipping', 'delivery',
            'warranty', 'years', 'year', 'months', 'month', 'days', 'day', 'hours', 'hour'
        }
        words1 = words1 - common_words
        words2 = words2 - common_words
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0
        
        # Give more weight to brand and model matches
        brand_model_words = {
            'sennheiser', 'momentum', 'wireless', 'headphones', 'headphone',
            'bluetooth', 'noise', 'cancelling', 'anc', 'over', 'ear'
        }
        brand_model_matches = len(words1.intersection(words2).intersection(brand_model_words))
        
        base_score = intersection / union
        return base_score + (brand_model_matches * 0.1)  # Add bonus for brand/model matches

def main():
    # Get product URL from user
    print("\nEnter the product URL (Amazon, Flipkart, or Meesho):")
    url = input().strip()
    
    # Initialize price comparison
    price_comparison = PriceComparison()
    
    # Get product details and search results
    print("\nSearching for product and comparing prices...")
    results = price_comparison.get_product_details(url)
    
    if results:
        print("\nPrice Comparison Results:")
        print("=" * 80)
        
        # Sort platforms by price (if available)
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1]['price'] if x[1]['price'] is not None else float('inf')
        )
        
        for platform, details in sorted_results:
            print(f"\n{platform}:")
            print(f"Title: {details['title']}")
            print(f"Price: ₹{details['price'] if details['price'] else 'Not found'}")
            print(f"URL: {details['url']}")
            print("-" * 80)
            
        # Show best deal
        available_prices = [(p, d['price']) for p, d in sorted_results if d['price'] is not None]
        if available_prices:
            best_platform, best_price = available_prices[0]
            print(f"\nBest Deal: {best_platform} at ₹{best_price}")
    else:
        print("\nError: Could not fetch product details. Please check the URL and try again.")

if __name__ == "__main__":
    main() 