from typing import Optional, List
from app.models.user import User, UserCreate, UserUpdate, UserInDB
from app.db.mongodb import get_collection, get_database
from app.core.security import get_password_hash
from datetime import datetime
import logging
from bson import ObjectId
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self):
        self.db = None
        self.users_collection = None

    async def initialize(self):
        """Initialize the user service."""
        self.db = get_database()
        self.users_collection = get_collection("users")
        logger.info("User service initialized")

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by their ID."""
        try:
            await self.initialize()
            try:
                object_id = ObjectId(user_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user ID format: {user_id}"
                )
                
            user = await self.users_collection.find_one({"_id": object_id})
            if user:
                return User(**user)
            return None
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user"
            )

    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by their email."""
        try:
            await self.initialize()
            user = await self.users_collection.find_one({"email": email})
            if user:
                return UserInDB(**user)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user"
            )

    async def create_user(self, user: UserCreate) -> User:
        """Create a new user."""
        try:
            await self.initialize()
            
            # Check if user already exists
            existing_user = await self.get_user_by_email(user.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            # Create new user
            user_dict = user.model_dump(exclude={"password"})
            user_dict.update({
                "hashed_password": get_password_hash(user.password),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True,
                "is_superuser": False
            })

            result = await self.users_collection.insert_one(user_dict)
            user_dict["id"] = str(result.inserted_id)
            
            return User(**user_dict)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )

    async def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        """Update a user's information."""
        try:
            await self.initialize()
            
            # Check if user exists
            existing_user = await self.get_user_by_id(user_id)
            if not existing_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Prepare update data
            update_data = user_update.model_dump(exclude_unset=True)
            if "password" in update_data:
                update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
            update_data["updated_at"] = datetime.utcnow()

            # Update user
            result = await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User update failed"
                )
                
            return await self.get_user_by_id(user_id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating user"
            )

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        try:
            await self.initialize()
            
            result = await self.users_collection.delete_one({"_id": ObjectId(user_id)})
            if result.deleted_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
                
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting user"
            )

    async def get_all_users(self) -> List[User]:
        """Get all users."""
        try:
            await self.initialize()
            users = []
            async for user in self.users_collection.find():
                users.append(User(**user))
            return users
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving users"
            )

# Create user service instance
user_service = UserService() 