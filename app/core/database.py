from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

db = Database()

async def connect_to_mongo():
    """Create database connection."""
    try:
        # Set a shorter server selection timeout
        db.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000  # 5 seconds timeout
        )
        
        # Verify the connection
        await db.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB.")
        
        # Set the database
        db.db = db.client[settings.MONGODB_DB_NAME]
        logger.info(f"Using database: {settings.MONGODB_DB_NAME}")
        
    except ConnectionFailure as e:
        logger.error(f"Could not connect to MongoDB: {str(e)}")
        logger.error("Please ensure MongoDB is running and the connection URL is correct.")
        raise
    except ServerSelectionTimeoutError as e:
        logger.error(f"Server selection timeout: {str(e)}")
        logger.error("MongoDB server is not responding. Please check if it's running.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
        raise

async def close_mongo_connection():
    """Close database connection."""
    try:
        if db.client:
            db.client.close()
            logger.info("Closed MongoDB connection.")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {str(e)}")
        raise

def get_database():
    """Get database instance."""
    if not db.db:
        raise Exception("Database not initialized. Please ensure connect_to_mongo() was called.")
    return db.db 