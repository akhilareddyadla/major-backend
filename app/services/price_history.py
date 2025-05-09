from datetime import datetime
from typing import List, Optional
from app.db.mongodb import get_collection
from app.models.price_history import PriceHistory
from bson import ObjectId
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class PriceHistoryService:
    def __init__(self):
        self.price_history_collection = None
        self._initialized = False

    async def initialize(self):
        """Initialize the price history collection."""
        if self._initialized:
            return

        try:
            self.price_history_collection = get_collection("price_history")
            logger.info("PriceHistoryService initialized successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"Error initializing PriceHistoryService: {str(e)}")
            raise

    async def get_price_history(self, product_id: str) -> List[PriceHistory]:
        """Get price history for a product."""
        try:
            if not self._initialized:
                await self.initialize()

            # Validate product_id
            try:
                object_id = ObjectId(product_id)
            except Exception as e:
                logger.error(f"Invalid product ID format: {product_id}")
                return []

            # Get price history from collection
            cursor = self.price_history_collection.find({"product_id": product_id})
            price_history = await cursor.to_list(length=None)
            
            # Also get product's embedded price history
            product_collection = get_collection("products")
            product = await product_collection.find_one(
                {"_id": object_id},
                {"price_history": 1}
            )
            
            # Combine both sources of price history
            combined_history = []
            
            # Add from price_history collection
            for entry in price_history:
                try:
                    price = Decimal(str(entry.get("price", 0)))
                    if price < 0:
                        logger.warning(f"Skipping negative price entry: {price}")
                        continue

                    timestamp = entry.get("timestamp")
                    if not isinstance(timestamp, datetime):
                        timestamp = datetime.utcnow()

                    formatted_entry = PriceHistory(
                        id=str(entry.get("_id")),
                        product_id=product_id,
                        price=price,
                        timestamp=timestamp,
                        currency=entry.get("currency", "INR"),
                        discount_percentage=float(entry["discount_percentage"]) if entry.get("discount_percentage") is not None else None,
                        is_discount=bool(entry.get("is_discount", False)),
                        source=entry.get("source", "manual")
                    )
                    combined_history.append(formatted_entry)
                except Exception as e:
                    logger.error(f"Error formatting price history entry: {str(e)}")
                    continue
            
            # Add from product's embedded price history
            if product and "price_history" in product:
                for entry in product["price_history"]:
                    try:
                        price = Decimal(str(entry.get("price", 0)))
                        if price < 0:
                            logger.warning(f"Skipping negative price entry: {price}")
                            continue

                        timestamp = entry.get("timestamp")
                        if not isinstance(timestamp, datetime):
                            timestamp = datetime.utcnow()

                        formatted_entry = PriceHistory(
                            product_id=product_id,
                            price=price,
                            timestamp=timestamp,
                            currency=entry.get("currency", "INR"),
                            discount_percentage=float(entry["discount_percentage"]) if entry.get("discount_percentage") is not None else None,
                            is_discount=bool(entry.get("is_discount", False)),
                            source=entry.get("source", "embedded")
                        )
                        combined_history.append(formatted_entry)
                    except Exception as e:
                        logger.error(f"Error formatting embedded price history entry: {str(e)}")
                        continue

            # Sort by timestamp
            combined_history.sort(key=lambda x: x.timestamp)
            
            # Ensure at least one entry
            if not combined_history:
                # Create a default entry with current price
                product = await product_collection.find_one({"_id": object_id})
                if product:
                    current_price = Decimal(str(product.get("current_price", 0)))
                    default_entry = PriceHistory(
                        product_id=product_id,
                        price=current_price,
                        timestamp=datetime.utcnow(),
                        currency=product.get("currency", "INR"),
                        is_discount=False,
                        source="default"
                    )
                    combined_history.append(default_entry)

            logger.info(f"Retrieved {len(combined_history)} price history entries for product {product_id}")
            return combined_history

        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            return []

    async def add_price_history(self, price_history: PriceHistory) -> bool:
        """Add a new price history entry."""
        try:
            if not self._initialized:
                await self.initialize()

            # Validate price
            if price_history.price < 0:
                logger.error(f"Invalid negative price: {price_history.price}")
                return False

            # Ensure timestamp is datetime
            if not isinstance(price_history.timestamp, datetime):
                price_history.timestamp = datetime.utcnow()

            # Convert to dict and ensure proper types
            entry_dict = {
                "product_id": price_history.product_id,
                "price": float(price_history.price),
                "timestamp": price_history.timestamp,
                "currency": price_history.currency or "INR",
                "discount_percentage": float(price_history.discount_percentage) if price_history.discount_percentage is not None else None,
                "is_discount": bool(price_history.is_discount),
                "source": price_history.source or "manual"
            }

            # Add to price_history collection
            result = await self.price_history_collection.insert_one(entry_dict)
            
            if result.inserted_id:
                # Also update the product's embedded price history
                try:
                    product_collection = get_collection("products")
                    await product_collection.update_one(
                        {"_id": ObjectId(price_history.product_id)},
                        {
                            "$push": {
                                "price_history": {
                                    "price": float(price_history.price),
                                    "timestamp": price_history.timestamp,
                                    "currency": price_history.currency or "INR",
                                    "discount_percentage": float(price_history.discount_percentage) if price_history.discount_percentage is not None else None,
                                    "is_discount": bool(price_history.is_discount)
                                }
                            }
                        }
                    )
                except Exception as e:
                    logger.error(f"Error updating product's embedded price history: {str(e)}")
            
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding price history: {str(e)}")
            return False

# Create service instance
price_history_service = PriceHistoryService() 