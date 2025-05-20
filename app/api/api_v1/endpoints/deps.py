from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings
from app.models.user import User
from app.services.auth import auth_service
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        logging.error("No token provided")
        raise credentials_exception

    try:
        logging.info(f"Validating token: {token[:10]}...")
        
        # Decode the token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        logging.info(f"Token decoded successfully")
        
        # Extract user ID from payload
        user_id: str = payload.get("sub")
        if not user_id:
            logging.error("Token payload missing user ID")
            raise credentials_exception
        
        logging.info(f"Looking up user: {user_id}")
        
        # Get user from database
        user = await auth_service.get_user_by_id(user_id)
        if not user:
            logging.error(f"User not found in database: {user_id}")
            raise credentials_exception
        
        if not user.is_active:
            logging.error(f"User is inactive: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        logging.info(f"Authentication successful for user: {user_id}")
        return user
            
    except JWTError as e:
        logging.error(f"JWT validation error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        raise credentials_exception 