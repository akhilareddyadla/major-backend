from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.models.user import User, UserCreate, Token, UserSignup
from app.services.auth import auth_service
from app.api.deps import oauth2_scheme
import logging
from pydantic import BaseModel, EmailStr
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        user = await auth_service.get_current_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.post("/signup", response_model=None)
async def signup(user: UserSignup):
    """
    Create a new user account.
    """
    # Validate passwords match (already handled by Pydantic)
    user_create = UserCreate(
        email=user.email,
        username=user.username,
        password=user.password
    )
    try:
        logging.info(f"Attempting to create user with email: {user.email}")
        db_user = await auth_service.signup(user_create)
        logging.info(f"Successfully created user: {user.email}")
        
        # Return success response with redirect URL
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "User created successfully",
                "redirect_url": "/api/v1/auth/login",
                "user": {
                    "username": db_user.username,
                    "email": db_user.email
                }
            }
        )
    except HTTPException as e:
        logging.error(f"HTTP error during user creation: {str(e)}")
        raise e
    except Exception as e:
        logging.error(f"Unexpected error during user creation: {str(e)}")
        logging.exception("Full error traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """
    Login endpoint that accepts email and password.
    """
    try:
        logging.info(f"Login request received for email: {login_data.email}")
        token = await auth_service.login(login_data.email, login_data.password)
        
        # Return token with additional user info
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "access_token": token.access_token,
                "token_type": token.token_type,
                "message": "Login successful"
            }
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/token", response_model=Token)
async def login_token(login_data: LoginRequest):
    """
    Alias for login endpoint to maintain compatibility with OAuth2 standard.
    """
    try:
        logging.info(f"Token request received for email: {login_data.email}")
        token = await auth_service.login(login_data.email, login_data.password)
        
        # Return token with additional user info
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "access_token": token.access_token,
                "token_type": token.token_type,
                "message": "Login successful"
            }
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    try:
        logger.info(f"Accessing user info for: {current_user.email}")
        
        # Convert user to dict and ensure all required fields are present
        user_dict = current_user.model_dump()
        
        # Ensure id is present and properly formatted
        if "_id" in user_dict:
            user_dict["id"] = str(user_dict.pop("_id"))
        elif "id" not in user_dict:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User ID is missing"
            )
            
        # Ensure all required fields are present
        required_fields = ["email", "username", "is_active", "created_at", "updated_at"]
        for field in required_fields:
            if field not in user_dict:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Required field {field} is missing"
                )
                
        # Convert datetime objects to ISO format strings
        for key, value in list(user_dict.items()):
            if isinstance(value, datetime):
                user_dict[key] = value.isoformat()
                
        return user_dict
        
    except Exception as e:
        logger.error(f"Error fetching user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user info: {str(e)}"
        ) 