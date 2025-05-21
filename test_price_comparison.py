from price_extractor import PriceExtractor

def main():
    # Create an instance of PriceExtractor
    price_extractor = PriceExtractor()
    
    # Test URLs for different platforms
    test_urls = [
        "https://www.amazon.in/dp/B08KH7VF4Q",  # Example Amazon URL
        "https://www.flipkart.com/product/p/itm123",  # Example Flipkart URL
        "https://www.meesho.com/product/123"  # Example Meesho URL
    ]
    
    # Test each URL
    for url in test_urls:
        print(f"\nAnalyzing URL: {url}")
        results = price_extractor.get_product_details(url)
        
        # Print results for each platform
        for platform, details in results.items():
            print(f"\n{platform.upper()}:")
            print(f"Title: {details.get('title', 'N/A')}")
            print(f"Price: ₹{details.get('price', 'N/A')}")
        print("\n" + "="*50)

if __name__ == "__main__":
    main() 