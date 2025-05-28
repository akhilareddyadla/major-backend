from price_extractor import PriceExtractor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_flipkart_search():
    # Test cases for Whirlpool refrigerators
    test_cases = [
        "Whirlpool 184 L 2 Star Direct-Cool Single Door Refrigerator (205 WDE CLS 2S SAPPHIRE BLUE-Z, Blue,2023 Model)",
        "Whirlpool 205 WDE CLS 2S",
        "Whirlpool 184L Direct Cool Refrigerator",
        "Whirlpool 184L 2 Star Refrigerator"
    ]
    
    extractor = None
    try:
        extractor = PriceExtractor()
        
        for test_case in test_cases:
            logger.info(f"\nTesting search term: {test_case}")
            result = extractor._search_flipkart(test_case)
            logger.info(f"Search result: {result}")
            
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
    finally:
        if extractor:
            extractor.cleanup()

if __name__ == "__main__":
    test_flipkart_search() 