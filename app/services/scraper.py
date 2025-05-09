from typing import Optional
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings
from app.models.product import Product, WebsiteType
import logging

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")

    async def get_product_info(self, url: str, website_type: WebsiteType) -> Optional[Product]:
        try:
            if website_type == WebsiteType.AMAZON:
                return await self._scrape_amazon(url)
            elif website_type == WebsiteType.EBAY:
                return await self._scrape_ebay(url)
            elif website_type == WebsiteType.WALMART:
                return await self._scrape_walmart(url)
            else:
                return await self._scrape_custom(url)
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None

    async def _scrape_amazon(self, url: str) -> Optional[Product]:
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Amazon specific selectors
            name = soup.select_one("#productTitle")
            price = soup.select_one(".a-price-whole")
            image = soup.select_one("#landingImage")
            
            if not all([name, price, image]):
                # Try with Selenium if BeautifulSoup fails
                return await self._scrape_with_selenium(url, WebsiteType.AMAZON)
            
            return Product(
                name=name.text.strip(),
                url=url,
                website_type=WebsiteType.AMAZON,
                current_price=float(price.text.strip().replace(',', '')),
                image_url=image.get('src', ''),
                description=soup.select_one("#productDescription") and soup.select_one("#productDescription").text.strip()
            )
        except Exception as e:
            logger.error(f"Error scraping Amazon product: {str(e)}")
            return None

    async def _scrape_ebay(self, url: str) -> Optional[Product]:
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # eBay specific selectors
            name = soup.select_one(".x-item-title")
            price = soup.select_one(".x-price-primary")
            image = soup.select_one(".ux-image-carousel-item img")
            
            if not all([name, price, image]):
                return await self._scrape_with_selenium(url, WebsiteType.EBAY)
            
            return Product(
                name=name.text.strip(),
                url=url,
                website_type=WebsiteType.EBAY,
                current_price=float(price.text.strip().replace('$', '').replace(',', '')),
                image_url=image.get('src', ''),
                description=soup.select_one(".item-description") and soup.select_one(".item-description").text.strip()
            )
        except Exception as e:
            logger.error(f"Error scraping eBay product: {str(e)}")
            return None

    async def _scrape_walmart(self, url: str) -> Optional[Product]:
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Walmart specific selectors
            name = soup.select_one("h1[data-automation-id='product-title']")
            price = soup.select_one("[data-automation-id='product-price']")
            image = soup.select_one(".hover-zoom-hero-image")
            
            if not all([name, price, image]):
                return await self._scrape_with_selenium(url, WebsiteType.WALMART)
            
            return Product(
                name=name.text.strip(),
                url=url,
                website_type=WebsiteType.WALMART,
                current_price=float(price.text.strip().replace('$', '').replace(',', '')),
                image_url=image.get('src', ''),
                description=soup.select_one("[data-automation-id='product-description']") and 
                          soup.select_one("[data-automation-id='product-description']").text.strip()
            )
        except Exception as e:
            logger.error(f"Error scraping Walmart product: {str(e)}")
            return None

    async def _scrape_custom(self, url: str) -> Optional[Product]:
        try:
            # For custom websites, use Selenium by default
            return await self._scrape_with_selenium(url, WebsiteType.CUSTOM)
        except Exception as e:
            logger.error(f"Error scraping custom product: {str(e)}")
            return None

    async def _scrape_with_selenium(self, url: str, website_type: WebsiteType) -> Optional[Product]:
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Website-specific selectors
            selectors = {
                WebsiteType.AMAZON: {
                    "name": "#productTitle",
                    "price": ".a-price-whole",
                    "image": "#landingImage",
                    "description": "#productDescription"
                },
                WebsiteType.EBAY: {
                    "name": ".x-item-title",
                    "price": ".x-price-primary",
                    "image": ".ux-image-carousel-item img",
                    "description": ".item-description"
                },
                WebsiteType.WALMART: {
                    "name": "h1[data-automation-id='product-title']",
                    "price": "[data-automation-id='product-price']",
                    "image": ".hover-zoom-hero-image",
                    "description": "[data-automation-id='product-description']"
                },
                WebsiteType.CUSTOM: {
                    "name": "h1",
                    "price": ".price",
                    "image": "img.product-image",
                    "description": ".description"
                }
            }
            
            selector = selectors[website_type]
            name = driver.find_element(By.CSS_SELECTOR, selector["name"]).text
            price = driver.find_element(By.CSS_SELECTOR, selector["price"]).text
            image = driver.find_element(By.CSS_SELECTOR, selector["image"]).get_attribute("src")
            description = driver.find_element(By.CSS_SELECTOR, selector["description"]).text if driver.find_elements(By.CSS_SELECTOR, selector["description"]) else None
            
            driver.quit()
            
            return Product(
                name=name.strip(),
                url=url,
                website_type=website_type,
                current_price=float(price.strip().replace('$', '').replace(',', '')),
                image_url=image,
                description=description
            )
        except Exception as e:
            logger.error(f"Error with Selenium scraping: {str(e)}")
            return None 