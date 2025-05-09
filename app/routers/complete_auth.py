from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User, UserCreate, Token
from app.services.auth import authenticate_user, create_access_token, get_current_user
from app.services.users import user_service
from app.core.config import settings
from datetime import timedelta
import logging

router = APIRouter(prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])

@router.post("/register", response_model=User)
async def register(user: UserCreate):
    """
    Register a new user.
    Returns the created user without sensitive information.
    """
    try:
        # Use user_service to create the user
        db_user = await user_service.create_user(user)
        
        # Convert to User model (without sensitive data)
        return User(
            id=db_user.id,
            email=db_user.email,
            username=db_user.username,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
            is_active=db_user.is_active,
            is_superuser=db_user.is_superuser
        )
    except ValueError as e:
        # Handle validation errors
        logging.warning(f"Registration validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Handle unexpected errors
        logging.error(f"Failed to register user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login.
    Returns an access token for future authenticated requests.
    """
    try:
        # Authenticate user
        user = await authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token with configured expiration
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},  # Use user ID, not username
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logging.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login process failed"
        )

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get information about the currently logged in user.
    This endpoint requires authentication.
    """
    return current_user 