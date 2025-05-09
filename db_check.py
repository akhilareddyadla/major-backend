import asyncio
import logging
from app.db.mongodb import connect_to_mongo, get_database

async def check_db():
    try:
        print("Connecting to MongoDB...")
        await connect_to_mongo()
        
        print("Getting database connection...")
        db = get_database()
        
        print("Retrieving products...")
        products = await db["products"].find().to_list(10)
        
        print(f"Found {len(products)} products:")
        for product in products:
            product["_id"] = str(product["_id"])  # Convert ObjectId to string
            print(f"- {product.get('name', 'Unknown')} | ID: {product['_id']} | Price: {product.get('current_price', 'N/A')}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        logging.error(f"Database check error: {str(e)}")

if __name__ == "__main__":
    print("Starting database check...")
    asyncio.run(check_db())
    print("Database check complete.") 