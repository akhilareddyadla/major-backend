from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.db.mongodb import get_collection, connect_to_mongo
from app.models.product import AlertPreference, PriceDropAlert, DiscountAlert, AlertType, AlertPreferenceCreate, AlertPreferenceUpdate
from app.services.notification import notification_service
from app.services.products import product_service
import logging
import asyncio
from bson import ObjectId
from fastapi import WebSocket
from app.schemas.alert import AlertCreate, AlertResponse

logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self):
        self.initialized = False
        self.alert_preferences_collection = None
        self.price_drop_alerts_collection = None
        self.discount_alerts_collection = None
        self.active_connections: Dict[str, WebSocket] = {}
        self.alerts_collection = None
        self.notifications_collection = None
        self.products_collection = None

    async def initialize(self):
        """Initialize the collections after MongoDB connection is established."""
        if not self.initialized:
            try:
                self.alert_preferences_collection = get_collection("alert_preferences")
                self.price_drop_alerts_collection = get_collection("price_drop_alerts")
                self.discount_alerts_collection = get_collection("discount_alerts")
                self.alerts_collection = get_collection("alerts")
                self.notifications_collection = get_collection("notifications")
                self.products_collection = get_collection("products")
                logger.info("AlertService collections initialized")
                self.initialized = True
            except Exception as e:
                logger.error(f"Error initializing AlertService collections: {str(e)}")
                raise

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[id(websocket)] = websocket

    async def disconnect(self, websocket: WebSocket):
        if id(websocket) in self.active_connections:
            del self.active_connections[id(websocket)]

    async def send_alert(self, user_id: str, message: str):
        """Send an alert to a specific user's WebSocket connection."""
        for ws in self.active_connections.values():
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error(f"Error sending alert: {str(e)}")

    async def create_alert_preference(
        self,
        user_id: str,
        alert_preference: AlertPreferenceCreate
    ) -> AlertPreference:
        """Create a new alert preference."""
        try:
            await self.initialize()  # Ensure collections are initialized
            alert_dict = alert_preference.dict()
            alert_dict["user_id"] = user_id
            alert_dict["is_active"] = True

            result = await self.alert_preferences_collection.insert_one(alert_dict)
            alert_dict["_id"] = result.inserted_id
            return AlertPreference(**alert_dict)
        except Exception as e:
            logger.error(f"Error creating alert preference: {str(e)}")
            raise

    async def get_alert_preferences(self, user_id: str) -> List[AlertPreference]:
        """Get all alert preferences for a user."""
        try:
            await self.initialize()  # Ensure collections are initialized
            cursor = self.alert_preferences_collection.find({"user_id": user_id})
            preferences = await cursor.to_list(length=None)
            return [AlertPreference(**pref) for pref in preferences]
        except Exception as e:
            logger.error(f"Error getting alert preferences: {str(e)}")
            raise

    async def get_alert_preference(self, alert_id: str) -> Optional[AlertPreference]:
        """Get a single alert preference by ID."""
        try:
            await self.initialize()  # Ensure collections are initialized
            alert = await self.alert_preferences_collection.find_one({"_id": ObjectId(alert_id)})
            return AlertPreference(**alert) if alert else None
        except Exception as e:
            logger.error(f"Error getting alert preference: {str(e)}")
            raise

    async def update_alert_preference(
        self,
        alert_id: str,
        alert_update: AlertPreferenceUpdate
    ) -> Optional[AlertPreference]:
        """Update an alert preference."""
        try:
            await self.initialize()  # Ensure collections are initialized
            update_data = alert_update.dict(exclude_unset=True)
            result = await self.alert_preferences_collection.find_one_and_update(
                {"_id": ObjectId(alert_id)},
                {"$set": update_data},
                return_document=True
            )
            return AlertPreference(**result) if result else None
        except Exception as e:
            logger.error(f"Error updating alert preference: {str(e)}")
            raise

    async def delete_alert_preference(self, alert_id: str) -> bool:
        """Delete an alert preference."""
        try:
            await self.initialize()  # Ensure collections are initialized
            result = await self.alert_preferences_collection.delete_one({"_id": ObjectId(alert_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting alert preference: {str(e)}")
            raise

    async def check_price_drops(self):
        """Check for price drops and create alerts."""
        try:
            await self.initialize()  # Ensure collections are initialized
            # Get all active products
            products = await product_service.get_products(is_active=True)
            
            for product in products:
                # Get current price from product service
                current_price = product.current_price
                
                # Get alert preferences for this product
                preferences = await self.get_alert_preferences(
                    product_id=product.id,
                    alert_type=AlertType.PRICE_DROP
                )
                
                for preference in preferences:
                    if preference.threshold_price and current_price <= preference.threshold_price:
                        # Create price drop alert
                        alert = PriceDropAlert(
                            user_id=preference.user_id,
                            product_id=product.id,
                            original_price=product.current_price,
                            current_price=current_price,
                            price_drop=current_price - product.current_price,
                            percentage_drop=((product.current_price - current_price) / product.current_price) * 100,
                            alert_type=AlertType.PRICE_DROP
                        )
                        
                        # Save alert
                        result = await self.price_drop_alerts_collection.insert_one(alert.dict())
                        alert.id = str(result.inserted_id)
                        
                        # Send notification
                        await notification_service.send_notification(
                            user_id=preference.user_id,
                            alert=alert
                        )
                        
        except Exception as e:
            logger.error(f"Error checking price drops: {str(e)}")
            raise

    async def check_discounts(self):
        """Check for discounts and create alerts."""
        try:
            await self.initialize()  # Ensure collections are initialized
            # Get all active alert preferences
            preferences = await self.alert_preferences_collection.find({
                "is_active": True,
                "alert_type": AlertType.DISCOUNT
            }).to_list(length=None)

            for pref in preferences:
                product = await product_service.get_product(pref["product_id"])
                if not product:
                    continue

                # Check if product has discount
                if product.discount_percentage > 0:
                    # Create discount alert
                    alert = DiscountAlert(
                        user_id=pref["user_id"],
                        product_id=product.id,
                        original_price=product.original_price,
                        discounted_price=product.current_price,
                        discount_percentage=product.discount_percentage,
                        valid_until=product.discount_end_date or datetime.utcnow() + timedelta(days=7)
                    )

                    # Save alert
                    result = await self.discount_alerts_collection.insert_one(alert.dict())
                    alert.id = str(result.inserted_id)

                    # Send notification
                    await notification_service.send_notification(
                        user_id=pref["user_id"],
                        alert=alert
                    )

        except Exception as e:
            logger.error(f"Error checking discounts: {str(e)}")
            raise

    async def get_user_alerts(
        self,
        user_id: str,
        alert_type: Optional[AlertType] = None,
        is_read: Optional[bool] = None,
        limit: int = 10,
        skip: int = 0
    ) -> List[dict]:
        """Get alerts for a user."""
        try:
            await self.initialize()  # Ensure collections are initialized
            query = {"user_id": user_id}
            if alert_type:
                query["alert_type"] = alert_type
            if is_read is not None:
                query["is_read"] = is_read

            alerts = []
            
            # Get price drop alerts
            cursor = self.price_drop_alerts_collection.find(query).skip(skip).limit(limit)
            async for alert in cursor:
                alert["id"] = str(alert["_id"])
                alerts.append(alert)
            
            # Get discount alerts
            cursor = self.discount_alerts_collection.find(query).skip(skip).limit(limit)
            async for alert in cursor:
                alert["id"] = str(alert["_id"])
                alerts.append(alert)
            
            return sorted(alerts, key=lambda x: x["created_at"], reverse=True)
        except Exception as e:
            logger.error(f"Error getting user alerts: {str(e)}")
            raise

    async def mark_alert_as_read(self, alert_id: str, alert_type: AlertType):
        """Mark an alert as read."""
        try:
            await self.initialize()  # Ensure collections are initialized
            collection = self.price_drop_alerts_collection if alert_type == AlertType.PRICE_DROP else self.discount_alerts_collection
            result = await collection.update_one(
                {"_id": ObjectId(alert_id)},
                {"$set": {"is_read": True}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking alert as read: {str(e)}")
            raise

    async def create_alert(self, alert: AlertCreate, user_id: str) -> AlertResponse:
        """Create a new price alert."""
        alert_dict = alert.model_dump()
        alert_dict.update({
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True
        })
        
        result = await self.alerts_collection.insert_one(alert_dict)
        alert_dict["id"] = str(result.inserted_id)
        
        return AlertResponse(**alert_dict)

    async def check_all_alerts(self):
        """Check all active alerts and trigger notifications if conditions are met."""
        try:
            # Get all active alerts
            cursor = self.alerts_collection.find({"is_active": True})
            alerts = await cursor.to_list(length=None)
            
            for alert in alerts:
                try:
                    # Get the associated product
                    product = await self.products_collection.find_one({"_id": ObjectId(alert["product_id"])})
                    if not product:
                        logger.warning(f"Product not found for alert {alert['_id']}")
                        continue
                    
                    # Check if price has dropped below threshold
                    if product["current_price"] <= alert["target_price"]:
                        # Create notification
                        notification = {
                            "user_id": alert["user_id"],
                            "title": "Price Drop Alert!",
                            "message": f"Price for {product['name']} has dropped to {product['current_price']} {product['currency']}",
                            "type": "price_drop",
                            "created_at": datetime.utcnow(),
                            "is_read": False,
                            "data": {
                                "product_id": str(product["_id"]),
                                "current_price": product["current_price"],
                                "target_price": alert["target_price"]
                            }
                        }
                        
                        # Insert notification
                        await self.notifications_collection.insert_one(notification)
                        
                        # Deactivate alert if it's a one-time alert
                        if alert.get("alert_type") == "one_time":
                            await self.alerts_collection.update_one(
                                {"_id": alert["_id"]},
                                {"$set": {"is_active": False}}
                            )
                            
                except Exception as e:
                    logger.error(f"Error checking alert {alert['_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in check_all_alerts: {str(e)}")
            raise

# Create a singleton instance of AlertService
alert_service = AlertService()