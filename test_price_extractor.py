import asyncio
import logging
from app.services.price_extractor import PriceExtractor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_price_extraction():
    extractor = PriceExtractor()
    try:
        # Test URL
        url = "https://www.amazon.in/Whirlpool-265-Litre-Direct-Cool-Refrigerator/dp/B0B4N6JQFB"
        
        # Get product details
        title, prices = await extractor.get_product_details(url)
        
        # Print results
        logger.info(f"Product Title: {title}")
        logger.info(f"Prices: {prices}")
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
    finally:
        # Clean up resources
        extractor.cleanup()

if __name__ == "__main__":
    asyncio.run(test_price_extraction()) 