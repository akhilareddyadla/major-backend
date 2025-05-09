from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.auth import auth_service
from app.models.user import Token, User, UserCreate
import logging

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

logger = logging.getLogger(__name__)

# @router.post("/signup", response_model=User)
# async def signup(user: UserCreate):
#     """
#     Create a new user account.
#     """
#     return await auth_service.signup(user)

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    try:
        token = await auth_service.login(form_data.username, form_data.password)
        return token
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(auth_service.get_current_active_user)):
    """
    Get current user information.
    """
    return current_user

@router.get("/test-token", response_model=User)
async def test_token(current_user: User = Depends(auth_service.get_current_active_user)):
    """
    Test access token.
    """
    return current_user 