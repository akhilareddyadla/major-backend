import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import WebSocket
from typing import Dict, List, Optional, Set, Union
from app.core.config import settings
from app.models.product import AlertType, PriceDropAlert, DiscountAlert
from app.db.mongodb import get_collection
import logging
from datetime import datetime
from bson import ObjectId
import json

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        self.smtp_server = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_templates = {
            "price_drop": {
                "subject": "Price Drop Alert: {product_name}",
                "text": """
                Price Drop Alert!
                
                Product: {product_name}
                Original Price: ${original_price}
                Current Price: ${current_price}
                Price Drop: ${price_drop}
                Percentage Drop: {percentage_drop}%
                
                Check it out here: {product_url}
                """,
                "html": """
                <html>
                    <body>
                        <h2>Price Drop Alert: {product_name}</h2>
                        <p>Product: {product_name}</p>
                        <table>
                            <tr>
                                <td>Original Price:</td>
                                <td>${original_price}</td>
                            </tr>
                            <tr>
                                <td>Current Price:</td>
                                <td>${current_price}</td>
                            </tr>
                            <tr>
                                <td>Price Drop:</td>
                                <td>${price_drop}</td>
                            </tr>
                            <tr>
                                <td>Percentage Drop:</td>
                                <td>{percentage_drop}%</td>
                            </tr>
                        </table>
                        <p><a href="{product_url}">Check it out here</a></p>
                    </body>
                </html>
                """
            },
            "discount": {
                "subject": "Discount Alert: {product_name}",
                "text": """
                Discount Alert!
                
                Product: {product_name}
                Original Price: ${original_price}
                Discounted Price: ${discounted_price}
                Discount: {discount_percentage}%
                Valid Until: {valid_until}
                
                Check it out here: {product_url}
                """,
                "html": """
                <html>
                    <body>
                        <h2>Discount Alert: {product_name}</h2>
                        <p>Product: {product_name}</p>
                        <table>
                            <tr>
                                <td>Original Price:</td>
                                <td>${original_price}</td>
                            </tr>
                            <tr>
                                <td>Discounted Price:</td>
                                <td>${discounted_price}</td>
                            </tr>
                            <tr>
                                <td>Discount:</td>
                                <td>{discount_percentage}%</td>
                            </tr>
                            <tr>
                                <td>Valid Until:</td>
                                <td>{valid_until}</td>
                            </tr>
                        </table>
                        <p><a href="{product_url}">Check it out here</a></p>
                    </body>
                </html>
                """
            }
        }

    async def initialize(self):
        """Initialize the notification service."""
        try:
            # Test SMTP connection if email notifications are configured
            if self.smtp_username and self.smtp_password:
                result = await self.test_email_connection()
                if not result["success"]:
                    logger.warning("SMTP connection test failed. Email notifications may not work.")
                    logger.warning(f"SMTP test details: {result['details']}")
                else:
                    logger.info("SMTP connection test successful")
            else:
                logger.info("Email notifications not configured")

            # Initialize any other required resources
            self.active_connections = {}
            self.user_connections = {}
            
            logger.info("NotificationService initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing NotificationService: {str(e)}")
            raise

    async def connect(self, websocket: WebSocket, user_id: str):
        """Connect a WebSocket client."""
        try:
            if not user_id:
                raise ValueError("User ID is required for WebSocket connection")
                
            # Store the connection
            self.active_connections[websocket] = user_id
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
            
            # Send a welcome message
            await websocket.send_json({
                "type": "connection_established",
                "message": "Connected successfully"
            })
            
            logger.info(f"Client connected successfully: {user_id}")
        except Exception as e:
            logger.error(f"Error connecting client: {str(e)}")
            if websocket in self.active_connections:
                del self.active_connections[websocket]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            raise

    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Disconnect a WebSocket client."""
        try:
            # Remove from active connections
            if websocket in self.active_connections:
                del self.active_connections[websocket]
            
            # Remove from user connections
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            logger.info(f"Client disconnected successfully: {user_id}")
        except Exception as e:
            logger.error(f"Error disconnecting client: {str(e)}")

    async def send_notification(self, user_id: str, message: dict):
        """Send a notification to a specific user."""
        try:
            if not user_id:
                raise ValueError("User ID is required for sending notification")
                
            if user_id in self.user_connections:
                disconnected = set()
                for websocket in self.user_connections[user_id]:
                    try:
                        await websocket.send_json({
                            "type": "notification",
                            "data": message
                        })
                        logger.debug(f"Notification sent to user {user_id}")
                    except Exception as e:
                        logger.error(f"Error sending notification to websocket: {str(e)}")
                        disconnected.add(websocket)
                
                # Clean up disconnected websockets
                for websocket in disconnected:
                    await self.disconnect(websocket, user_id)
            else:
                logger.warning(f"No active connections found for user {user_id}")
        except Exception as e:
            logger.error(f"Error in send_notification: {str(e)}")
            raise

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        try:
            for websocket in self.active_connections:
                try:
                    await websocket.send_json(message)
                    logger.debug("Broadcast message sent successfully")
                except Exception as e:
                    logger.error(f"Error broadcasting message: {str(e)}")
                    user_id = self.active_connections[websocket]
                    await self.disconnect(websocket, user_id)
        except Exception as e:
            logger.error(f"Error in broadcast: {str(e)}")
            raise

    async def send_email_notification(self, user_email: str, alert: Union[PriceDropAlert, DiscountAlert]):
        """Send notification via email."""
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.smtp_username
            message["To"] = user_email

            # Get product details
            product_collection = get_collection("products")
            product = await product_collection.find_one({"_id": ObjectId(alert.product_id)})
            if not product:
                raise ValueError(f"Product not found: {alert.product_id}")

            # Prepare email content based on alert type
            if isinstance(alert, PriceDropAlert):
                template = self.email_templates["price_drop"]
                message["Subject"] = template["subject"].format(product_name=product["name"])
                
                # Format text content
                text_content = template["text"].format(
                    product_name=product["name"],
                    original_price=alert.original_price,
                    current_price=alert.current_price,
                    price_drop=alert.price_drop,
                    percentage_drop=alert.percentage_drop,
                    product_url=product["url"]
                )
                
                # Format HTML content
                html_content = template["html"].format(
                    product_name=product["name"],
                    original_price=alert.original_price,
                    current_price=alert.current_price,
                    price_drop=alert.price_drop,
                    percentage_drop=alert.percentage_drop,
                    product_url=product["url"]
                )
            else:  # DiscountAlert
                template = self.email_templates["discount"]
                message["Subject"] = template["subject"].format(product_name=product["name"])
                
                # Format text content
                text_content = template["text"].format(
                    product_name=product["name"],
                    original_price=alert.original_price,
                    discounted_price=alert.discounted_price,
                    discount_percentage=alert.discount_percentage,
                    valid_until=alert.valid_until.strftime("%Y-%m-%d %H:%M:%S"),
                    product_url=product["url"]
                )
                
                # Format HTML content
                html_content = template["html"].format(
                    product_name=product["name"],
                    original_price=alert.original_price,
                    discounted_price=alert.discounted_price,
                    discount_percentage=alert.discount_percentage,
                    valid_until=alert.valid_until.strftime("%Y-%m-%d %H:%M:%S"),
                    product_url=product["url"]
                )

            # Attach both text and HTML versions
            message.attach(MIMEText(text_content, "plain"))
            message.attach(MIMEText(html_content, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
                
            logger.info(f"Email notification sent to {user_email}")
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            raise

    async def send_notification(self, user_id: str, user_email: str, alert: Union[PriceDropAlert, DiscountAlert]):
        """Send notification through all available channels."""
        try:
            # Get user preferences
            preferences_collection = get_collection("alert_preferences")
            preferences = await preferences_collection.find_one({
                "user_id": user_id,
                "product_id": alert.product_id
            })

            if not preferences:
                logger.warning(f"No preferences found for user {user_id} and product {alert.product_id}")
                return

            # Send notifications based on user preferences
            if preferences.get("notify_websocket", True):
                await self.send_notification(user_id, alert.dict())
            
            if preferences.get("notify_email", True):
                await self.send_email_notification(user_email, alert)

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise

    async def test_email_connection(self, send_test_email: bool = False, recipient_email: str = None):
        """
        Test SMTP server connection and optionally send a test email.
        
        Args:
            send_test_email: If True, sends a test email after successful connection
            recipient_email: Email address to send the test email to (required if send_test_email is True)
            
        Returns:
            dict: Status and details of the test
        """
        result = {
            "success": False,
            "connection": False,
            "auth": False,
            "tls": False,
            "email_sent": False,
            "details": []
        }
        
        try:
            # Check required settings
            if not settings.SMTP_HOST or not settings.SMTP_PORT:
                result["details"].append("Missing SMTP host or port settings")
                return result
            
            # Test connection
            logger.info(f"Connecting to SMTP server: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
            try:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
                result["connection"] = True
                result["details"].append(f"Connected to {settings.SMTP_HOST}:{settings.SMTP_PORT}")
                
                # Test TLS
                try:
                    server.starttls()
                    result["tls"] = True
                    result["details"].append("TLS connection established")
                except Exception as tls_error:
                    result["details"].append(f"TLS error: {str(tls_error)}")
                    
                # Test authentication
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    try:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                        result["auth"] = True
                        result["details"].append(f"Authentication successful for {settings.SMTP_USER}")
                    except smtplib.SMTPAuthenticationError as auth_error:
                        result["details"].append(f"Authentication failed: {str(auth_error)}")
                    except Exception as auth_error:
                        result["details"].append(f"Authentication error: {str(auth_error)}")
                else:
                    result["details"].append("No SMTP credentials provided, skipping authentication")
                    
                # Send test email if requested
                if send_test_email and recipient_email:
                    if result["auth"] or not (settings.SMTP_USER and settings.SMTP_PASSWORD):
                        try:
                            message = f"""\
Subject: Test Email from {settings.PROJECT_NAME}
From: {settings.SMTP_USER}
To: {recipient_email}

This is a test email from {settings.PROJECT_NAME}.
If you received this email, your SMTP configuration is working correctly.

Time: {datetime.utcnow().isoformat()}
"""
                            server.sendmail(settings.SMTP_USER, recipient_email, message)
                            result["email_sent"] = True
                            result["details"].append(f"Test email sent to {recipient_email}")
                        except Exception as email_error:
                            result["details"].append(f"Failed to send test email: {str(email_error)}")
                    else:
                        result["details"].append("Skipping test email, authentication failed")
                
                # Close connection
                try:
                    server.quit()
                    result["details"].append("SMTP connection closed properly")
                except Exception:
                    result["details"].append("Error closing SMTP connection")
                    
            except smtplib.SMTPConnectError as conn_error:
                result["details"].append(f"Connection error: {str(conn_error)}")
            except Exception as conn_error:
                result["details"].append(f"Connection error: {str(conn_error)}")
        except Exception as e:
            result["details"].append(f"General error: {str(e)}")
            logger.error(f"SMTP test failed: {str(e)}")
        
        # Set overall success
        result["success"] = result["connection"] and (result["auth"] or not (settings.SMTP_USER and settings.SMTP_PASSWORD))
        
        return result

class AlertGenerator:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def check_price_drop(self, product_id: str, current_price: float, user_id: str, user_email: str):
        """Check for price drops and generate alerts."""
        try:
            # Get price history
            price_history_collection = get_collection("price_history")
            price_history = await price_history_collection.find(
                {"product_id": product_id}
            ).sort("timestamp", -1).limit(1).to_list(1)
            
            if not price_history:
                return
            
            last_price = price_history[0]["price"]
            
            # Calculate price drop
            price_drop = last_price - current_price
            percentage_drop = (price_drop / last_price) * 100
            
            # Get user preferences
            preferences_collection = get_collection("alert_preferences")
            preferences = await preferences_collection.find_one({
                "user_id": user_id,
                "product_id": product_id
            })
            
            if not preferences:
                return
            
            # Check if price drop meets criteria
            if (preferences.get("percentage_drop") and percentage_drop >= preferences["percentage_drop"]) or \
               (preferences.get("price_threshold") and current_price <= preferences["price_threshold"]):
                
                # Create price drop alert
                alert = PriceDropAlert(
                    id=str(ObjectId()),
                    user_id=user_id,
                    product_id=product_id,
                    original_price=last_price,
                    current_price=current_price,
                    price_drop=price_drop,
                    percentage_drop=percentage_drop,
                    created_at=datetime.utcnow(),
                    is_read=False
                )
                
                # Save alert
                alert_collection = get_collection("alerts")
                await alert_collection.insert_one(alert.dict())
                
                # Send notification
                await self.notification_service.send_notification(
                    user_id=user_id,
                    user_email=user_email,
                    alert=alert
                )
                
        except Exception as e:
            logger.error(f"Error checking price drop: {str(e)}")
            raise

    async def check_discount(self, product_id: str, current_price: float, user_id: str, user_email: str):
        """Check for discounts and generate alerts."""
        try:
            # Get product details
            product_collection = get_collection("products")
            product = await product_collection.find_one({"_id": ObjectId(product_id)})
            
            if not product or not product.get("discount_percentage"):
                return
            
            # Get user preferences
            preferences_collection = get_collection("alert_preferences")
            preferences = await preferences_collection.find_one({
                "user_id": user_id,
                "product_id": product_id,
                "alert_type": AlertType.DISCOUNT
            })
            
            if not preferences:
                return
            
            # Create discount alert
            alert = DiscountAlert(
                id=str(ObjectId()),
                user_id=user_id,
                product_id=product_id,
                original_price=product["original_price"],
                discounted_price=current_price,
                discount_percentage=product["discount_percentage"],
                valid_until=product.get("discount_end_date", datetime.utcnow() + timedelta(days=7)),
                created_at=datetime.utcnow(),
                is_read=False
            )
            
            # Save alert
            alert_collection = get_collection("alerts")
            await alert_collection.insert_one(alert.dict())
            
            # Send notification
            await self.notification_service.send_notification(
                user_id=user_id,
                user_email=user_email,
                alert=alert
            )
                
        except Exception as e:
            logger.error(f"Error checking discount: {str(e)}")
            raise

# Create service instances
notification_service = NotificationService()
alert_generator = AlertGenerator(notification_service)