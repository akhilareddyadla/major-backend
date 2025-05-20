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
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

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
            # Get the product URL
            product_link = result.find("a", {"class": "a-link-normal s-no-outline"})
            if product_link and 'href' in product_link.attrs:
                product_url = "https://www.amazon.in" + product_link['href']
                # Use the price extractor to get the current price
                return price_extractor.get_current_price(product_url)
        
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
            if product_link and 'href' in product_link.attrs:
                product_url = "https://www.amazon.in" + product_link['href']
                return price_extractor.get_current_price(product_url)
                
        logger.error("[Amazon] No product found. HTML snippet: %s", soup.prettify()[:1000])
        return None
    except Exception as e:
        logger.error("[Amazon] Error fetching price: %s", str(e))
        return None

def fetch_flipkart_price(product_name: str):
    search_url = f"https://www.flipkart.com/search?q={product_name.replace(' ', '+')}"
    try:
        driver = get_selenium_driver()
        driver.get(search_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div._1AtVbE"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        result = soup.find("div", {"class": "_1AtVbE col-12-12"})
        if result:
            price_tag = result.find("div", {"class": "_30jeq3"})
            if price_tag:
                return float(price_tag.text.replace("₹", "").replace(",", "").strip())
        logger.error("[Flipkart] No price found. HTML snippet: %s", soup.prettify()[:1000])
        return None
    except Exception as e:
        logger.error("[Flipkart] Error fetching price: %s", str(e))
        return None

def fetch_meesho_price(product_name: str):
    search_url = f"https://www.meesho.com/search?q={product_name.replace(' ', '%20')}"
    try:
        driver = get_selenium_driver()
        driver.get(search_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.sc-gswNZR"))
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        result = soup.find("div", {"class": "sc-gswNZR"})
        if result:
            price_tag = result.find("h5")
            if price_tag:
                return float(price_tag.text.replace("₹", "").replace(",", "").strip())
        logger.error("[Meesho] No price found. HTML snippet: %s", soup.prettify()[:1000])
        return None
    except Exception as e:
        logger.error("[Meesho] Error fetching price: %s", str(e))
        return None

@app.get("/compare-prices")
async def compare_prices(product_name: str = Query(..., description="Name of the product to compare")) -> Dict:
    try:
        # Try Apify first for Amazon
        amazon_url = f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}"
        amazon_data = await apify_scraper.fetch_product_price(amazon_url)
        amazon_price = amazon_data.get("current_price") if amazon_data else None
    except Exception as e:
        logger.error(f"Apify scraping failed: {str(e)}")
        amazon_price = fetch_amazon_price(product_name)

    prices = {
        "amazon": amazon_price,
        "flipkart": fetch_flipkart_price(product_name),
        "meesho": fetch_meesho_price(product_name),
    }
    
    return {
        "product_name": product_name,
        "prices": prices,
        "timestamp": time.time()
    }

class ProductAddRequest(BaseModel):
    product_name: str
    source: str

@app.post("/add-and-compare")
async def add_and_compare_product(
    data: ProductAddRequest,
    background_tasks: BackgroundTasks
):
    prices = {
        "amazon": fetch_amazon_price(data.product_name),
        "flipkart": fetch_flipkart_price(data.product_name),
        "meesho": fetch_meesho_price(data.product_name),
    }
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