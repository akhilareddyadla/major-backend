from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_amazon():
    """Test Amazon price extraction"""
    logger.info("Testing Amazon price extraction...")
    
    # Initialize Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Test URL
        url = "https://www.amazon.in/Sennheiser-Momentum-Wireless-Headphones-Designed/dp/B0CCRZPKR1"
        logger.info(f"Accessing URL: {url}")
        
        # Get the page
        driver.get(url)
        time.sleep(5)  # Wait for page to load
        
        # Try to get the title
        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#productTitle'))
            )
            title = title_element.text.strip()
            logger.info(f"Found title: {title}")
        except Exception as e:
            logger.error(f"Error getting title: {str(e)}")
            title = None
        
        # Try to get the price
        try:
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.a-price-whole'))
            )
            price = price_element.text.strip()
            logger.info(f"Found price: {price}")
        except Exception as e:
            logger.error(f"Error getting price: {str(e)}")
            price = None
        
        # Clean up
        driver.quit()
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in test_amazon: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None, None

def test_flipkart():
    """Test Flipkart price extraction"""
    logger.info("Testing Flipkart price extraction...")
    
    # Initialize Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Test URL
        url = "https://www.flipkart.com/sennheiser-momentum-4-wireless-headphones/p/itm123456789"
        logger.info(f"Accessing URL: {url}")
        
        # Get the page
        driver.get(url)
        time.sleep(5)  # Wait for page to load
        
        # Try to get the title
        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.B_NuCI'))
            )
            title = title_element.text.strip()
            logger.info(f"Found title: {title}")
        except Exception as e:
            logger.error(f"Error getting title: {str(e)}")
            title = None
        
        # Try to get the price
        try:
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div._30jeq3'))
            )
            price = price_element.text.strip()
            logger.info(f"Found price: {price}")
        except Exception as e:
            logger.error(f"Error getting price: {str(e)}")
            price = None
        
        # Clean up
        driver.quit()
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in test_flipkart: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None, None

def test_meesho():
    """Test Meesho price extraction"""
    logger.info("Testing Meesho price extraction...")
    
    # Initialize Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Test URL
        url = "https://www.meesho.com/sennheiser-momentum-4-wireless-headphones/p/123456"
        logger.info(f"Accessing URL: {url}")
        
        # Get the page
        driver.get(url)
        time.sleep(5)  # Wait for page to load
        
        # Try to get the title
        try:
            title_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pdp-title'))
            )
            title = title_element.text.strip()
            logger.info(f"Found title: {title}")
        except Exception as e:
            logger.error(f"Error getting title: {str(e)}")
            title = None
        
        # Try to get the price
        try:
            price_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h5'))
            )
            price = price_element.text.strip()
            logger.info(f"Found price: {price}")
        except Exception as e:
            logger.error(f"Error getting price: {str(e)}")
            price = None
        
        # Clean up
        driver.quit()
        
        return title, price
        
    except Exception as e:
        logger.error(f"Error in test_meesho: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None, None

if __name__ == "__main__":
    print("\nTesting Amazon...")
    amazon_title, amazon_price = test_amazon()
    print(f"Amazon Results - Title: {amazon_title}, Price: {amazon_price}")
    
    print("\nTesting Flipkart...")
    flipkart_title, flipkart_price = test_flipkart()
    print(f"Flipkart Results - Title: {flipkart_title}, Price: {flipkart_price}")
    
    print("\nTesting Meesho...")
    meesho_title, meesho_price = test_meesho()
    print(f"Meesho Results - Title: {meesho_title}, Price: {meesho_price}") 