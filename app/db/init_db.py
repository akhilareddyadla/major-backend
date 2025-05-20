import logging
from app.db.mongodb import get_database

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize the database with required collections and indexes."""
    try:
        db = get_database()
        
        # List of required collections
        collections = [
            "users",
            "products",
            "alerts",
            "notifications",
            "price_history"
        ]
        
        # Create collections if they don't exist
        existing_collections = await db.list_collection_names()
        for collection in collections:
            if collection not in existing_collections:
                logger.info(f"Creating collection: {collection}")
                await db.create_collection(collection)
        
        # Create indexes
        # Users collection indexes
        await db.users.create_index([("email", 1)], unique=True)
        await db.users.create_index([("username", 1)], unique=True)
        
        # Products collection indexes
        await db.products.create_index([("user_id", 1)])
        await db.products.create_index([("created_at", -1)])
        await db.products.create_index([("is_favorite", 1)])
        await db.products.create_index([("is_active", 1)])
        
        # Alerts collection indexes
        await db.alerts.create_index([("user_id", 1)])
        await db.alerts.create_index([("product_id", 1)])
        await db.alerts.create_index([("is_active", 1)])
        
        # Notifications collection indexes
        await db.notifications.create_index([("user_id", 1)])
        await db.notifications.create_index([("created_at", -1)])
        await db.notifications.create_index([("is_read", 1)])
        
        # Price history collection indexes
        await db.price_history.create_index([("product_id", 1)])
        await db.price_history.create_index([("timestamp", -1)])
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise 