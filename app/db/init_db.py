from app.db.mongodb import get_collection, get_database
import logging

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize database with required indexes."""
    try:
        # Get database instance
        db = get_database()
        
        # Define collections and their indexes
        collections_config = {
            "price_history": [
                {"keys": [("product_id", 1)]},
                {"keys": [("timestamp", -1)]},
                {"keys": [("product_id", 1), ("timestamp", -1)]}
            ],
            "products": [
                {"keys": [("user_id", 1)]},
                {"keys": [("created_at", -1)]},
                {"keys": [("is_favorite", 1)]}
            ],
            "users": [
                {"keys": [("email", 1)], "unique": True},
                {"keys": [("username", 1)], "unique": True}
            ]
        }
        
        # Create collections and indexes
        for collection_name, indexes in collections_config.items():
            collection = get_collection(collection_name)
            for index_spec in indexes:
                keys = index_spec["keys"]
                options = {k: v for k, v in index_spec.items() if k != "keys"}
                await collection.create_index(keys, **options)
                logger.info(f"Created index {keys} for collection {collection_name}")
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating database indexes: {str(e)}")
        raise 