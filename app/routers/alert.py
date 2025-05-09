from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Union, Optional
from app.models.product import AlertPreference, AlertType, PriceDropAlert, DiscountAlert, Alert
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
    alert_preference: AlertPreference,
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Create a new alert preference for the current user.
    This endpoint allows users to set up alerts for price drops or discounts.
    """
    try:
        # Ensure the alert is created for the current user
        alert_preference.user_id = str(current_user.id)
        
        # Create the alert preference
        result = await alert_service.create_alert_preference(
            user_id=alert_preference.user_id,
            product_id=alert_preference.product_id,
            alert_type=alert_preference.alert_type,
            threshold_price=alert_preference.threshold_price,
            percentage_drop=alert_preference.percentage_drop,
            notification_channels=alert_preference.notification_channels,
            frequency=alert_preference.frequency,
            custom_message=alert_preference.custom_message
        )
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logging.error(f"Error creating alert preference: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert preference"
        )

@router.get("/{id}", response_model=Union[PriceDropAlert, DiscountAlert])
async def get_alert(
    id: str,
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Get alert details by ID.
    This endpoint returns either a price drop alert or discount alert based on the ID.
    """
    try:
        # Try to get from price_drop_alerts first
        alert = await alert_service.price_drop_alerts.find_one({"_id": ObjectId(id)})
        
        # If not found in price_drop_alerts, try discount_alerts
        if not alert:
            alert = await alert_service.discount_alerts.find_one({"_id": ObjectId(id)})
            
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
            
        # Check if the alert belongs to the current user
        if alert.get("user_id") != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this alert"
            )
            
        # Convert ObjectId to string for JSON serialization
        alert["id"] = str(alert["_id"])
        
        # Determine alert type and return appropriate model
        if "percentage_drop" in alert:
            return PriceDropAlert(**alert)
        else:
            return DiscountAlert(**alert)
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid alert ID format"
        )
    except Exception as e:
        logging.error(f"Error retrieving alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert"
        )

@router.get("/user", response_model=List[dict])
async def get_user_alerts(
    alert_type: Optional[AlertType] = None,
    is_read: Optional[bool] = None,
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Get alerts for the current user.
    This endpoint returns all alerts that belong to the authenticated user.
    Optional filters can be applied for alert type and read status.
    """
    try:
        alerts = await alert_service.get_user_alerts(
            user_id=str(current_user.id),
            alert_type=alert_type,
            is_read=is_read,
            limit=limit,
            skip=skip
        )
        
        return alerts
    except Exception as e:
        logging.error(f"Error retrieving user alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        ) 