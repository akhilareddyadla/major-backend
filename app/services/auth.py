from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserCreate, UserInDB, Token, TokenPayload
from app.db.mongodb import get_collection, get_database
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

class AuthService:
    def __init__(self):
        self.db = None
        self.users_collection = None

    async def initialize(self):
        """Initialize the auth service."""
        self.db = get_database()
        self.users_collection = get_collection("users")
        logger.info("Auth service initialized")

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a new JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY, 
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

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
                user["id"] = str(user["_id"])
                user.pop("_id", None)
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
                user["id"] = str(user["_id"])
                user.pop("_id", None)
                return UserInDB(**user)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user"
            )

    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """Get a user by their username."""
        try:
            await self.initialize()
            user = await self.users_collection.find_one({"username": username})
            if user:
                user["id"] = str(user["_id"])
                user.pop("_id", None)
                return UserInDB(**user)
            return None
        except Exception as e:
            logger.error(f"Error getting user by username: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user"
            )

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user and return their data if valid."""
        try:
            user = await self.get_user_by_email(email)
            if not user:
                return None
            if not verify_password(password, user.hashed_password):
                return None
            return User(**user.model_dump(exclude={"hashed_password"}))
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            return None

    async def get_current_user(self, token: str = Depends(oauth2_scheme)) -> User:
        """Get the current user from the JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # Decode JWT token
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
            
            # Get user from database
            user = await self.get_user_by_id(user_id)
            if user is None:
                raise credentials_exception
                
            return user
            
        except JWTError:
            raise credentials_exception

    async def get_current_active_user(self, current_user: User = Depends(get_current_user)) -> User:
        """Get the current active user."""
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        return current_user

    async def login(self, email: str, password: str) -> Token:
        """Authenticate user and return access token using email and password."""
        try:
            # Get user by email
            user = await self.get_user_by_email(email)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if not verify_password(password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(
                data={"sub": str(user.id)},
                expires_delta=access_token_expires
            )
            
            return Token(access_token=access_token, token_type="bearer")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login process failed"
            )

    async def signup(self, user: UserCreate) -> User:
        """Create a new user account."""
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
            # Fetch the user back from the DB to ensure _id is present and is a string
            user_db = await self.users_collection.find_one({"_id": result.inserted_id})
            if user_db:
                user_db["_id"] = str(user_db["_id"])
                if "hashed_password" in user_db:
                    user_db.pop("hashed_password")
                return User(**user_db)
            else:
                raise HTTPException(status_code=500, detail="User creation failed")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Signup process failed"
            )

    async def oauth_login(self, email: str, name: str = None, provider: str = None) -> Token:
        await self.initialize()
        user_data = await self.users_collection.find_one({"email": email})

        if not user_data:
            # Create a new user for social login
            user_dict = {
                "email": email,
                "username": email.split("@")[0],
                "hashed_password": None,  # No password for social login
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True,
                "is_superuser": False,
                "is_oauth": True,
                "oauth_provider": provider
            }
            result = await self.users_collection.insert_one(user_dict)
            user_id = str(result.inserted_id)
        else:
            user_id = str(user_data.get("_id"))

        # Generate JWT token with user ID as subject
        access_token_expires = timedelta(minutes=60*24*7)  # 1 week
        access_token = self.create_access_token(
            data={"sub": user_id},
            expires_delta=access_token_expires
        )
        return Token(access_token=access_token, token_type="bearer")

# Create auth service instance
auth_service = AuthService()

async def get_user_by_email(email: str) -> Optional[UserInDB]:
    try:
        user_collection = get_collection("users")
        user = await user_collection.find_one({"email": email})
        if user is not None:
            return UserInDB(**user)
        return None
    except Exception as e:
        logging.error(f"Error in get_user_by_email: {str(e)}")
        raise

async def get_user_by_username(username: str) -> Optional[UserInDB]:
    try:
        user_collection = get_collection("users")
        user = await user_collection.find_one({"username": username})
        if user is not None:
            return UserInDB(**user)
        return None
    except Exception as e:
        logging.error(f"Error in get_user_by_username: {str(e)}")
        raise

async def create_user(user: UserCreate) -> UserInDB:
    logging.info(f"Starting user creation process for {user.email}")
    try:
        user_collection = get_collection("users")
        logging.info("Got users collection")
        
        # Check if user already exists
        logging.info("Checking for existing email...")
        existing_email_user = await get_user_by_email(user.email)
        if existing_email_user is not None:
            logging.warning(f"Email {user.email} already registered")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        logging.info("Checking for existing username...")
        existing_username_user = await get_user_by_username(user.username)
        if existing_username_user is not None:
            logging.warning(f"Username {user.username} already taken")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create new user
        logging.info("Creating new user document...")
        user_dict = user.model_dump(exclude={"password"})
        user_dict.update({
            "id": str(ObjectId()),
            "hashed_password": get_password_hash(user.password),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "is_superuser": False
        })
        
        logging.info("Inserting user into database...")
        logging.debug(f"User document to insert: {user_dict}")
        result = await user_collection.insert_one(user_dict)
        if result.inserted_id:
            logging.info(f"Successfully created user {user.username}")
            return UserInDB(**user_dict)
        else:
            raise Exception("Failed to insert user into database")
    except Exception as e:
        logging.error(f"Error in create_user: {str(e)}")
        logging.exception("Full error traceback:")
        raise

async def authenticate_user(email: str, password: str):
    """Authenticate a user using the auth service."""
    return await auth_service.authenticate_user(email, password)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get the current user using the auth service."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
            
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise credentials_exception
            
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current active user using the auth service."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def verify_token(token: str) -> str:
    """Verify a JWT token and return the user ID."""
    try:
        logger.info("Starting token verification...")
        logger.debug(f"Token to verify: {token[:20]}...")

        # Decode the token
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            logger.info("Token decoded successfully")
        except jwt.ExpiredSignatureError:
            logger.error("Token has expired")
            return None
        except jwt.JWTError as e:
            logger.error(f"JWT decode error: {str(e)}")
            return None
        
        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            logger.error("No user ID found in token payload")
            return None
            
        logger.info(f"Found user_id in token: {user_id}")
            
        # Verify user exists
        try:
            # Initialize auth service if needed
            if auth_service.users_collection is None:
                await auth_service.initialize()
                
            # Convert string ID to ObjectId
            try:
                object_id = ObjectId(user_id)
            except Exception as e:
                logger.error(f"Invalid ObjectId format: {user_id}")
                return None

            # Find user in database
            user = await auth_service.users_collection.find_one({"_id": object_id})
            if user is None:
                logger.error(f"User not found in database: {user_id}")
                return None
                
            # Check if user is active
            if not user.get("is_active", False):
                logger.error(f"User is not active: {user_id}")
                return None
                
            logger.info(f"User verified successfully: {user_id}")
            return user_id
            
        except Exception as e:
            logger.error(f"Error verifying user: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return None 