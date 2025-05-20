import logging
import motor.motor_asyncio
from app.core.config import settings
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

# MongoDB client instance
client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None

async def connect_to_mongo():
    """Connect to MongoDB."""
    global client, db
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"MongoDB connection attempt {attempt} of {max_retries}")
            
            # Get MongoDB URL and database name from settings
            mongodb_url = settings.get_mongodb_url()
            database_name = settings.DATABASE_NAME
            
            logger.info(f"Connecting to: {mongodb_url}")
            
            # Create MongoDB client
            client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
            
            # Test the connection
            await client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            # Set the database
            db = client[database_name]
            logger.info(f"Using database: {database_name}")
            
            return
            
        except Exception as e:
            logger.error(f"Connection attempt {attempt} failed: {str(e)}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("All connection attempts failed")
                raise Exception("Failed to connect to MongoDB after multiple attempts")

async def close_mongo_connection():
    """Close MongoDB connection."""
    global client
    if client is not None:
        client.close()
        logger.info("MongoDB connection closed")

def get_database():
    """Get database instance."""
    if db is None:
        raise Exception("Database not initialized. Call connect_to_mongo() first.")
    return db

def get_collection(collection_name: str):
    """Get collection instance."""
    if db is None:
        raise Exception("Database not initialized. Call connect_to_mongo() first.")
    return db[collection_name] 