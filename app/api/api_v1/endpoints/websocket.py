from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status, APIRouter
from app.services.auth import verify_token
from app.services.notification import notification_service
from app.services.price_history import price_history_service
import logging
import json
from datetime import datetime
from starlette.websockets import WebSocketState
from typing import Optional
from decimal import Decimal

logger = logging.getLogger(__name__)
router = APIRouter()

async def websocket_auth(websocket: WebSocket) -> Optional[str]:
    """Authenticate WebSocket connection and return user_id."""
    try:
        # Log connection details for debugging
        logger.info("==================================================")
        logger.info("WebSocket Connection Details:")
        logger.info(f"Client: {websocket.client.host}:{websocket.client.port}")
        logger.info(f"Headers: {dict(websocket.headers)}")
        logger.info(f"Query parameters: {dict(websocket.query_params)}")
        logger.info("==================================================")

        # Get token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            logger.error("No token provided in query parameters")
            return None

        # Validate token
        logger.info(f"Validating token: {token[:20]}...")
        try:
            user_id = await verify_token(token)
            if not user_id:
                logger.error("Token validation failed: No user ID returned")
                return None
                
            logger.info(f"Token validated successfully for user: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return None

    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None

@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    user_id = None
    try:
        # Log incoming connection
        logger.info(f"New WebSocket connection from {websocket.client.host}:{websocket.client.port}")
        
        # Accept the connection first
        try:
            await websocket.accept()
            logger.info("WebSocket connection accepted")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            return

        # Authenticate the connection
        user_id = await websocket_auth(websocket)
        if not user_id:
            logger.error("WebSocket authentication failed - closing connection")
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1008)  # Policy violation
            return

        # Connect to notification service
        try:
            logger.info(f"Connecting WebSocket for user {user_id} to notification service")
            await notification_service.connect(websocket, user_id)
            await websocket.send_json({
                "type": "connection_established",
                "message": "Connected successfully",
                "user_id": user_id
            })
            logger.info(f"Connection established successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error in notification service connection: {str(e)}")
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1011)  # Internal error
            return

        # Handle messages
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break

            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                message_type = message.get("type", "")

                if message_type == "get_price_history":
                    product_id = message.get("product_id")
                    if not product_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Product ID is required"
                        })
                        continue

                    try:
                        history = await price_history_service.get_price_history(product_id)
                        
                        # Format the response data
                        formatted_history = []
                        for entry in history:
                            try:
                                formatted_entry = {
                                    "price": float(entry.price),
                                    "timestamp": entry.timestamp.isoformat(),
                                    "currency": entry.currency or "INR",
                                    "discount_percentage": float(entry.discount_percentage) if entry.discount_percentage is not None else None,
                                    "is_discount": bool(entry.is_discount)
                                }
                                formatted_history.append(formatted_entry)
                            except (ValueError, AttributeError) as e:
                                logger.error(f"Error formatting price history entry: {str(e)}")
                                continue

                        # Sort by timestamp
                        formatted_history.sort(key=lambda x: x["timestamp"])
                        
                        # Send response
                        await websocket.send_json({
                            "type": "price_history",
                            "product_id": product_id,
                            "data": formatted_history
                        })
                        logger.info(f"Sent {len(formatted_history)} price history entries")

                    except Exception as e:
                        logger.error(f"Error processing price history: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Error retrieving price history"
                        })

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}")
                break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format"
                })
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal server error"
                })

    except Exception as e:
        logger.error(f"Critical WebSocket error: {str(e)}")
    finally:
        if user_id:
            try:
                await notification_service.disconnect(websocket, user_id)
            except Exception as e:
                logger.error(f"Error disconnecting from notification service: {str(e)}")
        
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {str(e)}") 