from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import logging
import json
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.core.config import settings
from app.services.alerts import alert_service
from app.services.products import product_service
from app.services.auth import auth_service
from app.services.notification import notification_service
from app.services.apify import ApifyAmazonScraper
from app.services.price_extractor import price_extractor
from app.db.init_db import init_db
from fastapi.responses import JSONResponse, RedirectResponse
from app.api.api_v1 import api_router
from fastapi.websockets import WebSocketState
import uvicorn
from starlette.routing import Route, WebSocketRoute
from typing import Dict, Optional
from app.services.scheduler import price_check_scheduler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import time
from pydantic import BaseModel
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
from fastapi import Depends
from app.api.api_v1.endpoints import products
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
apify_scraper = ApifyAmazonScraper(settings.APIFY_API_TOKEN)

# Mount the API router with prefix
app.include_router(api_router, prefix="/api/v1")


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    await init_db()
    await price_check_scheduler.initialize()
    price_check_scheduler.setup_scheduler(apify_scraper, notification_service)
    await alert_service.initialize()
    await product_service.initialize()
    await auth_service.initialize()
    await notification_service.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
    await price_check_scheduler.shutdown()

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        routes=app.routes,
    )
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

def get_selenium_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    ua = UserAgent()
    options.add_argument(f"user-agent={ua.random}")
    # Use the correct hardcoded path to chromedriver.exe
    chromedriver_path = r"C:\Users\Kitti\.wdm\drivers\chromedriver\win64\136.0.7103.94\chromedriver-win32\chromedriver.exe"
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def extract_product_name_from_url(url: str) -> str:
    """Extract product name from Amazon URL"""
    try:
        logger.info(f"[Extract] Trying to extract product name from URL: {url}")
        # Try to extract the product slug from the URL
        match = re.search(r"amazon\.[a-z.]+/(?:.*?/)?([A-Za-z0-9-]+)/dp/", url)
        if match:
            slug = match.group(1)
            name = slug.replace('-', ' ')
            name = re.sub(r'\b(by|from|on|in|at|the)\b', '', name, flags=re.IGNORECASE)
            name = ' '.join(name.split())
            logger.info(f"[Extract] Extracted from slug: {name}")
            if name and len(name) > 3:
                return name
        # If no match found, try to get it from the page
        driver = get_selenium_driver()
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span#productTitle, h1#title"))
        )
        for selector in ["span#productTitle", "h1#title", "div#title", "span.a-size-large"]:
            try:
                title_element = driver.find_element(By.CSS_SELECTOR, selector)
                if title_element:
                    product_name = title_element.text.strip()
                    logger.info(f"[Extract] Extracted from page: {product_name}")
                    driver.quit()
                    return product_name
            except Exception as e:
                logger.debug(f"[Extract] Selector {selector} failed: {str(e)}")
                continue
        driver.quit()
        logger.warning(f"[Extract] Could not extract product name from URL: {url}")
        return ""
    except Exception as e:
        logger.error(f"[Extract] Error extracting product name from URL: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return ""

def fetch_amazon_price(product_name: str):
    search_url = f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}"
    try:
        # First try to get the first product URL
        ua = UserAgent()
        headers = {
            "User-Agent": ua.random,
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result = soup.find("div", {"data-component-type": "s-search-result"})
        
        if result:
            # Get the product URL and title
            product_link = result.find("a", {"class": "a-link-normal s-no-outline"})
            product_title = result.find("span", {"class": "a-text-normal"})
            if product_link and 'href' in product_link.attrs:
                product_url = "https://www.amazon.in" + product_link['href']
                # Use the price extractor to get the current price
                price = price_extractor.get_current_price(product_url)
                # Return both price and title
                title = product_title.text.strip() if product_title else product_name
                logger.info(f"[Amazon] Found product title: {title}")
                return price, title
        
        # If we couldn't get the product URL, try direct search
        driver = get_selenium_driver()
        driver.get(search_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        
        result = soup.find("div", {"data-component-type": "s-search-result"})
        if result:
            product_link = result.find("a", {"class": "a-link-normal s-no-outline"})
            product_title = result.find("span", {"class": "a-text-normal"})
            if product_link and 'href' in product_link.attrs:
                product_url = "https://www.amazon.in" + product_link['href']
                price = price_extractor.get_current_price(product_url)
                title = product_title.text.strip() if product_title else product_name
                logger.info(f"[Amazon] Found product title: {title}")
                return price, title
                
        logger.error("[Amazon] No product found. HTML snippet: %s", soup.prettify()[:1000])
        return None, product_name
    except Exception as e:
        logger.error("[Amazon] Error fetching price: %s", str(e))
        return None, product_name

def fetch_flipkart_price(product_name: str):
    search_terms = product_name.split()
    search_variations = [
        product_name,
        ' '.join(search_terms[:3]),
        ' '.join(search_terms[:2]),
        search_terms[0],
        ' '.join([term for term in search_terms if len(term) > 3]),
        ' '.join([term for term in search_terms if term.lower() not in ['the', 'a', 'an', 'and', 'or', 'but']])
    ]
    logger.info(f"[Flipkart] Search variations: {search_variations}")
    for search_term in search_variations:
        search_url = f"https://www.flipkart.com/search?q={search_term.replace(' ', '+')}"
        try:
            logger.info(f"[Flipkart] Trying search URL: {search_url}")
            driver = get_selenium_driver()
            driver.get(search_url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._1AtVbE, div._4rR01T, div._2kHMtA, div._1fQZEK"))
            )
            time.sleep(2)
            product_selectors = [
                "div._1AtVbE",
                "div._4rR01T",
                "div._2kHMtA",
                "div._1fQZEK",
                "div._2MlkI1"
            ]
            for selector in product_selectors:
                try:
                    results = driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"[Flipkart] {len(results)} results with selector {selector}")
                    # Print first 3 product titles for debugging
                    for result in results[:3]:
                        try:
                            title_element = result.find_element(By.CSS_SELECTOR, "div._4rR01T")
                            logger.info(f"[Flipkart] Debug title: {title_element.text.strip()}")
                        except Exception as e:
                            logger.debug(f"[Flipkart] Debug title fetch failed: {str(e)}")
                    for result in results[:5]:
                        title_selectors = ["div._4rR01T", "a.s1Q9rs", "div._2WkVRV"]
                        product_title = None
                        for title_selector in title_selectors:
                            try:
                                title_element = result.find_element(By.CSS_SELECTOR, title_selector)
                                if title_element:
                                    product_title = title_element.text.strip().lower()
                                    logger.info(f"[Flipkart] Found product title: {product_title}")
                                    break
                            except:
                                continue
                        if not product_title:
                            continue
                        search_terms_lower = search_term.lower().split()
                        title_terms = product_title.split()
                        matching_terms = sum(1 for term in search_terms_lower if any(term in t for t in title_terms))
                        match_score = matching_terms / len(search_terms_lower)
                        logger.info(f"[Flipkart] Match score for '{product_title}': {match_score}")
                        if match_score >= 0.3:
                            price_selectors = ["div._30jeq3", "div._1_WHN1", "div._16Jk6d", "div._3qQ9m1", "div._25b18c", "span._1_WHN1"]
                            for price_selector in price_selectors:
                                try:
                                    price_element = result.find_element(By.CSS_SELECTOR, price_selector)
                                    if price_element:
                                        price_text = price_element.text.strip()
                                        logger.info(f"[Flipkart] Found price text: {price_text}")
                                        price = float(re.sub(r'[^\d.]', '', price_text))
                                        driver.quit()
                                        logger.info(f"[Flipkart] Successfully extracted price: {price}")
                                        return price
                                except Exception as e:
                                    logger.debug(f"[Flipkart] Price selector {price_selector} failed: {str(e)}")
                                    continue
                except Exception as e:
                    logger.debug(f"[Flipkart] Product selector {selector} failed: {str(e)}")
                    continue
            driver.quit()
        except Exception as e:
            logger.error(f"[Flipkart] Error with search term '{search_term}': {str(e)}")
            if 'driver' in locals():
                driver.quit()
            continue
    logger.error(f"[Flipkart] No price found for product: {product_name}")
    return None

def fetch_meesho_price(product_name: str):
    search_terms = product_name.split()
    search_variations = [
        product_name,
        ' '.join(search_terms[:3]),
        ' '.join(search_terms[:2]),
        search_terms[0],
        ' '.join([term for term in search_terms if len(term) > 3]),
        ' '.join([term for term in search_terms if term.lower() not in ['the', 'a', 'an', 'and', 'or', 'but']])
    ]
    logger.info(f"[Meesho] Search variations: {search_variations}")
    for search_term in search_variations:
        search_url = f"https://www.meesho.com/search?q={search_term.replace(' ', '%20')}"
        try:
            logger.info(f"[Meesho] Trying search URL: {search_url}")
            driver = get_selenium_driver()
            driver.get(search_url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.sc-gswNZR, div.sc-ckVGcZ, div.sc-bczRLJ, div.sc-dkzDqf"))
            )
            time.sleep(2)
            product_selectors = [
                "div.sc-gswNZR",
                "div.sc-ckVGcZ",
                "div.sc-bczRLJ",
                "div.sc-dkzDqf",
                "div.sc-bczRLJ"
            ]
            for selector in product_selectors:
                try:
                    results = driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"[Meesho] {len(results)} results with selector {selector}")
                    # Print first 3 product titles for debugging
                    for result in results[:3]:
                        try:
                            title_element = result.find_element(By.CSS_SELECTOR, "p.sc-bczRLJ")
                            logger.info(f"[Meesho] Debug title: {title_element.text.strip()}")
                        except Exception as e:
                            logger.debug(f"[Meesho] Debug title fetch failed: {str(e)}")
                    for result in results[:5]:
                        title_selectors = ["p.sc-bczRLJ", "div.sc-bczRLJ", "h5"]
                        product_title = None
                        for title_selector in title_selectors:
                            try:
                                title_element = result.find_element(By.CSS_SELECTOR, title_selector)
                                if title_element:
                                    product_title = title_element.text.strip().lower()
                                    logger.info(f"[Meesho] Found product title: {product_title}")
                                    break
                            except:
                                continue
                        if not product_title:
                            continue
                        search_terms_lower = search_term.lower().split()
                        title_terms = product_title.split()
                        matching_terms = sum(1 for term in search_terms_lower if any(term in t for t in title_terms))
                        match_score = matching_terms / len(search_terms_lower)
                        logger.info(f"[Meesho] Match score for '{product_title}': {match_score}")
                        if match_score >= 0.3:
                            price_selectors = ["h5", "div.pdp-price", "div.sc-bczRLJ", "div.pdp-discounted-price", "div.sc-bczRLJ h5", "span.sc-bczRLJ"]
                            for price_selector in price_selectors:
                                try:
                                    price_element = result.find_element(By.CSS_SELECTOR, price_selector)
                                    if price_element:
                                        price_text = price_element.text.strip()
                                        logger.info(f"[Meesho] Found price text: {price_text}")
                                        price = float(re.sub(r'[^\d.]', '', price_text))
                                        driver.quit()
                                        logger.info(f"[Meesho] Successfully extracted price: {price}")
                                        return price
                                except Exception as e:
                                    logger.debug(f"[Meesho] Price selector {price_selector} failed: {str(e)}")
                                    continue
                except Exception as e:
                    logger.debug(f"[Meesho] Product selector {selector} failed: {str(e)}")
                    continue
            driver.quit()
        except Exception as e:
            logger.error(f"[Meesho] Error with search term '{search_term}': {str(e)}")
            if 'driver' in locals():
                driver.quit()
            continue
    logger.error(f"[Meesho] No price found for product: {product_name}")
    return None

@app.get("/api/v1/products/fetch-price/")
async def fetch_price(url: str = Query(..., description="URL of the product to fetch price for")) -> Dict:
    try:
        product_name = extract_product_name_from_url(url)
        if not product_name:
            logger.error(f"[API] Could not extract product name from URL: {url}")
            raise HTTPException(status_code=400, detail="Could not extract product name from URL")
        product_name = product_name.replace('Amazon.in:', '').strip()
        product_name = re.sub(r'\b(by|from|on|in|at|the)\b', '', product_name, flags=re.IGNORECASE)
        product_name = ' '.join(product_name.split())
        logger.info(f"[API] Searching with product name: {product_name}")
        amazon_price = None
        try:
            amazon_data = await apify_scraper.fetch_product_price(url)
            amazon_price = amazon_data.get("current_price") if amazon_data else None
        except Exception as e:
            logger.error(f"[API] Apify scraping failed: {str(e)}. Trying direct scraping.")
            try:
                amazon_price, _ = fetch_amazon_price(product_name)
            except Exception as e2:
                logger.error(f"[API] Direct Amazon price fetch failed: {str(e2)}")
                amazon_price = None
        flipkart_price = fetch_flipkart_price(product_name)
        meesho_price = fetch_meesho_price(product_name)
        prices = {
            "amazon": amazon_price,
            "flipkart": flipkart_price,
            "meesho": meesho_price,
        }
        prices = {k: (v if v is not None else "Not found") for k, v in prices.items()}
        logger.info(f"[API] Final prices: {prices}")
        return {
            "product_name": product_name,
            "prices": prices,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"[API] Error in fetch_price: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class ProductAddRequest(BaseModel):
    product_name: str
    source: str

@app.post("/add-and-compare")
async def add_and_compare_product(
    data: ProductAddRequest,
    background_tasks: BackgroundTasks
):
    # Fetch prices from all platforms
    prices = {
        "amazon": fetch_amazon_price(data.product_name),
        "flipkart": fetch_flipkart_price(data.product_name),
        "meesho": fetch_meesho_price(data.product_name),
    }
    
    # Clean up prices (convert None to "Not found")
    prices = {k: (v if v is not None else "Not found") for k, v in prices.items()}
    
    comparison = {
        "product_name": data.product_name,
        "source": data.source,
        "prices": prices
    }
    background_tasks.add_task(product_service.save_price_comparison, comparison)
    return comparison

@app.post("/add-and-compare-others")
async def add_and_compare_others(
    data: ProductAddRequest
):
    all_prices = {
        "amazon": fetch_amazon_price(data.product_name),
        "flipkart": fetch_flipkart_price(data.product_name),
        "meesho": fetch_meesho_price(data.product_name),
    }
    other_prices = {site: price for site, price in all_prices.items() if site != data.source}
    comparison = {
        "product_name": data.product_name,
        "source": data.source,
        "other_prices": other_prices
    }
    await product_service.save_price_comparison(comparison)
    return comparison

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)