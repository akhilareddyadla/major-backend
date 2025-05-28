from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import time
import logging
import urllib3
from urllib3.exceptions import MaxRetryError
import os
import platform
import sys
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress only selenium and urllib3 debug logs
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def get_chrome_version():
    """Get the installed Chrome version"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        return version
    except Exception as e:
        logger.error(f"Error getting Chrome version: {str(e)}")
        return None

def setup_driver(max_retries=3, retry_delay=2):
    """Setup and return a configured Chrome WebDriver with retry logic"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Get system architecture
    is_64bits = sys.maxsize > 2**32
    architecture = "win64" if is_64bits else "win32"
    
    for attempt in range(max_retries):
        try:
            # Get Chrome version
            chrome_version = get_chrome_version()
            if chrome_version:
                logger.info(f"Detected Chrome version: {chrome_version}")
            
            # Setup ChromeDriver with default manager (auto-detects version and architecture)
            service = Service(ChromeDriverManager().install())
            
            # Initialize driver with explicit executable path
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(30)
            
            # Test the connection
            driver.get('about:blank')
            return driver
            
        except (WebDriverException, MaxRetryError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise

def safe_get_element(driver, by, value, timeout=10):
    """Safely get an element with proper error handling"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception as e:
        logger.error(f"Error finding element {value}: {str(e)}")
        return None

def get_amazon_price(driver):
    # Try several selectors in order of likelihood
    selectors = [
        'span.a-price-whole',  # Standard price
        'span.a-offscreen',    # Sometimes used for price
        '#corePrice_feature_div span.a-price-whole',  # Core price
        'span.priceToPay span.a-price-whole',         # Price to pay
        'span.apexPriceToPay span.a-offscreen',       # Apex price
    ]
    for selector in selectors:
        price_element = safe_get_element(driver, By.CSS_SELECTOR, selector)
        if price_element and price_element.text.strip():
            return price_element.text.strip()
    return None

def test_amazon():
    """Test Amazon price extraction"""
    logger.info("Testing Amazon price extraction...")
    driver = None
    
    try:
        driver = setup_driver()
        url = "https://www.amazon.in/Sennheiser-Momentum-Wireless-Headphones-Designed/dp/B0CCRZPKR1"
        logger.info(f"Accessing URL: {url}")

        # Get the page with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(url)
                time.sleep(5)  # Wait for page to load
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Page load attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2)

        # Try to get the title
        title_element = safe_get_element(driver, By.CSS_SELECTOR, '#productTitle')
        title = title_element.text.strip() if title_element else None
        logger.info(f"Found title: {title}")

        # Try to get the price using the new function
        price = get_amazon_price(driver)
        logger.info(f"Found price: {price}")

        return title, price

    except Exception as e:
        logger.error(f"Error in test_amazon: {str(e)}")
        return None, None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")

def test_flipkart():
    """Test Flipkart price extraction"""
    logger.info("Testing Flipkart price extraction...")
    driver = None
    
    try:
        driver = setup_driver()
        
        # Test URL
        url = "https://www.flipkart.com/sennheiser-momentum-4-wireless-headphones/p/itm123456789"
        logger.info(f"Accessing URL: {url}")
        
        # Get the page with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(url)
                time.sleep(5)  # Wait for page to load
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Page load attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2)
        
        # Try to get the title
        title_element = safe_get_element(driver, By.CSS_SELECTOR, 'span.B_NuCI')
        title = title_element.text.strip() if title_element else None
        logger.info(f"Found title: {title}")
        
        # Try to get the price
        price_element = safe_get_element(driver, By.CSS_SELECTOR, 'div._30jeq3')
        price = price_element.text.strip() if price_element else None
        logger.info(f"Found price: {price}")
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in test_flipkart: {str(e)}")
        return None, None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")

def test_meesho():
    """Test Meesho price extraction"""
    logger.info("Testing Meesho price extraction...")
    driver = None
    
    try:
        driver = setup_driver()
        
        # Test URL
        url = "https://www.meesho.com/sennheiser-momentum-4-wireless-headphones/p/123456"
        logger.info(f"Accessing URL: {url}")
        
        # Get the page with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(url)
                time.sleep(5)  # Wait for page to load
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Page load attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2)
        
        # Try to get the title
        title_element = safe_get_element(driver, By.CSS_SELECTOR, 'h1.pdp-title')
        title = title_element.text.strip() if title_element else None
        logger.info(f"Found title: {title}")
        
        # Try to get the price
        price_element = safe_get_element(driver, By.CSS_SELECTOR, 'h5')
        price = price_element.text.strip() if price_element else None
        logger.info(f"Found price: {price}")
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in test_meesho: {str(e)}")
        return None, None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")

def get_reliance_digital_price(driver, search_term):
    """Get price from Reliance Digital"""
    try:
        # Construct search URL
        search_url = f"https://www.reliancedigital.in/search?q={search_term.replace(' ', '+')}"
        logger.info(f"Navigating to Reliance Digital search URL: {search_url}")
        
        # Navigate to search page
        driver.get(search_url)
        time.sleep(5)  # Wait for initial load
        
        # Wait for product containers with multiple selectors
        selectors = [
            'div.sp__product',
            'div.product-list',
            'div.product-item',
            'div[data-testid="product-card"]',
            'div.product-card'
        ]
        
        product_found = False
        for selector in selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                product_found = True
                logger.info(f"Found product container with selector: {selector}")
                break
            except:
                continue
        
        if not product_found:
            logger.warning("No product containers found")
            return "Not found"
            
        # Try to find price with multiple selectors
        price_selectors = [
            'span[data-testid="price"]',
            'span.price',
            'div.price',
            'span[class*="price"]',
            'div[class*="price"]'
        ]
        
        for selector in price_selectors:
            try:
                price_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                price_text = price_element.text.strip()
                # Clean price text (remove ₹, commas, etc.)
                price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text))
                if price:
                    logger.info(f"Found price with selector {selector}: {price}")
                    return price
            except:
                continue
                
        logger.warning("No price found with any selector")
        return "Not found"
        
    except Exception as e:
        logger.error(f"Error getting Reliance Digital price: {str(e)}")
        return "Not found"

if __name__ == "__main__":
    try:
        # Initialize driver
        driver = setup_driver()
        
        # Test Amazon
        amazon_title, amazon_price = test_amazon()
        
        # Test Flipkart
        flipkart_title, flipkart_price = test_flipkart()
        
        # Test Reliance Digital
        search_term = amazon_title.split(':')[0] if amazon_title else "product"
        reliance_price = get_reliance_digital_price(driver, search_term)
        
        # Format prices
        prices = {
            "amazon": str(amazon_price) if amazon_price else "Not found",
            "flipkart": str(flipkart_price) if flipkart_price else "Not found",
            "reliancedigital": reliance_price
        }
        
        # Print clean JSON response
        response = {
            "product_name": amazon_title,
            "prices": prices
        }
        print("\nFinal Results:")
        print(json.dumps(response, indent=2))
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.quit() 