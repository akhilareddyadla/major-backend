from fastapi import APIRouter, Depends, HTTPException, status
from app.models.product import AlertPreference, PriceDropAlert
from app.services.alerts import alert_service
from app.db.mongodb import get_database
from app.services.auth import get_current_active_user
from app.models.user import User
from bson import ObjectId
import logging

router = APIRouter(prefix="/alerts", tags=["alerts"])

async def get_db():
    return get_database()

@router.post("/", response_model=AlertPreference)
async def create_alert(
    pref: AlertPreference, 
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """Create a new alert preference."""
    try:
        # Override user_id with authenticated user for security
        return await alert_service.create_alert_preference(
            user_id=str(current_user.id),
            product_id=pref.product_id,
            alert_type=pref.alert_type,
            threshold_price=pref.threshold_price,
            percentage_drop=pref.percentage_drop
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error creating alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create alert")

@router.get("/{id}", response_model=PriceDropAlert)
async def get_alert(
    id: str, 
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """Get a price drop alert by ID."""
    try:
        alert = await alert_service.price_drop_alerts.find_one({"_id": ObjectId(id)})
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        # Ensure alert belongs to the current user
        if alert.get("user_id") != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this alert"
            )
            
        alert["id"] = str(alert["_id"])
        return PriceDropAlert(**alert)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
    except Exception as e:
        logging.error(f"Error retrieving alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert") 