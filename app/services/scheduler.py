from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any
from bson import ObjectId

from app.services.apify import ApifyAmazonScraper
from app.services.notification import NotificationService
from app.db.mongodb import get_database
from app.core.config import settings
from app.services.price_extractor import PriceExtractor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceCheckScheduler:
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.db = None
        self.initialized = False
        self.scraper = None
        self.notifier = None

    async def initialize(self):
        """Initialize the scheduler."""
        if not self.initialized:
            self.db = get_database()
            
            # Configure executors
            executors = {
                'default': ThreadPoolExecutor(20),
                'processpool': ProcessPoolExecutor(5)
            }
            
            # Configure job defaults
            job_defaults = {
                'coalesce': False,
                'max_instances': 3
            }
            
            # Create scheduler with memory storage
            self.scheduler = AsyncIOScheduler(
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC'
            )
            
            # Add error listener
            self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
            
            self.initialized = True
            logger.info("PriceCheckScheduler initialized successfully")

    def _job_listener(self, event):
        """Handle job execution events."""
        if event.exception:
            logger.error(f'Job {event.job_id} failed: {str(event.exception)}')
        else:
            logger.info(f'Job {event.job_id} completed successfully')

    @staticmethod
    async def check_price_drops(scraper: ApifyAmazonScraper, notifier: NotificationService, price_extractor: PriceExtractor):
        """Check for price drops across all tracked products."""
        try:
            db = get_database()
            # Get all active products with price alerts
            products = await db.products.find({
                "is_active": True,
                "target_price": {"$exists": True}
            }).to_list(length=None)

            for product in products:
                try:
                    logger.info(f"Checking price for product: {product.get('name', product.get('url'))}")
                    # Fetch prices using the PriceExtractor for multiple sites
                    # Note: get_product_details returns (product_name, prices_dict)
                    product_name_from_extractor, fetched_prices = await price_extractor.get_product_details(product["url"])

                    if not fetched_prices:
                        logger.warning(f"Could not fetch prices for product {product['_id']}")
                        continue

                    # Extract prices for each platform, handle None or 'Not found'
                    amazon_price_str = fetched_prices.get('amazon')
                    flipkart_price_str = fetched_prices.get('flipkart')
                    reliance_digital_price_str = fetched_prices.get('reliancedigital')

                    # Convert prices to float, handling potential errors and 'Not found'
                    amazon_price = float(amazon_price_str) if amazon_price_str not in [None, 'Not found', 'Error'] else None
                    flipkart_price = float(flipkart_price_str) if flipkart_price_str not in [None, 'Not found', 'Error'] else None
                    reliance_digital_price = float(reliance_digital_price_str) if reliance_digital_price_str not in [None, 'Not found', 'Error'] else None

                    # Find the lowest valid fetched price
                    valid_prices = [p for p in [amazon_price, flipkart_price, reliance_digital_price] if p is not None]
                    lowest_price = min(valid_prices) if valid_prices else None

                    # Get previous current price from the database
                    previous_current_price = product.get("current_price")

                    # Prepare update data for the product
                    update_data = {
                        "last_checked": datetime.utcnow(),
                        "amazon_price": amazon_price,
                        "flipkart_price": flipkart_price,
                        "reliance_digital_price": reliance_digital_price,
                        "current_price": lowest_price # Update current_price to the lowest found price
                    }

                    # Update product prices in the database
                    await db.products.update_one(
                        {"_id": product["_id"]},
                        {"$set": update_data}
                    )

                    # Check if the lowest price has dropped to or below the target price
                    # Ensure previous_current_price is treated as a number for comparison if it exists
                    previous_price_numeric = float(previous_current_price) if isinstance(previous_current_price, (int, float, str)) and str(previous_current_price).replace('.', '', 1).isdigit() else None

                    if lowest_price is not None and lowest_price <= product["target_price"]:
                        # Check if this is a *new* price drop to or below the target
                        # It's a new drop if there was no previous price, or the previous price was above the target, or the new price is lower than the previous price
                        is_new_drop = False
                        if previous_price_numeric is None or previous_price_numeric > product["target_price"] or lowest_price < previous_price_numeric:
                             is_new_drop = True

                        if is_new_drop:
                            logger.info(f"Price drop detected for product {product['_id']}. New lowest price: {lowest_price}, Target price: {product['target_price']}")

                            # Create price drop alert
                            price_drop_alert = {
                                "user_id": product["user_id"],
                                "product_id": str(product["_id"]),
                                "product_name": product.get('name', product_name_from_extractor or product.get('title', 'Unknown Product')),
                                "product_url": product["url"],
                                "original_price": previous_price_numeric or lowest_price, # Use previous numeric price if available
                                "current_price": lowest_price,
                                "price_drop": (previous_price_numeric or lowest_price) - lowest_price if previous_price_numeric is not None else 0.0,
                                "percentage_drop": ((previous_price_numeric or lowest_price) - lowest_price) / (previous_price_numeric or lowest_price) * 100 if previous_price_numeric is not None and (previous_price_numeric or lowest_price) > 0 else 0.0,
                                "alert_type": "PRICE_DROP",
                                "created_at": datetime.utcnow(),
                                "amazon_price": amazon_price,
                                "flipkart_price": flipkart_price,
                                "reliance_digital_price": reliance_digital_price,
                                "message": f"Price drop alert for {product.get('name', product_name_from_extractor or product.get('title', 'Unknown Product'))}! Lowest price is now {lowest_price} (Target: {product['target_price']})."
                            }

                            # Get user details
                            user = await db.users.find_one({"_id": ObjectId(product["user_id"])})
                            if user:
                                logger.info(f"Sending notification to user {user.get('email') or user['_id']}")
                                # Send notification using the notifier service
                                await notifier.send_notification(
                                    user_id=str(user["_id"]),
                                    user_email=user.get("email"),
                                    alert=price_drop_alert # Pass the created alert dictionary
                                )

                except Exception as e:
                    logger.error(f"Error processing product {product['_id']}: {str(e)}", exc_info=True)
                    continue

        except Exception as e:
            logger.error(f"Error in check_price_drops: {str(e)}", exc_info=True)
            raise

    def setup_scheduler(self, scraper: ApifyAmazonScraper, notifier: NotificationService, price_extractor: PriceExtractor):
        """Set up the scheduler with price check jobs."""
        try:
            if not self.initialized:
                raise RuntimeError("Scheduler not initialized. Call initialize() first.")

            self.scraper = scraper
            self.notifier = notifier

            # Add daily price check job
            self.scheduler.add_job(
                PriceCheckScheduler.check_price_drops,
                trigger=CronTrigger(hour=0, minute=0),  # Run at midnight UTC
                args=[scraper, notifier, price_extractor],
                id='daily_price_check',
                replace_existing=True
            )

            # Add hourly price check
            self.scheduler.add_job(
                PriceCheckScheduler.check_price_drops,
                trigger=IntervalTrigger(hours=1),
                args=[scraper, notifier, price_extractor],
                id='hourly_price_check',
                replace_existing=True
            )

            # Start the scheduler
            self.scheduler.start()
            logger.info("Price check scheduler started successfully")

        except Exception as e:
            logger.error(f"Error setting up scheduler: {str(e)}")
            raise

    async def shutdown(self):
        """Shutdown the scheduler gracefully."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Price check scheduler shut down successfully")

# Create a singleton instance
price_check_scheduler = PriceCheckScheduler() 