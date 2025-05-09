from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from app.models.product import AlertPreference, PriceDropAlert, DiscountAlert, AlertPreferenceCreate, AlertPreferenceUpdate
from app.models.product import AlertType
from app.services.alerts import alert_service, AlertService
from app.api.deps import get_current_user
from app.models.user import User
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
alert_service = AlertService()

@router.post("/preferences", response_model=AlertPreference)
async def create_alert_preference(
    alert_preference: AlertPreferenceCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new alert preference."""
    try:
        return await alert_service.create_alert_preference(
            user_id=str(current_user.id),
            alert_preference=alert_preference
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/preferences", response_model=List[AlertPreference])
async def get_alert_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get alert preferences for the current user."""
    try:
        return await alert_service.get_alert_preferences(str(current_user.id))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/preferences/{alert_id}", response_model=AlertPreference)
async def get_alert_preference(
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        alert = await alert_service.get_alert_preference(alert_id)
        if not alert or alert.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert preference not found"
            )
        return alert
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/preferences/{alert_id}", response_model=AlertPreference)
async def update_alert_preference(
    alert_id: str,
    alert_update: AlertPreferenceUpdate,
    current_user: User = Depends(get_current_user)
):
    try:
        alert = await alert_service.get_alert_preference(alert_id)
        if not alert or alert.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert preference not found"
            )
        return await alert_service.update_alert_preference(alert_id, alert_update)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/preferences/{alert_id}")
async def delete_alert_preference(
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete an alert preference."""
    try:
        alert = await alert_service.get_alert_preference(alert_id)
        if not alert or alert.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert preference not found"
            )

        await alert_service.delete_alert_preference(alert_id)
        return {"message": "Alert preference deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/alerts", response_model=List[dict])
async def get_alerts(
    current_user: User = Depends(get_current_user),
    alert_type: Optional[AlertType] = None,
    is_read: Optional[bool] = None,
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get alerts for the current user."""
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
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: str,
    alert_type: AlertType,
    current_user: User = Depends(get_current_user)
):
    """Mark an alert as read."""
    try:
        # Verify ownership
        alert = await alert_service.price_drop_alerts.find_one({
            "_id": ObjectId(alert_id),
            "user_id": str(current_user.id)
        }) if alert_type == AlertType.PRICE_DROP else await alert_service.discount_alerts.find_one({
            "_id": ObjectId(alert_id),
            "user_id": str(current_user.id)
        })
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        await alert_service.mark_alert_as_read(alert_id, alert_type)
        return {"message": "Alert marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_alert_stats(
    current_user: User = Depends(get_current_user)
):
    """Get alert statistics for the current user."""
    try:
        # Get total alerts
        total_alerts = await alert_service.price_drop_alerts.count_documents({
            "user_id": str(current_user.id)
        }) + await alert_service.discount_alerts.count_documents({
            "user_id": str(current_user.id)
        })

        # Get unread alerts
        unread_alerts = await alert_service.price_drop_alerts.count_documents({
            "user_id": str(current_user.id),
            "is_read": False
        }) + await alert_service.discount_alerts.count_documents({
            "user_id": str(current_user.id),
            "is_read": False
        })

        # Get alert preferences
        total_preferences = await alert_service.alert_preferences.count_documents({
            "user_id": str(current_user.id)
        })

        return {
            "total_alerts": total_alerts,
            "unread_alerts": unread_alerts,
            "total_preferences": total_preferences
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await alert_service.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle any incoming messages if needed
    except WebSocketDisconnect:
        await alert_service.disconnect(websocket)