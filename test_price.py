from price_extractor import PriceExtractor

def main():
    url = 'https://www.amazon.in/POCO-C75-Aqua-Bliss-64GB/dp/B0DRKNZFT2/ref=sr_1_1?crid=1BOLMHLPCPDBJ&dib=eyJ2IjoiMSJ9.J0yEy1v4gx4YCferjVs5YQbQL9m9VLp2jq6Aw8tn7tXoIbqjle5PXJYkcZSWnmdI889Om4c8wieroTVBjkJXvcmp8PoNlUbCqnDOUQ9u1aOvDJlQ2G1hvD3zzszyODPbzcEndEMX0QHnshoDy4EjE7uy-O4PdeE_m3pdG2tRnkAO1Dw02FiLNwnLDNQl6RPLcXFFA2JLoE9p2phCP8zkNbtykIfvsMwov_o3Z3lv2Tg.3gjX4Vs8hBAXLGPRe-yIir3OjYoU0uQTRfAaNIqyTr8&dib_tag=se&keywords=poco&nsdOptOutParam=true&qid=1748366368&sprefix=poco%2Caps%2C239&sr=8-1&th=1'
    extractor = PriceExtractor()
    result = extractor.get_product_details(url)
    print("Result:", result)

if __name__ == "__main__":
    main() 