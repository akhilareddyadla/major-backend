import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import requests
import base64
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import HTTPException, WebSocket
from app.db.mongodb import get_database, get_collection
from app.core.config import settings  # Import settings to load .env variables
from bson import ObjectId
from app.models.product import Alert, AlertType, PriceDropAlert

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.db = None  # Initialize db as None
        self.notifications_collection = None
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.initialized = False

    async def initialize(self):
        """Initialize the notification service."""
        if not self.initialized:
            self.db = get_database()
            self.notifications_collection = get_collection("notifications")
            logger.info("NotificationService initialized successfully")
            self.initialized = True

    async def connect(self, websocket: WebSocket, user_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"New WebSocket connection for user {user_id}")

    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Disconnect a WebSocket client."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_notification(self, user_id: str, user_email: str, alert: Alert):
        """
        Send a notification to a user based on an alert.
        Handles both email and in-app notifications.
        """
        try:
            if not self.initialized:
                await self.initialize()

            # Create notification message based on alert type
            if isinstance(alert, PriceDropAlert):
                message = self._create_price_drop_message(alert)
                subject = f"Price Drop Alert: {alert.product_name}"
            else:
                message = alert.message
                subject = "Price Alert"

            # Send email notification
            if user_email:
                await self.send_email_notification(user_email, subject, message)

            # Store notification in database
            notification_data = {
                "user_id": user_id,
                "type": alert.alert_type.value,
                "message": message,
                "subject": subject,
                "data": alert.dict(),
                "created_at": datetime.utcnow(),
                "is_read": False
            }
            
            result = await self.notifications_collection.insert_one(notification_data)
            notification_data["_id"] = result.inserted_id

            # Send to connected WebSocket clients
            if user_id in self.active_connections:
                for connection in self.active_connections[user_id]:
                    try:
                        await connection.send_json(notification_data)
                    except Exception as e:
                        logger.error(f"Error sending to WebSocket: {str(e)}")
                        await self.disconnect(connection, user_id)

            return notification_data

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send notification: {str(e)}"
            )

    def _create_price_drop_message(self, alert: PriceDropAlert) -> str:
        """Create a formatted message for price drop alerts."""
        return f"""
Price Drop Alert!

Product: {alert.product_name}
Original Price: ₹{alert.original_price:.2f}
Current Price: ₹{alert.current_price:.2f}
Price Drop: ₹{alert.price_drop:.2f} ({alert.percentage_drop:.1f}%)

View the product: {alert.product_url}

This is an automated alert from your price tracking service.
"""

    async def send_email_notification(self, email: str, subject: str, message: str) -> None:
        """Send an email notification."""
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAILS_FROM_EMAIL, email, msg.as_string())
            logger.info(f"Email sent to {email}")
        except Exception as e:
            logger.error(f"Email error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")

    async def send_whatsapp_notification(self, phone_number: str, message: str) -> None:
        """
        Send a WhatsApp notification using Twilio API.
        """
        if self.db is None:
            await self.initialize()  # Ensure database is initialized
        try:
            account_sid = settings.TWILIO_ACCOUNT_SID  # Load from settings
            auth_token = settings.TWILIO_AUTH_TOKEN  # Load from settings
            from_number = settings.TWILIO_FROM_NUMBER_WHATSAPP  # Load from settings
            to_number = f"whatsapp:{phone_number}"

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            payload = {
                "From": from_number,
                "To": to_number,
                "Body": message
            }
            headers = {
                "Authorization": f"Basic {base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()}"
            }

            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp message sent to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send WhatsApp notification: {str(e)}")

    async def send_sms_notification(self, phone_number: str, message: str) -> None:
        """
        Send an SMS notification using Twilio API.
        """
        if self.db is None:
            await self.initialize()  # Ensure database is initialized
        try:
            account_sid = settings.TWILIO_ACCOUNT_SID  # Load from settings
            auth_token = settings.TWILIO_AUTH_TOKEN  # Load from settings
            from_number = settings.TWILIO_FROM_NUMBER_SMS  # Load from settings
            to_number = phone_number

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            payload = {
                "From": from_number,
                "To": to_number,
                "Body": message
            }
            headers = {
                "Authorization": f"Basic {base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()}"
            }

            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"SMS sent to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send SMS notification: {str(e)}")

    async def get_user_notifications(self, user_id: str, limit: int = 50) -> list:
        """Get recent notifications for a user."""
        cursor = self.notifications_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)
        notifications = await cursor.to_list(length=limit)
        return [{**notification, "id": str(notification["_id"])} for notification in notifications]

    async def mark_as_read(self, notification_id: str, user_id: str):
        """Mark a notification as read."""
        result = await self.notifications_collection.update_one(
            {"_id": ObjectId(notification_id), "user_id": user_id},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def mark_all_as_read(self, user_id: str):
        """Mark all notifications as read for a user."""
        result = await self.notifications_collection.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        return result.modified_count

    async def check_and_notify_price_drops(self) -> None:
        """Check for price drops and send notifications."""
        try:
            if not self.initialized:
                await self.initialize()

            # Get all active price alerts
            alerts = await self.db.price_alerts.find({
                "is_active": True,
                "target_price": {"$exists": True}
            }).to_list(length=None)

            for alert in alerts:
                product = await self.db.products.find_one({"_id": ObjectId(alert["product_id"])})
                if not product:
                    continue

                current_price = product.get("current_price")
                if current_price and current_price <= alert["target_price"]:
                    # Create price drop alert
                    price_drop_alert = PriceDropAlert(
                        user_id=alert["user_id"],
                        product_id=str(product["_id"]),
                        product_name=product["title"],
                        product_url=product["url"],
                        original_price=alert["original_price"],
                        current_price=current_price,
                        price_drop=alert["original_price"] - current_price,
                        percentage_drop=((alert["original_price"] - current_price) / alert["original_price"]) * 100,
                        alert_type=AlertType.PRICE_DROP,
                        created_at=datetime.utcnow()
                    )

                    # Get user details
                    user = await self.db.users.find_one({"_id": ObjectId(alert["user_id"])})
                    if user:
                        await self.send_notification(
                            user_id=str(user["_id"]),
                            user_email=user.get("email"),
                            alert=price_drop_alert
                        )

        except Exception as e:
            logger.error(f"Error checking price drops: {str(e)}")
            raise

    async def test_email_connection(self, send_test_email: bool = False, recipient_email: Optional[str] = None) -> Dict:
        """
        Test the SMTP connection and optionally send a test email.
        """
        try:
            smtp_server = settings.SMTP_HOST
            smtp_port = settings.SMTP_PORT
            smtp_user = settings.SMTP_USER
            smtp_password = settings.SMTP_PASSWORD
            from_email = settings.EMAILS_FROM_EMAIL

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                if send_test_email and recipient_email:
                    msg = MIMEMultipart()
                    msg["From"] = from_email
                    msg["To"] = recipient_email
                    msg["Subject"] = "Test Email"
                    msg.attach(MIMEText("This is a test email from the Price Tracker.", "plain"))
                    server.sendmail(from_email, recipient_email, msg.as_string())
            return {"status": "success", "message": "SMTP connection successful"}
        except Exception as e:
            logger.error(f"SMTP test failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"SMTP test failed: {str(e)}")

# Create a singleton instance
notification_service = NotificationService()