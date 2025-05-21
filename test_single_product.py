from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import time
import logging
import re
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_price_and_title(url):
    """Extract price and title from a product URL"""
    logger.info(f"Starting price extraction for URL: {url}")
    
    # Initialize Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Set a realistic user agent
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    try:
        # Initialize Chrome driver
        logger.info("Initializing Chrome driver...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Execute CDP commands to prevent detection
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        # Get the page
        logger.info(f"Accessing URL: {url}")
        driver.get(url)
        
        # Add random delay to simulate human behavior
        time.sleep(random.uniform(3, 5))
        
        # Get page source for debugging
        page_source = driver.page_source
        logger.info(f"Page source length: {len(page_source)}")
        
        # Try to get the title
        title = None
        price = None
        
        if 'amazon.' in url.lower():
            logger.info("Detected Amazon URL")
            
            # Try to get title using JavaScript
            try:
                title = driver.execute_script("""
                    return document.querySelector('#productTitle')?.textContent?.trim() ||
                           document.querySelector('h1#title')?.textContent?.trim() ||
                           document.querySelector('span#productTitle')?.textContent?.trim() ||
                           document.querySelector('h1.a-size-large')?.textContent?.trim();
                """)
                if title:
                    logger.info(f"Found title using JavaScript: {title}")
            except Exception as e:
                logger.error(f"Error getting title with JavaScript: {str(e)}")
            
            # If JavaScript method failed, try Selenium
            if not title:
                title_selectors = [
                    '#productTitle',
                    'h1#title',
                    'span#productTitle',
                    'h1.a-size-large'
                ]
                
                for selector in title_selectors:
                    try:
                        logger.info(f"Trying title selector: {selector}")
                        title_element = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        title = title_element.text.strip()
                        logger.info(f"Found title: {title}")
                        break
                    except Exception as e:
                        logger.error(f"Failed with selector {selector}: {str(e)}")
            
            # Try to get price using JavaScript
            try:
                price_text = driver.execute_script("""
                    return document.querySelector('span.a-price-whole')?.textContent?.trim() ||
                           document.querySelector('span.a-offscreen')?.textContent?.trim() ||
                           document.querySelector('span.a-price')?.textContent?.trim() ||
                           document.querySelector('#priceblock_dealprice')?.textContent?.trim() ||
                           document.querySelector('#priceblock_ourprice')?.textContent?.trim();
                """)
                if price_text:
                    price = float(re.sub(r'[^\d.]', '', price_text))
                    logger.info(f"Found price using JavaScript: {price}")
            except Exception as e:
                logger.error(f"Error getting price with JavaScript: {str(e)}")
            
            # If JavaScript method failed, try Selenium
            if not price:
                price_selectors = [
                    'span.a-price-whole',
                    'span.a-offscreen',
                    'span.a-price',
                    '#priceblock_dealprice',
                    '#priceblock_ourprice'
                ]
                
                for selector in price_selectors:
                    try:
                        logger.info(f"Trying price selector: {selector}")
                        price_element = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        price_text = price_element.text.strip()
                        price = float(re.sub(r'[^\d.]', '', price_text))
                        logger.info(f"Found price: {price}")
                        break
                    except Exception as e:
                        logger.error(f"Failed with selector {selector}: {str(e)}")
        
        elif 'flipkart.' in url.lower():
            logger.info("Detected Flipkart URL")
            try:
                title_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'span.B_NuCI'))
                )
                title = title_element.text.strip()
                logger.info(f"Found title: {title}")
            except Exception as e:
                logger.error(f"Error getting Flipkart title: {str(e)}")
            
            try:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div._30jeq3'))
                )
                price_text = price_element.text.strip()
                price = float(re.sub(r'[^\d.]', '', price_text))
                logger.info(f"Found price: {price}")
            except Exception as e:
                logger.error(f"Error getting Flipkart price: {str(e)}")
        
        elif 'meesho.' in url.lower():
            logger.info("Detected Meesho URL")
            try:
                title_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pdp-title'))
                )
                title = title_element.text.strip()
                logger.info(f"Found title: {title}")
            except Exception as e:
                logger.error(f"Error getting Meesho title: {str(e)}")
            
            try:
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h5'))
                )
                price_text = price_element.text.strip()
                price = float(re.sub(r'[^\d.]', '', price_text))
                logger.info(f"Found price: {price}")
            except Exception as e:
                logger.error(f"Error getting Meesho price: {str(e)}")
        
        # Clean up
        driver.quit()
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in price extraction: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None, None

if __name__ == "__main__":
    # Test URLs for different platforms
    test_urls = [
        # Amazon URLs
        "https://www.amazon.in/Sennheiser-Momentum-Wireless-Headphones-Designed/dp/B0CCRZPKR1",
        "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
        "https://www.amazon.in/Samsung-Galaxy-S23-Ultra-Phantom/dp/B0BSHFXH1P",
        
        # Flipkart URLs
        "https://www.flipkart.com/samsung-galaxy-s23-ultra-5g-phantom-black-256-gb/p/itm5a9f3f8aa9872",
        "https://www.flipkart.com/apple-iphone-15-pro-max-natural-titanium-256-gb/p/itm6e30c6ee045d2",
        
        # Meesho URLs
        "https://www.meesho.com/electronics/c/6",
        "https://www.meesho.com/mobiles/c/7"
    ]
    
    print("\nStarting price extraction tests...")
    print("=" * 80)
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        print("-" * 80)
        title, price = extract_price_and_title(url)
        
        print("\nResults:")
        print(f"Title: {title}")
        print(f"Price: ₹{price if price else 'Not found'}")
        print("=" * 80) 