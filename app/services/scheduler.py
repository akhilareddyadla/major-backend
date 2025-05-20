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
    async def check_price_drops(scraper: ApifyAmazonScraper, notifier: NotificationService):
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
                    # Fetch current price
                    scraped_data = await scraper.fetch_product_price(product["url"])
                    if not scraped_data or "current_price" not in scraped_data:
                        logger.warning(f"Could not fetch price for product {product['_id']}")
                        continue

                    new_price = scraped_data["current_price"]
                    current_price = product.get("current_price")
                    
                    # Update product price
                    await db.products.update_one(
                        {"_id": product["_id"]},
                        {
                            "$set": {
                                "current_price": new_price,
                                "currency": scraped_data.get("currency", "INR"),
                                "last_checked": datetime.utcnow()
                            }
                        }
                    )

                    # Check if price has dropped below target
                    if new_price and new_price <= product["target_price"]:
                        # Create price drop alert
                        price_drop_alert = {
                            "user_id": product["user_id"],
                            "product_id": str(product["_id"]),
                            "product_name": product["title"],
                            "product_url": product["url"],
                            "original_price": current_price or new_price,
                            "current_price": new_price,
                            "price_drop": (current_price or new_price) - new_price,
                            "percentage_drop": ((current_price or new_price) - new_price) / (current_price or new_price) * 100,
                            "alert_type": "PRICE_DROP",
                            "created_at": datetime.utcnow()
                        }

                        # Get user details
                        user = await db.users.find_one({"_id": ObjectId(product["user_id"])})
                        if user:
                            await notifier.send_notification(
                                user_id=str(user["_id"]),
                                user_email=user.get("email"),
                                alert=price_drop_alert
                            )

                except Exception as e:
                    logger.error(f"Error processing product {product['_id']}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error in check_price_drops: {str(e)}")
            raise

    def setup_scheduler(self, scraper: ApifyAmazonScraper, notifier: NotificationService):
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
                args=[scraper, notifier],
                id='daily_price_check',
                replace_existing=True
            )

            # Add hourly price check
            self.scheduler.add_job(
                PriceCheckScheduler.check_price_drops,
                trigger=IntervalTrigger(hours=1),
                args=[scraper, notifier],
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