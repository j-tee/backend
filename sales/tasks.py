import logging

from celery import shared_task

from sales.models import StockReservation

logger = logging.getLogger(__name__)


@shared_task(name="sales.tasks.release_expired_reservations", ignore_result=True)
def release_expired_reservations():
    """Celery task that releases all expired stock reservations."""
    released = StockReservation.release_expired()
    if released:
        logger.info("Released %s expired stock reservations", released)
    else:
        logger.debug("No expired reservations to release.")
    return released
