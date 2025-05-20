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

def extract_price_with_requests(url):
    """
    Extract current price using requests and BeautifulSoup
    """
    try:
        ua = UserAgent()
        headers = {
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try different price selectors
        price_selectors = [
            'span.a-price-whole',  # Main price selector
            'span.a-offscreen',     # Alternative price selector
            'span.a-price'          # Another common price selector
        ]
        
        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                # Extract numeric value from price
                price_text = price_element.text.strip()
                # Remove currency symbol and commas, then convert to float
                price = float(re.sub(r'[^\d.]', '', price_text))
                return int(price)
                
        return None
    except Exception as e:
        print(f"Error extracting price with requests: {str(e)}")
        return None

def extract_price_with_selenium(url):
    """
    Extract current price using Selenium (more reliable but slower)
    """
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'user-agent={UserAgent().random}')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait for price element to be present
        wait = WebDriverWait(driver, 10)
        price_selectors = [
            'span.a-price-whole',
            'span.a-offscreen',
            'span.a-price'
        ]
        
        for selector in price_selectors:
            try:
                price_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                price_text = price_element.text.strip()
                price = float(re.sub(r'[^\d.]', '', price_text))
                driver.quit()
                return int(price)
            except:
                continue
                
        driver.quit()
        return None
    except Exception as e:
        print(f"Error extracting price with selenium: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return None

def get_current_price(url):
    """
    Main function to get current price using both methods
    """
    # First try with requests (faster)
    price = extract_price_with_requests(url)
    
    # If requests fails, try with selenium (more reliable)
    if price is None:
        price = extract_price_with_selenium(url)
    
    return price

# Example usage
if __name__ == "__main__":
    test_url = "https://www.amazon.in/Haier-Direct-Refrigerator-HRD-2203BS-Brushline/dp/B08KH7VF4Q/"
    price = get_current_price(test_url)
    print(f"Current price: {price}") 