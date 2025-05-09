from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.alerts import alert_service
from app.services.products import product_service
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs."""
        # Check price drops every hour
        self.scheduler.add_job(
            self.check_price_drops,
            CronTrigger(hour="*"),
            id="check_price_drops",
            name="Check for price drops",
            replace_existing=True
        )

        # Check discounts every 6 hours
        self.scheduler.add_job(
            self.check_discounts,
            CronTrigger(hour="*/6"),
            id="check_discounts",
            name="Check for discounts",
            replace_existing=True
        )

        # Update product prices daily
        self.scheduler.add_job(
            self.update_product_prices,
            CronTrigger(hour=0, minute=0),
            id="update_product_prices",
            name="Update product prices",
            replace_existing=True
        )

        # Clean up old alerts weekly
        self.scheduler.add_job(
            self.cleanup_old_alerts,
            CronTrigger(day_of_week="mon", hour=0, minute=0),
            id="cleanup_old_alerts",
            name="Clean up old alerts",
            replace_existing=True
        )

    async def check_price_drops(self):
        """Check for price drops and create alerts."""
        try:
            logger.info("Checking for price drops...")
            await alert_service.check_price_drops()
            logger.info("Price drop check completed")
        except Exception as e:
            logger.error(f"Error checking price drops: {str(e)}")

    async def check_discounts(self):
        """Check for discounts and create alerts."""
        try:
            logger.info("Checking for discounts...")
            await alert_service.check_discounts()
            logger.info("Discount check completed")
        except Exception as e:
            logger.error(f"Error checking discounts: {str(e)}")

    async def update_product_prices(self):
        """Update product prices."""
        try:
            logger.info("Updating product prices...")
            await product_service.update_all_prices()
            logger.info("Product price update completed")
        except Exception as e:
            logger.error(f"Error updating product prices: {str(e)}")

    async def cleanup_old_alerts(self):
        """Clean up old alerts."""
        try:
            logger.info("Cleaning up old alerts...")
            # Delete alerts older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            # Clean up price drop alerts
            await alert_service.price_drop_alerts.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            # Clean up discount alerts
            await alert_service.discount_alerts.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            logger.info("Alert cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {str(e)}")

    def start(self):
        """Start the scheduler."""
        try:
            self.scheduler.start()
            logger.info("Scheduler started")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            raise

    def shutdown(self):
        """Shutdown the scheduler."""
        try:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {str(e)}")
            raise

# Create scheduler instance
scheduler = Scheduler()