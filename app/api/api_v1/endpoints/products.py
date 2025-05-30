from fastapi import APIRouter, Form, HTTPException, Depends, Query, Request
from app.models.product import ProductResponse
from app.db.mongodb import get_collection
from typing import Optional, List
from datetime import datetime
import logging
from app.api.api_v1.endpoints.deps import get_current_user
from app.models.user import User
from urllib.parse import unquote
from app.services.apify import ApifyAmazonScraper
from app.core.config import settings
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import Chrome
import time
import re
from selenium.webdriver.common.keys import Keys
from app.services.price_extractor import price_extractor
from app.services.price_extractor import PriceExtractor
import inspect # Added for debugging
from bson import ObjectId # Import ObjectId

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Products"])

apify_scraper = ApifyAmazonScraper(settings.APIFY_API_TOKEN)

# Replace this with the ACTUAL path to your downloaded chromedriver.exe
CHROMEDRIVER_PATH = r"C:\Users\Kitti\OneDrive\Desktop\sample BE\drivers\chromedriver.exe"

# Scraping helpers

def scrape_amazon_price(url: str):
    headers = {
        "User-Agent": UserAgent().random,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        price_tag = soup.find("span", {"class": "a-price-whole"})
        if price_tag:
            price = price_tag.text.replace(",", "").strip()
            return float(price)
        return None
    except Exception:
        return None

def scrape_flipkart_price(product_name: str):
    search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
    headers = {
        "User-Agent": UserAgent().random,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        price_tag = soup.find("div", {"class": "_30jeq3"})
        if price_tag:
            price = price_tag.text.replace("₹", "").replace(",", "").strip()
            return float(price)
        return None
    except Exception:
        return None

def scrape_reliance_digital_price(product_name: str):
    """Scrape the price of a product from Reliance Digital using the product name."""
    try:
        logging.info(f"Scraping Reliance Digital price for {product_name}")
        # Assuming a function exists to do the actual scraping
        price = price_extractor._search_reliance_digital(product_name)
        if price is not None:
            return price
        else:
            return "Not found"
    except Exception as e:
        logging.error(f"Error scraping Reliance Digital price for {product_name}: {e}")
        return "Error"

def scrape_google_shopping(product_name):
    headers = {
        "User-Agent": UserAgent().random,
        "Accept-Language": "en-US,en;q=0.9",
    }
    search_url = f"https://www.google.com/search?tbm=shop&q={product_name.replace(' ', '+')}"
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        offers = []
        for item in soup.select("div.sh-dgr__content"):
            title = item.select_one("h4, h3")
            price = item.select_one(".a8Pemb")
            store = item.select_one(".aULzUe")
            if title and price and store:
                offers.append({
                    "title": title.text.strip(),
                    "price": price.text.strip(),
                    "store": store.text.strip()
                })
        # Try to find Amazon, Flipkart, Meesho prices
        result = {"amazon": "Not found", "flipkart": "Not found", "reliancedigital": "Not found"}
        for offer in offers:
            if "amazon" in offer["store"].lower():
                result["amazon"] = offer["price"]
            if "flipkart" in offer["store"].lower():
                result["flipkart"] = offer["price"]
            if "reliancedigital" in offer["store"].lower():
                result["reliancedigital"] = offer["price"]
        return result
    except Exception as e:
        print("Google Shopping scrape error:", e)
        return {"amazon": "Not found", "flipkart": "Not found", "reliancedigital": "Not found"}

# Selenium scraping helpers

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--force-device-scale-factor=1')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    chrome_options.add_argument('--disable-site-isolation-trials')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Add experimental options
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    
    # Execute CDP commands
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = {
                runtime: {}
            };
        '''
    })
    return driver

def get_amazon_price(driver, product_name):
    try:
        logging.info(f"Attempting to scrape Amazon for {product_name}")
        search_url = f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}"
        driver.get(search_url)

        time.sleep(7)  # Initial wait for page load

        # Try to find product link based on search term with updated selectors
        product_link_element = None
        # Added multiple potential selectors for product links on Amazon search results
        amazon_link_selectors = [
            'div[data-component-type="s-search-result"] a.a-link-normal.s-underline-text.s-underline-link-text.s-link-attributes.s-title-instructions-style', # Original selector
            'div[data-component-type="s-search-result"] a.a-link-normal.a-text-normal', # Another common link selector
            'div[data-component-type="s-search-result"] a.a-link-normal', # Link within a search result item
            'div.s-result-item h2 a.a-link-normal', # Link within heading of a result item
            'a[href*="/dp/"]', # Link containing product detail path
            'div[data-index] a.a-link-normal' # Generic link within a data-index div
        ]

        for selector in amazon_link_selectors:
            try:
                # Look for the first product link that contains the product name in its text or a related title
                product_results = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"], div.s-result-item') # Include s-result-item as potential container
                logging.debug(f"Trying Amazon link selector '{selector}'. Found {len(product_results)} potential result containers.")
                for result in product_results:
                    try:
                        link = result.find_element(By.CSS_SELECTOR, selector)
                        # Check if the product name is in the link's text or a relevant element's text within the result
                        # Add more selectors for title/name within the search result item
                        title_elements = result.find_elements(By.CSS_SELECTOR, 'span.a-text-normal, h2 span, div.a-color-base.a-text-normal') # Added another title selector
                        link_text = link.text.lower()
                        combined_text = link_text + " " + " ".join([t.text.lower() for t in title_elements])

                        if product_name.lower() in combined_text:
                            product_link_element = link
                            logging.info(f"Found specific product link for {product_name} using selector '{selector}'.")
                            break # Found the relevant product link, exit inner loop
                    except Exception as e:
                        logging.debug(f"Could not find link with selector '{selector}' in a result container or process its text: {e}")
                        continue # Continue to the next result container
                if product_link_element: # If found in inner loop, break outer loop
                    break
            except Exception as e:
                logging.debug(f"Amazon link selector '{selector}' failed to find any elements: {e}")
                continue # Try the next selector

        # Fallback: If no specific product link found after trying all selectors, try getting the very first product link available
        if not product_link_element:
             logging.info("Specific product link not found after trying all selectors. Attempting to find the first product link as a fallback.")
             # Try a broader set of selectors for the very first link on the page
             fallback_selectors = [
                 'div[data-component-type="s-search-result"] a.a-link-normal', # Link within a search result item
                 'div.s-result-item h2 a.a-link-normal', # Link within heading of a result item
                 'a[href*="/dp/"]', # Link containing product detail path
                 'a.a-link-normal' # Any normal Amazon link
             ]
             for selector in fallback_selectors: # Use fallback selectors
                try:
                    product_link_element = driver.find_element(By.CSS_SELECTOR, selector)
                    logging.info(f"Found a fallback product link using selector '{selector}'.")
                    break # Found a fallback link, break loop
                except Exception as fallback_e:
                     logging.debug(f"Fallback selector '{selector}' failed on Amazon: {fallback_e}")
                     continue # Try next fallback selector


        if product_link_element:
            product_url = product_link_element.get_attribute('href')
            logging.info(f"Found Amazon product URL: {product_url}")
            driver.get(product_url)

            time.sleep(10)  # Increased wait time on product page

            price = "Not found"
            # Updated and reordered selectors to prioritize the main displayed *discounted* price
            price_selectors = [
                'span.a-price.a-text-price span.a-offscreen',  # High priority: Often captures the main displayed price (including deal) in the offscreen span
                '#priceblock_dealprice',  # High priority: Specific deal price block
                '#dealprice_feature_div span.a-offscreen', # High priority: Deal price selector within its feature div
                'span.a-size-base.a-color-price', # High priority: Specific class often used for the final selling price
                'div.a-section.a-spacing-small.a-spacing-top-small span.a-price.a-text-price span.a-offscreen', # High priority: More specific path to deal price offscreen
                'span.a-offscreen', # Medium priority: Fallback for any offscreen price (might be deal or regular)
                'div#corePriceDisplay_feature_div span.a-price span.a-offscreen',  # Medium priority: Core price display offscreen
                'div#corePrice_feature_div span.a-price-whole',  # Lower priority: Core price whole number - could be deal or MRP
                'span.a-price-whole',  # Lower priority: Generic whole price - could be deal or MRP
                'div#buybox span.a-price-whole',  # Lower priority: Buy box whole price
                'div#price_inside_buybox',  # Lower priority: Price inside buy box
                'div#twister-plus-price-data-row .a-price-whole',  # Lower priority: Price for variations
                'div#corePriceDisplay_feature_div span.a-price-whole', # Lower priority: Core price display whole number
                'div#priceblock_ourprice',  # Lowest priority: Regular price block (likely MRP if deal exists)
                 'span.a-price span.a-text-price' # Medium priority: Another common pattern for the visible price text (could be deal or MRP)
                 # Explicitly AVOIDING selectors known to contain the struck-through MRP like 'span.before-price.strike-through'
            ]

            for selector in price_selectors:
                try:
                    # Use WebDriverWait for price element with a timeout
                    # Increased timeout slightly for finding the price element
                    price_element = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    price = price_element.get_attribute('textContent') or price_element.text
                    logging.info(f"Found Amazon price element with selector {selector}: {price}")
                    
                    # Add a check to potentially skip struck-through prices if possible (though prioritizing selectors is better)
                    if price_element.value_of_css_property('text-decoration').strip() == 'line-through':
                         logging.info(f"Price found with selector {selector} is struck-through. Skipping.")
                         price = "Not found"
                         continue # Skip this price and try the next selector

                    # Keep this check to ensure price is not empty
                    if price and price.strip() != '':
                        logging.info(f"Found non-empty price {price} with selector {selector}.")
                        break
                    else:
                        price = "Not found"
                        logging.info(f"Price found with selector {selector} was empty.")
                except Exception as price_e:
                    logging.debug(f"Price selector {selector} failed on Amazon: {price_e}")
                    continue # Try next selector

            if price != "Not found":
                # Clean the price string - remove currency symbols, commas, and whitespace
                # Keep commas initially to handle Indian currency format like 9,890
                cleaned_price = re.sub(r'[^\d.,]', '', price) # Allow comma and dot
                logging.info(f"Cleaned Amazon price: {cleaned_price}")
                try:
                    # Remove commas before converting to float
                    price = float(cleaned_price.replace(',', ''))
                    logging.info(f"Converted Amazon price to float: {price}")
                except ValueError:
                    logging.warning(f"Could not convert cleaned Amazon price '{cleaned_price}' to float.")
                    price = "Not found"

            return {"store": "Amazon", "price": price}
        else:
            logging.warning(f"No product link found for {product_name} on Amazon.")
            return {"store": "Amazon", "price": "Not found"}

    except Exception as e:
        logging.error(f"Error scraping Amazon price for {product_name}: {e}", exc_info=True)
        return {"store": "Amazon", "price": "Error"}

def get_flipkart_price(driver, url):
    try:
        driver.get(url)
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_30jeq3"))
        ).text
        return price
    except Exception as e:
        print(f"Flipkart scrape error: {e}")
        return "Not found"

def get_reliancedigital_price(driver, url):
    try:
        driver.get(url)
        # Try primary price class (pdp-discounted-price for deal price)
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "pdp-discounted-price"))
        ).text
        return price
    except Exception as e:
        # If discounted price is not found, return "Not found" instead of falling back
        print(f"Reliance Digital discounted price scrape error: {e}")
        return "Not found"

def get_flipkart_price_from_search(driver, product_name):
    search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
    try:
        driver.get(search_url)
        # Wait for search results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_1fQZEK")) # Adjust selector if needed for product link
        )
        # Try to click the first product link (this selector might need adjustment)
        first_product = driver.find_element(By.CLASS_NAME, "_1fQZEK")
        first_product.click()

        # Wait for the product page to load and find the price
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_30jeq3"))
        )
        price = driver.find_element(By.CLASS_NAME, "_30jeq3").text
        return price
    except Exception as e:
        print(f"Flipkart search scrape error: {e}")
        return "Not found"

def get_reliancedigital_price_from_search(driver, product_name):
    search_url = f"https://www.reliancedigital.com/search?q={product_name.replace(' ', '%20')}"
    try:
        driver.get(search_url)
        # Wait for search results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".sc-ckVGcZ.gTOCES")) # Adjust selector if needed for product link
        )
        # Try to click the first product link (this selector might need adjustment)
        first_product = driver.find_element(By.CSS_SELECTOR, ".sc-ckVGcZ.gTOCES")
        first_product.click()

        # Wait for the product page to load and find the price
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "pdp-discounted-price, .pdp-price")) # Adjust selector if needed for price
        )
        try:
             price = driver.find_element(By.CLASS_NAME, "pdp-discounted-price").text
        except Exception as e:
             print(f"Could not find discounted price after search: {e}")
             price = "Not found"
        return price
    except Exception as e:
        print(f"Reliance Digital search scrape error: {e}")
        return "Not found"

def scrape_flipkart_price_selenium(driver, product_name):
    try:
        logging.info(f"Attempting to scrape Flipkart for {product_name}")
        search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
        driver.get(search_url)

        time.sleep(5)  # Increased initial wait time

        # Try to find product link based on search term
        product_link_element = None
        # Added multiple potential selectors for product cards and links on Flipkart search results
        flipkart_card_selectors = [
            'div._1AtVbE', # Common product card selector
            'div.cPHb8h', # Another potential card selector
            'div[data-id]', # Generic data-id selector for items
            'div.slAVV4', # Another potential card selector
            'a._1fQZEK' # Sometimes the link itself is the main clickable area
        ]
        flipkart_link_selectors = [
            'a._1fQZEK', # Selector for product link within card
            'a[href*="/p/"]', # Link containing product detail path
             'a' # General link selector
        ]

        for card_selector in flipkart_card_selectors:
             try:
                product_cards = driver.find_elements(By.CSS_SELECTOR, card_selector)
                logging.debug(f"Trying Flipkart card selector '{card_selector}'. Found {len(product_cards)} potential product cards.")
                for card in product_cards:
                    for link_selector in flipkart_link_selectors:
                        try:
                            link = card.find_element(By.CSS_SELECTOR, link_selector)
                            # Check if the product name is in the link's text or a relevant element's text within the card
                            # Add more selectors for title/name within the search result item
                            title_elements = card.find_elements(By.CSS_SELECTOR, 'div._4rR01T, a.IRpwCc, div.syl9yP') # Added another title selector
                            link_text = link.text.lower()
                            combined_text = link_text + " " + " ".join([t.text.lower() for t in title_elements])

                            if product_name.lower() in combined_text:
                                product_link_element = link
                                logging.info(f"Found specific product link for {product_name} using card selector '{card_selector}' and link selector '{link_selector}'.")
                                break # Found the relevant product link, exit all inner loops
                        except Exception as e:
                             logging.debug(f"Could not find link with selector '{link_selector}' in a Flipkart card using card selector '{card_selector}' or process its text: {e}")
                             continue # Try the next link selector in this card
                    if product_link_element: # If found with any link selector, break card loop
                         break
             except Exception as e:
                 logging.debug(f"Flipkart card selector '{card_selector}' failed to find any elements: {e}")
                 continue # Try the next card selector
             if product_link_element: # If found with any card selector, break outer loop
                 break


        # Fallback to the first product link if specific link not found
        if not product_link_element:
             logging.info("Specific product link not found after trying all selectors. Attempting to find the first product link as a fallback on Flipkart.")
             # Try a broader set of selectors for the very first link on the page
             fallback_selectors = [
                 'a._1fQZEK', # Selector for product link
                 'a[href*="/p/"]', # Link containing product detail path
                 'div._1AtVbE a', # Any link within a common product card container
                 'a' # Any link on the page
             ]
             for selector in fallback_selectors: # Use fallback selectors
                try:
                    product_link_element = driver.find_element(By.CSS_SELECTOR, selector)
                    logging.info(f"Found a fallback product link using selector '{selector}' on Flipkart.")
                    break # Found a fallback link, break loop
                except Exception as fallback_e:
                     logging.debug(f"Fallback link selector '{selector}' failed on Flipkart: {fallback_e}")
                     continue # Try next fallback selector


        if product_link_element:
            product_url = product_link_element.get_attribute('href')
            logging.info(f"Found Flipkart product URL: {product_url}")
            # Flipkart often returns relative URLs, make sure it's absolute
            if not product_url.startswith('http'):
                product_url = f"https://www.flipkart.com{product_url}"
                logging.info(f"Corrected Flipkart product URL to absolute: {product_url}")

            driver.get(product_url)
            time.sleep(7) # Increased wait time after navigating to product page

            price = "Not found"
            # Try multiple selectors for the price (Keeping previous selectors and adding more)
            price_selectors = [
                'div._30jeq3', # Common price class
                'div._25b18c ._30jeq3', # Another potential price container
                '._1_WHN1', # Older price class
                'div.CEmi00 div._30jeq3', # Price within a specific container on product page
                'div.PR 구매', # Another potential price container
                'div.B_NuCI', # Another potential price container (product title, sometimes contains price)
                'div._1gcOHe div._30jeq3' # Price in a different structure
            ]
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    price = price_element.text
                    logging.info(f"Found Flipkart price element with selector {selector}: {price}")
                    if price and price.strip() != '':
                        break # Found price, no need to try other selectors
                    else:
                         price = "Not found"
                except Exception as price_e:
                    logging.debug(f"Price selector {selector} failed on Flipkart: {price_e}")
                    continue # Selector not found, try next one

            if price != "Not found":
                # Clean the price string
                cleaned_price = re.sub(r'[^\d.]', '', price)
                logging.info(f"Cleaned Flipkart price: {cleaned_price}")
                try:
                    price = float(cleaned_price)
                    logging.info(f"Converted Flipkart price to float: {price}")
                except ValueError:
                    logging.warning(f"Could not convert cleaned Flipkart price '{cleaned_price}' to float.")
                    price = "Not found"

            return {"store": "Flipkart", "price": price}
        else:
            logging.warning(f"No product link found for {product_name} on Flipkart.")
            return {"store": "Flipkart", "price": "Not found"}

    except Exception as e:
        logging.error(f"Error scraping Flipkart price for {product_name}: {e}", exc_info=True)
        return {"store": "Flipkart", "price": "Error"}

def scrape_reliancedigital_price_selenium(driver, product_name):
    try:
        logging.info(f"Attempting to scrape Reliance Digital for {product_name}")
        search_url = f"https://www.reliancedigital.com/search?q={product_name.replace(' ', '%20')}"
        driver.get(search_url)

        time.sleep(5) # Increased initial wait time

        # Try to find product link based on search term
        product_link_element = None
        # Added multiple potential selectors for product cards and links on Reliance Digital search results
        reliancedigital_card_selectors = [
             'div.sc-hzDkRC', # Original common product card selector
             'div[data-qa="product-card"]', # Data-qa product card selector
             'div._1INlE', # Another potential card selector
             'div._2m5l7', # Yet another potential card selector
             'a[data-qa="product-image"]', # Link/card directly wrapping the product image
             'div[data-qa="product-item"]' # Another common product item container
        ]
        reliancedigital_link_selectors = [
            'a', # Link is often a direct child of the card
            'a[href*="/"]' # Link containing a path
        ]

        for card_selector in reliancedigital_card_selectors:
            try:
                product_cards = driver.find_elements(By.CSS_SELECTOR, card_selector)
                logging.debug(f"Trying Reliance Digital card selector '{card_selector}'. Found {len(product_cards)} potential product cards.")
                for card in product_cards:
                    for link_selector in reliancedigital_link_selectors:
                        try:
                            link = card.find_element(By.CSS_SELECTOR, link_selector)
                            # Check if the product name is in the link's href or text, or a relevant element's text within the card
                            # Add more selectors for title/name within the search result item
                            title_elements = card.find_elements(By.CSS_SELECTOR, 'div.sc-hKwDk.jhmkKE, div.sc-hKwDk.iBSzcs, p.sc-gcgGn.kTcoqp') # Added another title selector
                            link_text = link.text.lower()
                            combined_text = link_text + " " + link.get_attribute('href').lower() + " " + " ".join([t.text.lower() for t in title_elements])

                            if product_name.lower() in combined_text:
                                product_link_element = link
                                logging.info(f"Found specific product link for {product_name} using card selector '{card_selector}' and link selector '{link_selector}'.")
                                break # Found the relevant product link, exit all inner loops
                        except Exception as e:
                            logging.debug(f"Could not find link with selector '{link_selector}' in a Reliance Digital card using card selector '{card_selector}' or process its text: {e}")
                            continue # Try the next link selector in this card
                    if product_link_element: # If found with any link selector, break card loop
                         break
            except Exception as e:
                logging.debug(f"Reliance Digital card selector '{card_selector}' failed to find any elements: {e}")
                continue # Try the next card selector
            if product_link_element: # If found with any card selector, break outer loop
                break

        # Fallback to the first product link if specific link not found
        if not product_link_element:
             logging.info("Specific product link not found after trying all selectors. Attempting to find the first product link as a fallback on Reliance Digital.")
             # Try a broader set of selectors for the very first link on the page
             fallback_selectors = [
                 'div.sc-hzDkRC a', # Link within original common card selector
                 'div[data-qa="product-card"] a', # Link within data-qa product card selector
                 'a[data-qa="product-image"]', # Link/card directly wrapping the product image
                 'a[href*="/"]' # Link containing a path
             ]
             for selector in fallback_selectors: # Use fallback selectors
                try:
                    # Use a general selector that likely targets the first product link
                    product_link_element = driver.find_element(By.CSS_SELECTOR, selector)
                    logging.info(f"Found a fallback product link using selector '{selector}' on Reliance Digital.")
                    break # Found a fallback link, break loop
                except Exception as fallback_e:
                     logging.debug(f"Fallback link selector '{selector}' failed on Reliance Digital: {fallback_e}")
                     continue # Try next fallback selector


        if product_link_element:
            product_url = product_link_element.get_attribute('href')
            logging.info(f"Found Reliance Digital product URL: {product_url}")
            # Reliance Digital often returns relative URLs, make sure it's absolute
            if not product_url.startswith('http'):
                 product_url = f"https://www.reliancedigital.com{product_url}"
                 logging.info(f"Corrected Reliance Digital product URL to absolute: {product_url}")

            driver.get(product_url)
            time.sleep(7) # Increased wait time after navigating to product page

            price = "Not found"
            # Try multiple selectors for the price (Keeping previous selectors and adding more)
            price_selectors = [
                'h5.sc-e sacEfv', # Common price class (may need adjustment)
                '.sc-e sacEfv', # Another potential price class
                'span.sc-g setoFj', # Another potential price class
                 'span.Price_Price__2x_go', # Another potential price class
                 'div[data-qa="product-price"]', # Data-qa price selector
                 'span._30jeq3', # Found this price class on some Reliance Digital product pages
                 'div._2m5l7 span.sc-gcgGn.kTcoqp' # Price within a specific card structure
            ]
            for selector in price_selectors:
                try:
                    # Use WebDriverWait for price element
                    price_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    price = price_element.text
                    logging.info(f"Found Reliance Digital price element with selector {selector}: {price}")
                    if price and price.strip() != '':
                        break # Found price, no need to try other selectors
                    else:
                         price = "Not found"
                except Exception as price_e:
                   logging.debug(f"Price selector {selector} failed on Reliance Digital: {price_e}")
                   continue # Selector not found, try next one


            if price != "Not found":
                # Clean the price string
                cleaned_price = re.sub(r'[^\d.]', '', price)
                logging.info(f"Cleaned Reliance Digital price: {cleaned_price}")
                try:
                    price = float(cleaned_price)
                    logging.info(f"Converted Reliance Digital price to float: {price}")
                except ValueError:
                    logging.warning(f"Could not convert cleaned Reliance Digital price '{cleaned_price}' to float.")
                    price = "Not found"

            return {"store": "Reliance Digital", "price": price}
        else:
            logging.warning(f"No product link found for {product_name} on Reliance Digital.")
            return {"store": "Reliance Digital", "price": "Not found"}

    except Exception as e:
        logging.error(f"Error scraping Reliance Digital price for {product_name}: {e}", exc_info=True)
        return {"store": "Reliance Digital", "price": "Error"}

@router.get("/fetch-price/")
async def fetch_price(url: str):
    try:
        logger.info(f"Received request to fetch price for URL: {url}")
        
        # Fetch product details using the price extractor
        product_name, prices = await price_extractor.get_product_details(url)
        
        if not product_name:
            raise HTTPException(status_code=400, detail="Could not extract product name")
        
        # Ensure prices is a dictionary with the correct structure
        if not isinstance(prices, dict):
            prices = {
                "amazon": None,
                "flipkart": None,
                "reliancedigital": None
            }
        
        # Ensure all prices are either strings or None
        formatted_prices = {}
        for platform, price in prices.items():
            if price is not None and price != "Not found":
                formatted_prices[platform] = str(price)
            else:
                formatted_prices[platform] = None
        
        # Format the response
        response = {
            "product_name": product_name,
            "prices": formatted_prices
        }
        
        logger.info(f"Successfully fetched prices: {response}")
        return response
        
    except Exception as e:
        logger.error(f"An unexpected error occurred in fetch_price endpoint for URL {url}: {str(e)}", exc_info=True)
        # Return a structured error response
        return {
            "product_name": "Error occurred",
            "prices": {
                "amazon": None,
                "flipkart": None,
                "reliancedigital": None
            }
        }

@router.get("/{product_url:path}", response_model=ProductResponse)
async def get_product_by_url(
    product_url: str,
    current_user: User = Depends(get_current_user)
):
    """Get a product by its URL."""
    try:
        # Decode the URL
        decoded_url = unquote(product_url)
        logger.info(f"Processing get_product_by_url request: url={decoded_url}")
        
        products_collection = get_collection("products")
        product = await products_collection.find_one({
            "url": decoded_url,
            "user_id": str(current_user.id)
        })
        
        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )
            
        product["id"] = str(product["_id"])
        del product["_id"]
        return ProductResponse(**product)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product by URL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting product: {str(e)}"
        )

@router.post("/", response_model=ProductResponse)
async def add_product(
    name: str = Form(...),
    url: str = Form(...),
    website: str = Form(...),
    currency: str = Form(...),
    current_price: float = Form(...),
    target_price: float = Form(...),
    price_drop_threshold: float = Form(...),
    category: str = Form(...),
    image_url: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"Processing add_product request: name={name}, url={url}, website={website}")
    
    # Fetch prices from all three sites using the consistent extractor method
    current_price_extractor = PriceExtractor()
    try:
        extractor_results = await current_price_extractor.get_product_details(url)
        amazon_price = extractor_results.get('amazon', 'Not found')
        flipkart_price = extractor_results.get('flipkart', 'Not found')
        reliance_digital_price = extractor_results.get('reliancedigital', 'Not found')
    except Exception as e:
        logger.error(f"Error fetching prices during add_product for URL {url}: {str(e)}")
        # Set prices to 'Error' or 'Not found' if fetching fails
        amazon_price = 'Error'
        flipkart_price = 'Error'
        reliance_digital_price = 'Error'
    finally:
        # Ensure the driver is always cleaned up if the extractor was created
        if current_price_extractor and hasattr(current_price_extractor, 'cleanup'):
            try:
                current_price_extractor.cleanup()
            except Exception as e:
                logger.warning(f"Error during cleanup in add_product endpoint: {str(e)}")

    # Prepare product data
    product_data = {
        "name": name,
        "url": url,
        "website": website,
        "currency": currency,
        "current_price": current_price, # Keep the price from the form for now
        "target_price": target_price,
        "price_drop_threshold": price_drop_threshold,
        "category": category,
        "image_url": image_url,
        "description": description,
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "amazon_price": amazon_price,
        "flipkart_price": flipkart_price,
        "reliance_digital_price": reliance_digital_price,
    }

    try:
        # Insert into MongoDB
        products_collection = get_collection("products")
        result = await products_collection.insert_one(product_data)
        product_data["id"] = str(result.inserted_id)
        logger.info(f"Product added successfully with ID: {product_data['id']}")
        return ProductResponse(**product_data)
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[ProductResponse])
async def get_products(current_user: User = Depends(get_current_user)):
    logger.info("Processing get_products request")
    try:
        products_collection = get_collection("products")
        products = await products_collection.find({"user_id": str(current_user.id)}).to_list(None)
        # Convert MongoDB documents to ProductResponse format
        for product in products:
            product["id"] = str(product["_id"])  # Convert ObjectId to string
            del product["_id"]  # Remove the MongoDB _id field
        logger.info(f"Successfully fetched {len(products)} products")
        return products
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a product by its ID."""
    try:
        logger.info(f"Processing delete_product request for ID: {product_id}")
        
        # Validate the product_id as a valid ObjectId
        if not ObjectId.is_valid(product_id):
            raise HTTPException(status_code=400, detail="Invalid product ID format")
            
        products_collection = get_collection("products")
        
        # Attempt to delete the product, ensuring it belongs to the current user
        result = await products_collection.delete_one({
            "_id": ObjectId(product_id),
            "user_id": str(current_user.id)
        })
        
        if result.deleted_count == 0:
            # Product not found or not owned by the user
            raise HTTPException(status_code=404, detail="Product not found or you do not have permission to delete it")
        
        logger.info(f"Product with ID {product_id} deleted successfully.")
        return {"message": "Product deleted successfully"}
    
    except HTTPException:
        raise # Re-raise HTTPException so FastAPI handles it
    except Exception as e:
        logger.error(f"Error deleting product with ID {product_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting product: {str(e)}"
        )