from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.notification import notification_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs."""
        # Check price drops at the interval specified in .env (PRICE_CHECK_INTERVAL in minutes)
        self.scheduler.add_job(
            self.check_price_drops,
            "interval",
            minutes=int(settings.PRICE_CHECK_INTERVAL),
            id="check_price_drops",
            name="Check for price drops and send notifications",
            replace_existing=True
        )

    async def check_price_drops(self):
        """Check for price drops and send notifications using notification_service."""
        try:
            logger.info("Checking for price drops...")
            await notification_service.check_and_notify_price_drops()
            logger.info("Price drop check and notifications completed")
        except Exception as e:
            logger.error(f"Error checking price drops: {str(e)}")

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

# Define setup_scheduler and shutdown_scheduler functions
def setup_scheduler():
    """Initialize the scheduler."""
    scheduler.start()

def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown()