from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import User, UserUpdate
from app.api.api_v1.endpoints.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information."""
    return current_user

@router.put("/me", response_model=User)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update current user information."""
    try:
        # Update user logic here
        # For now, just return the current user
        return current_user
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 