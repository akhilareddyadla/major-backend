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
            
            # Replace with your actual Actor ID if different, e.g., "apify/amazon-scraper"
            # You can find the Actor ID in the URL of the Actor on Apify Console
            # Example: https://console.apify.com/actors/YOUR_ACTOR_ID
            # Using a common Amazon scraper Actor ID here:
            actor_id = "apify/amazon-scraper" # Using the official Apify Amazon Scraper Actor ID

            run = await self.client.actor(actor_id).call(run_input=run_input)
            
            if not run:
                logger.error("Apify run failed - no run data returned")
                raise HTTPException(status_code=500, detail="Apify run failed")
                
            # Wait for the run to finish and get the dataset items
            # The .call() method already waits for the run to finish by default
            # but we might need to explicitly wait or handle large datasets differently later if needed.
            # For a single item scrape, iterating the dataset after .call() is fine.
            dataset = self.client.dataset(run["defaultDatasetId"])
            
            # Fetch all items from the dataset
            all_items = []
            async for item in dataset.iterate_items():
                 all_items.append(item)

            if not all_items:
                logger.warning(f"No product data found for URL: {product_url}")
                raise HTTPException(status_code=404, detail="Product not found")
                
            # Assuming we expect only one item for a product URL
            item = all_items[0]

            result = {
                "asin": item.get("asin"),
                "title": item.get("title"),
                "current_price": item.get("price", {}).get("value"),
                "currency": item.get("price", {}).get("currency"),
                "url": item.get("url"),
                "is_available": item.get("isAvailable", True) # Default to True if not provided
            }
            logger.info(f"Successfully scraped product: {result.get('title','N/A')} with price {result.get('current_price','N/A')}")
            return result
                
        except Exception as e:
            logger.error(f"Error during Apify scraping for {product_url}: {str(e)}", exc_info=True)
            # Re-raise as HTTPException to be handled by FastAPI
            raise HTTPException(status_code=500, detail=f"Apify scraping error for {product_url}: {str(e)}")

# Example Usage (for testing)
# async def main():
#     # Replace with your Apify API token
#     APIFY_API_TOKEN = "YOUR_APIFY_API_TOKEN"
#     if APIFY_API_TOKEN == "YOUR_APIFY_API_TOKEN":
#         print("Please replace YOUR_APIFY_API_TOKEN with your actual Apify API token.")
#         return

#     scraper = ApifyAmazonScraper(api_token=APIFY_API_TOKEN)
#     test_url = "https://www.amazon.in/OnePlus-Nord-CE-5G-Charcoal/dp/B095GT4BQ9/"
#     try:
#         details = await scraper.fetch_product_price(test_url)
#         print(f"Details for {test_url}:")
#         print(details)
#     except HTTPException as e:
#         print(f"Error scraping {test_url}: {e.detail}")

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main()) 