from datetime import datetime
from typing import List, Optional
from app.models.user_profile import UserProfile, UserProfileUpdate, WatchlistItem, InteractionHistory
from app.core.database import get_database, connect_to_mongo
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class UserProfileService:
    def __init__(self):
        self.db = None
        self.collection = None

    async def _ensure_db_connection(self):
        """Ensure database connection is established."""
        if not self.db:
            try:
                await connect_to_mongo()
                self.db = get_database()
                self.collection = self.db.user_profiles
            except Exception as e:
                logger.error(f"Error connecting to database: {str(e)}")
                raise

    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by user ID."""
        try:
            await self._ensure_db_connection()
            profile_data = await self.collection.find_one({"user_id": user_id})
            if profile_data:
                profile_data["_id"] = str(profile_data["_id"])
                return UserProfile(**profile_data)
            return None
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise

    async def create_user_profile(self, user_profile: UserProfile) -> UserProfile:
        """Create a new user profile."""
        try:
            await self._ensure_db_connection()
            profile_dict = user_profile.dict()
            profile_dict["created_at"] = datetime.utcnow()
            profile_dict["updated_at"] = datetime.utcnow()
            
            result = await self.collection.insert_one(profile_dict)
            profile_dict["_id"] = str(result.inserted_id)
            
            return UserProfile(**profile_dict)
        except Exception as e:
            logger.error(f"Error creating user profile: {str(e)}")
            raise

    async def update_user_profile(self, user_id: str, profile_update: UserProfileUpdate) -> Optional[UserProfile]:
        """Update user profile."""
        try:
            await self._ensure_db_connection()
            update_data = profile_update.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return await self.get_user_profile(user_id)
            return None
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise

    async def add_to_watchlist(self, user_id: str, watchlist_item: WatchlistItem) -> Optional[UserProfile]:
        """Add item to user's watchlist."""
        try:
            await self._ensure_db_connection()
            result = await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$push": {"watchlist": watchlist_item.dict()},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return await self.get_user_profile(user_id)
            return None
        except Exception as e:
            logger.error(f"Error adding to watchlist: {str(e)}")
            raise

    async def remove_from_watchlist(self, user_id: str, product_id: str) -> Optional[UserProfile]:
        """Remove item from user's watchlist."""
        try:
            await self._ensure_db_connection()
            result = await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$pull": {"watchlist": {"product_id": product_id}},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return await self.get_user_profile(user_id)
            return None
        except Exception as e:
            logger.error(f"Error removing from watchlist: {str(e)}")
            raise

    async def update_interaction_history(self, user_id: str, interaction_type: str, item_id: str) -> Optional[UserProfile]:
        """Update user's interaction history."""
        try:
            await self._ensure_db_connection()
            update_field = f"interaction_history.{interaction_type}"
            result = await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$push": {update_field: item_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return await self.get_user_profile(user_id)
            return None
        except Exception as e:
            logger.error(f"Error updating interaction history: {str(e)}")
            raise

# Create service instance
user_profile_service = UserProfileService() 