from fastapi import APIRouter, Depends, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict
from app.db.mongodb import get_database
from bson import ObjectId
from app.services.notification import notification_service
from app.services.auth import auth_service
from app.schemas.notification import NotificationResponse
from app.core.deps import get_current_user

router = APIRouter()
security = HTTPBearer()

# Dependency to get the database
async def get_db():
    return await get_database()

@router.get("/history/{user_id}", response_model=List[Dict])
async def get_notification_history(
    user_id: str,
    db=Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Fetch notification history for a specific user.
    """
    try:
        # Optionally, validate the user_id against the token's user ID here
        # For simplicity, we're assuming the token is validated by FastAPI's security middleware
        history = await db["notification_history"].find({"user_id": user_id}).to_list(length=None)
        if not history:
            return []

        # Convert MongoDB ObjectId to string for JSON serialization
        for entry in history:
            entry["_id"] = str(entry["_id"])
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notification history: {str(e)}")

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time notifications."""
    try:
        # Verify token and get user
        user = await auth_service.verify_token(token)
        if not user:
            await websocket.close(code=4001)
            return

        # Connect to notification service
        await notification_service.connect(websocket, str(user["_id"]))

        try:
            while True:
                # Keep connection alive and handle any incoming messages
                data = await websocket.receive_text()
                # You can handle any client messages here if needed
        except WebSocketDisconnect:
            await notification_service.disconnect(websocket, str(user["_id"]))
    except Exception as e:
        await websocket.close(code=4000)

@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    current_user = Depends(get_current_user),
    limit: int = 50
):
    """Get recent notifications for the current user."""
    notifications = await notification_service.get_user_notifications(
        str(current_user["_id"]),
        limit=limit
    )
    return notifications

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user = Depends(get_current_user)
):
    """Mark a notification as read."""
    success = await notification_service.mark_as_read(
        notification_id,
        str(current_user["_id"])
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success"}

@router.post("/read-all")
async def mark_all_notifications_read(
    current_user = Depends(get_current_user)
):
    """Mark all notifications as read for the current user."""
    count = await notification_service.mark_all_as_read(str(current_user["_id"]))
    return {"status": "success", "count": count}