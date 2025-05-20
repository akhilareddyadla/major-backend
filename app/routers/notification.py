from fastapi import APIRouter, Depends, HTTPException, status, Body, WebSocket, WebSocketDisconnect, Query
from app.models.product import Alert, AlertType, PriceDropAlert
from app.services.notification import notification_service
from app.services.users import user_service
from app.services.alerts import alert_service
from app.db.mongodb import get_database
from app.services.auth import get_current_active_user, verify_token
from app.models.user import User
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging
import smtplib
import json
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])

async def get_db():
    return get_database()

@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    alert: Alert = Body(...),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Send a notification based on the provided alert.
    This endpoint requires authentication and can only be accessed by administrators.
    """
    try:
        # Check if user is an admin
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can send notifications"
            )
            
        # Get the recipient user
        recipient = await user_service.get_user_by_id(alert.user_id)
        if not recipient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient user not found"
            )
            
        # Send the notification
        await notification_service.send_notification(
            user_id=alert.user_id,
            user_email=recipient.email,
            alert=alert
        )
        
        return {"message": "Notification sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notification"
        )

@router.post("/price-drop", status_code=status.HTTP_202_ACCEPTED)
async def create_price_drop_notification(
    product_id: str = Body(...),
    price: float = Body(...),
    recipient_id: str = Body(...),
    message: str = Body(None),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Create and send a price drop notification.
    This is a simplified endpoint for creating price drop alerts.
    """
    try:
        # Check if user is an admin
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can send notifications"
            )
            
        # Get recipient
        recipient = await user_service.get_user_by_id(recipient_id)
        if not recipient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient user not found"
            )
            
        # Get product (assuming you have a product service)
        product = await db["products"].find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
            
        # Create alert object
        alert = PriceDropAlert(
            user_id=recipient_id,
            product_id=product_id,
            original_price=product.get("current_price", 0),
            current_price=price,
            price_drop=product.get("current_price", 0) - price,
            percentage_drop=((product.get("current_price", 0) - price) / product.get("current_price", 1)) * 100,
            alert_type=AlertType.PRICE_DROP,
            created_at=datetime.utcnow(),
            is_read=False
        )
        
        # Send notification
        await notification_service.send_notification(
            user_id=recipient_id,
            user_email=recipient.email,
            alert=alert
        )
        
        return {"message": "Price drop notification sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending price drop notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send price drop notification"
        )

@router.post("/test-email", status_code=status.HTTP_202_ACCEPTED)
async def test_email(
    email: str = Body(..., description="Email address to send the test to"),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Test email notification by sending a sample alert.
    This endpoint requires administrator privileges.
    """
    try:
        # Check if user is an admin
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can send test emails"
            )
            
        # Validate email format
        from email_validator import validate_email, EmailNotValidError
        try:
            validate_email(email)
        except EmailNotValidError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
            
        # Create a sample alert for testing
        sample_alert = PriceDropAlert(
            id="test-id",
            user_id=str(current_user.id),
            product_id="test-product-id",
            product_name="Test Product",
            original_price=100.00,
            current_price=80.00,
            price_drop=20.00,
            percentage_drop=20.0,
            alert_type=AlertType.PRICE_DROP,
            created_at=datetime.utcnow(),
            is_read=False
        )
        
        # Send test email
        try:
            await notification_service.send_email_notification(email, sample_alert)
            return {"message": f"Test email sent successfully to {email}"}
        except smtplib.SMTPAuthenticationError:
            logging.error("SMTP Authentication Error: Failed to authenticate with the email server")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to authenticate with the email server. Check your SMTP credentials."
            )
        except smtplib.SMTPException as e:
            logging.error(f"SMTP Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"SMTP error: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending test email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email"
        )

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time notifications."""
    try:
        # Accept the WebSocket connection first
        await websocket.accept()
        logging.info("WebSocket connection accepted")
        
        try:
            # Connect the client to notification service
            await notification_service.connect(websocket, user_id)
            logging.info(f"Client connected successfully: {user_id}")
            
            # Keep the connection alive and handle incoming messages
            while True:
                try:
                    # Wait for any message from the client
                    data = await websocket.receive_text()
                    logging.debug(f"Received WebSocket message from user_id {user_id}: {data}")
                    
                    # Handle different message types
                    try:
                        message = json.loads(data)
                        message_type = message.get("type", "")
                        
                        if message_type == "ping":
                            # Simple ping/pong for connection health check
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        elif message_type == "get_price_history":
                            # Handle price history request
                            product_id = message.get("product_id")
                            if not product_id:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "Product ID is required"
                                })
                                continue
                                
                            try:
                                from app.services.products import product_service
                                price_history = await product_service.get_price_history(product_id)
                                
                                # Format the response
                                formatted_history = []
                                for entry in price_history:
                                    formatted_entry = {
                                        "price": float(entry.price),
                                        "timestamp": entry.timestamp.isoformat(),
                                        "currency": entry.currency,
                                        "discount_percentage": entry.discount_percentage,
                                        "is_discount": bool(entry.is_discount)
                                    }
                                    formatted_history.append(formatted_entry)
                                
                                await websocket.send_json({
                                    "type": "price_history",
                                    "product_id": product_id,
                                    "data": formatted_history
                                })
                            except Exception as e:
                                logging.error(f"Error getting price history: {str(e)}")
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"Error getting price history: {str(e)}"
                                })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Unknown message type: {message_type}"
                            })
                            
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON received from user_id {user_id}: {data}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid JSON message"
                        })
                        continue
                        
                except WebSocketDisconnect:
                    logging.info(f"WebSocket disconnected for user_id: {user_id}")
                    await notification_service.disconnect(websocket, user_id)
                    break
                    
        except Exception as e:
            logging.error(f"WebSocket connection error: {str(e)}")
            await notification_service.disconnect(websocket, user_id)
            
    except Exception as e:
        logging.error(f"WebSocket setup error: {str(e)}")
        try:
            await websocket.close(code=1011)  # Internal error
        except:
            pass

@router.get("/alerts", response_model=List[dict])
async def get_alerts(
    user_id: Optional[str] = Query(None, description="Filter alerts by user ID"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by alert type (price_drop or discount)"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of alerts to return"),
    skip: int = Query(0, ge=0, description="Number of alerts to skip (for pagination)"),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Get alerts with optional filtering.
    Admin users can view all alerts, regular users can only see their own alerts.
    """
    try:
        # If user_id is provided but user is not admin, ensure they can only see their own alerts
        if user_id and user_id != str(current_user.id) and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own alerts"
            )
            
        # If no user_id specified, non-admin users can only see their own
        if not user_id and not current_user.is_superuser:
            user_id = str(current_user.id)
            
        # Get alerts using the alert service
        alerts = await alert_service.get_user_alerts(
            user_id=user_id, 
            alert_type=alert_type,
            is_read=is_read,
            limit=limit,
            skip=skip
        )
        
        # If no alerts found, return empty list
        if not alerts:
            return []
            
        return alerts
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )

@router.get("/alerts/count", response_model=dict)
async def get_alerts_count(
    user_id: Optional[str] = Query(None, description="Filter alerts by user ID"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by alert type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Get the count of alerts with optional filtering.
    Admin users can count all alerts, regular users can only count their own alerts.
    """
    try:
        # If user_id is provided but user is not admin, ensure they can only see their own alerts
        if user_id and user_id != str(current_user.id) and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only count your own alerts"
            )
            
        # If no user_id specified, non-admin users can only see their own
        if not user_id and not current_user.is_superuser:
            user_id = str(current_user.id)
            
        # Build query for price drop alerts
        price_drop_query = {}
        if user_id:
            price_drop_query["user_id"] = user_id
        if is_read is not None:
            price_drop_query["is_read"] = is_read
        if alert_type and alert_type != AlertType.PRICE_DROP:
            price_drop_count = 0
        else:
            price_drop_count = await db["price_drop_alerts"].count_documents(price_drop_query)
            
        # Build query for discount alerts
        discount_query = {}
        if user_id:
            discount_query["user_id"] = user_id
        if is_read is not None:
            discount_query["is_read"] = is_read
        if alert_type and alert_type != AlertType.DISCOUNT:
            discount_count = 0
        else:
            discount_count = await db["discount_alerts"].count_documents(discount_query)
            
        return {
            "total": price_drop_count + discount_count,
            "price_drop_alerts": price_drop_count,
            "discount_alerts": discount_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error counting alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to count alerts"
        )

@router.post("/alerts", response_model=PriceDropAlert)
async def create_alert(
    alert_data: PriceDropAlert,
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Create a new price drop alert.
    Regular users can only create alerts for themselves, admins can create for any user.
    """
    try:
        # Security check: non-admin users can only create alerts for themselves
        if str(current_user.id) != alert_data.user_id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create alerts for yourself"
            )
            
        # Verify the product exists
        product = await db["products"].find_one({"_id": ObjectId(alert_data.product_id)})
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
            
        # Set creation timestamp if not provided
        if not alert_data.created_at:
            alert_data.created_at = datetime.utcnow()
            
        # Ensure is_read is set to false for new alerts
        alert_data.is_read = False
            
        # Convert to dictionary for database
        alert_dict = alert_data.dict(exclude={"id"})
        
        # Insert into database
        result = await db["price_drop_alerts"].insert_one(alert_dict)
        
        # Update with generated ID
        alert_data.id = str(result.inserted_id)
        
        # Return the created alert
        return alert_data
    except HTTPException:
        raise
    except ValueError as e:
        logging.error(f"Validation error creating alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logging.error(f"Error creating alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert"
        )

@router.post("/notify", response_model=Alert, status_code=status.HTTP_202_ACCEPTED)
async def notify(
    alert: Alert,
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Send a notification to the current user.
    This endpoint allows users to send notifications to themselves.
    """
    try:
        # Override user_id with the current user for security
        alert.user_id = str(current_user.id)
        
        # Send the notification
        await notification_service.send_notification(
            user_id=str(current_user.id),
            user_email=current_user.email,
            alert=alert
        )
        
        # Store the alert in the appropriate collection based on type
        if alert.alert_type == AlertType.PRICE_DROP:
            result = await db["price_drop_alerts"].insert_one(alert.dict(exclude={"id"}))
            alert.id = str(result.inserted_id)
        elif alert.alert_type == AlertType.DISCOUNT:
            result = await db["discount_alerts"].insert_one(alert.dict(exclude={"id"}))
            alert.id = str(result.inserted_id)
        
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send notification"
        )

@router.post("/test-smtp", response_model=dict)
async def test_smtp_connection(
    send_test_email: bool = Body(False, description="Whether to send a test email"),
    recipient_email: Optional[str] = Body(None, description="Email address to send the test email to"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Test SMTP server connection and optionally send a test email.
    This endpoint requires administrator privileges.
    """
    # Check if user is an admin
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can test SMTP settings"
        )
        
    # Validate recipient email if sending a test
    if send_test_email and not recipient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipient email is required when sending a test email"
        )
        
    # Run the test
    try:
        result = await notification_service.test_email_connection(
            send_test_email=send_test_email,
            recipient_email=recipient_email
        )
        return result
    except Exception as e:
        logging.error(f"SMTP test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP test failed: {str(e)}"
        )

@router.get("/", response_model=List[Notification])
async def get_notifications(
    current_user: User = Depends(get_current_active_user),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notifications to return"),
    skip: int = Query(0, ge=0, description="Number of notifications to skip (for pagination)"),
    sort_by: str = Query("created_at", description="Sort field (created_at, type)"),
    sort_order: int = Query(-1, description="Sort order (1 for ascending, -1 for descending)"),
    db=Depends(get_db)
):
    """
    Get notification history for the current user with filtering and pagination.
    """
    try:
        # Build query
        query = {"user_id": str(current_user.id)}
        
        # Apply filters
        if is_read is not None:
            query["is_read"] = is_read
        if notification_type:
            query["type"] = notification_type
            
        # Get notifications with pagination and sorting
        cursor = db.notifications.find(query)
        
        # Apply sorting
        if sort_by == "type":
            cursor = cursor.sort("type", sort_order)
        else:  # default sort by created_at
            cursor = cursor.sort("created_at", sort_order)
            
        # Apply pagination
        cursor = cursor.skip(skip).limit(limit)
        
        # Convert to list and return
        notifications = await cursor.to_list(length=None)
        return [Notification(**n) for n in notifications]
        
    except Exception as e:
        logging.error(f"Error retrieving notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )

@router.get("/count", response_model=dict)
async def get_notifications_count(
    current_user: User = Depends(get_current_active_user),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    db=Depends(get_db)
):
    """
    Get count of notifications for the current user with optional filtering.
    """
    try:
        # Build query
        query = {"user_id": str(current_user.id)}
        
        # Apply filters
        if is_read is not None:
            query["is_read"] = is_read
        if notification_type:
            query["type"] = notification_type
            
        # Get count
        total_count = await db.notifications.count_documents(query)
        unread_count = await db.notifications.count_documents({**query, "is_read": False})
        
        return {
            "total": total_count,
            "unread": unread_count
        }
        
    except Exception as e:
        logging.error(f"Error counting notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to count notifications"
        )

@router.put("/{notification_id}/read", response_model=Notification)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db=Depends(get_db)
):
    """
    Mark a notification as read.
    """
    try:
        # Find and update notification
        result = await db.notifications.find_one_and_update(
            {"_id": ObjectId(notification_id), "user_id": str(current_user.id)},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}},
            return_document=True
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
            
        return Notification(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error marking notification as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        ) 