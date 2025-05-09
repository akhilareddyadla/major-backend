from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging
import asyncio
from typing import Optional
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# MongoDB client
client = None
db = None

async def try_connect(max_retries: int = 5, retry_delay: int = 2) -> bool:
    """Try to connect to MongoDB with retries."""
    global client, db
    for attempt in range(max_retries):
        try:
            logger.info(f"MongoDB connection attempt {attempt + 1} of {max_retries}")
            logger.info(f"Connecting to: {settings.MONGODB_URL}")
            
            if client is None:
                client = AsyncIOMotorClient(
                    settings.MONGODB_URL,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000
                )
            
            # Test the connection
            await client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Initialize the database
            db = client[settings.MONGODB_DB_NAME]
            logger.info(f"Using database: {settings.MONGODB_DB_NAME}")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if client:
                try:
                    client.close()
                except:
                    pass
                client = None
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("All connection attempts failed")
            
    return False

async def connect_to_mongo():
    """Connect to MongoDB and initialize collections."""
    global client, db
    logger.info("Starting MongoDB connection...")
    
    try:
        connected = await try_connect()
        if not connected:
            raise Exception("Failed to connect to MongoDB after multiple attempts")
        
        # Ensure collections exist
        collections = [
            "users",
            "products",
            "alert_preferences",
            "price_drop_alerts",
            "discount_alerts",
            "price_history"
        ]
        
        for collection in collections:
            if collection not in await db.list_collection_names():
                logger.info(f"Creating collection: {collection}")
                await db.create_collection(collection)
        
        # Create indexes
        await db.products.create_index([("user_id", 1)])
        await db.products.create_index([("created_at", -1)])
        await db.products.create_index([("is_favorite", 1)])
        
        logger.info("MongoDB connection and setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during MongoDB connection: {str(e)}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")

def get_database():
    """Get database instance."""
    global db
    if db is None:
        raise Exception("MongoDB database not initialized")
    return db

def get_collection(collection_name: str):
    """Get collection instance."""
    global db
    if db is None:
        raise Exception("MongoDB database not initialized")
    return db[collection_name] 