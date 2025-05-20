import logging
from apify_client import ApifyClient
from fastapi import HTTPException
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ApifyAmazonScraper:
    def __init__(self, api_token: str):
        """Initialize the Apify Amazon scraper with API token."""
        self.client = ApifyClient(api_token)
        logger.info("ApifyAmazonScraper initialized")

    async def fetch_product_price(self, product_url: str) -> Dict[str, Any]:
        """
        Fetch product price and details from Amazon using Apify.
        
        Args:
            product_url (str): The Amazon product URL to scrape
            
        Returns:
            Dict[str, Any]: Product details including price, title, etc.
            
        Raises:
            HTTPException: If scraping fails or product not found
        """
        try:
            logger.info(f"Starting Apify scrape for URL: {product_url}")
            
            run_input = {
                "categoryOrProductUrls": [{"url": product_url}],
                "maxItemsPerStartUrl": 1,
                "proxyCountry": "US",
                "maxOffers": 0
            }
            
            run = self.client.actor("junglee/amazon-crawler").call(run_input=run_input)
            
            if not run:
                logger.error("Apify run failed - no run data returned")
                raise HTTPException(status_code=500, detail="Apify run failed")
                
            dataset = self.client.dataset(run["defaultDatasetId"]).iterate_items()
            
            for item in dataset:
                result = {
                    "asin": item.get("asin"),
                    "title": item.get("title"),
                    "current_price": item.get("price", {}).get("value"),
                    "currency": item.get("price", {}).get("currency"),
                    "url": item.get("url")
                }
                logger.info(f"Successfully scraped product: {result['title']}")
                return result
                
            logger.warning(f"No product data found for URL: {product_url}")
            raise HTTPException(status_code=404, detail="Product not found")
            
        except Exception as e:
            logger.error(f"Error during Apify scraping: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}") 