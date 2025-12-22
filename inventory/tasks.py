"""
Celery tasks for Inventory Management
Handles async notifications for stock alerts and inventory updates
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
import logging

logger = logging.getLogger(__name__)


@shared_task(name='inventory.send_low_stock_alert')
def send_low_stock_alert(business_id: str, product_ids: list = None):
    """
    Send email alert for low stock items.
    
    Args:
        business_id: UUID of the business
        product_ids: Optional list of specific product IDs to alert about
        
    Returns:
        dict: Alert results
    """
    from accounts.models import Business
    from inventory.models import StockProduct
    from django.db.models import Q
    
    logger.info(f"Checking low stock for business {business_id}")
    
    try:
        business = Business.objects.select_related('owner').get(id=business_id)
        
        # Query low stock items
        low_stock_query = StockProduct.objects.filter(business=business)
        
        if product_ids:
            low_stock_query = low_stock_query.filter(product_id__in=product_ids)
        
        # Items with stock below reorder level or minimum stock threshold
        low_stock_items = low_stock_query.filter(
            Q(calculated_quantity__lte=models.F('reorder_level')) |
            Q(calculated_quantity__lte=5)  # Default minimum threshold
        ).select_related('product', 'supplier')
        
        if not low_stock_items.exists():
            logger.info(f"No low stock items for business {business_id}")
            return {
                'status': 'no_alerts',
                'business_id': business_id,
                'message': 'All items sufficiently stocked'
            }
        
        # Prepare email content
        items_list = "\n".join([
            f"- {item.product.name}: {item.calculated_quantity} units remaining "
            f"(Reorder level: {item.reorder_level or 'Not set'})"
            for item in low_stock_items[:20]  # Limit to 20 items in email
        ])
        
        subject = f"Low Stock Alert - {business.name}"
        message = f"""
Hello {business.owner.name},

The following items are running low on stock:

{items_list}

{f'...and {low_stock_items.count() - 20} more items' if low_stock_items.count() > 20 else ''}

Total items with low stock: {low_stock_items.count()}

Please review your inventory and consider reordering these items.

Best regards,
POS Backend Team
"""
        
        # Send email
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [business.owner.email],
            fail_silently=False,
        )
        
        logger.info(f"Low stock alert sent to {business.owner.email} for {low_stock_items.count()} items")
        
        return {
            'status': 'sent',
            'business_id': business_id,
            'items_count': low_stock_items.count(),
            'recipient': business.owner.email
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending low stock alert: {str(e)}", exc_info=True)
        raise


@shared_task(name='inventory.send_stock_movement_report')
def send_stock_movement_report(business_id: str, period_days: int = 7):
    """
    Send periodic stock movement report.
    
    Args:
        business_id: UUID of the business
        period_days: Number of days to report on
        
    Returns:
        dict: Report results
    """
    from accounts.models import Business
    from sales.models import Sale, SaleItem
    from django.db.models import Sum, Count
    from datetime import timedelta
    
    logger.info(f"Generating stock movement report for business {business_id}")
    
    try:
        business = Business.objects.select_related('owner').get(id=business_id)
        cutoff_date = timezone.now() - timedelta(days=period_days)
        
        # Get sales data
        sales = Sale.objects.filter(
            business=business,
            created_at__gte=cutoff_date
        )
        
        # Top selling items
        top_items = SaleItem.objects.filter(
            sale__in=sales
        ).values('product__name').annotate(
            total_quantity=Sum('quantity'),
            total_sales=Count('id')
        ).order_by('-total_quantity')[:10]
        
        if not top_items:
            logger.info(f"No sales data for business {business_id} in last {period_days} days")
            return {
                'status': 'no_data',
                'business_id': business_id,
                'period_days': period_days
            }
        
        # Prepare email content
        items_list = "\n".join([
            f"{idx + 1}. {item['product__name']}: {item['total_quantity']} units sold ({item['total_sales']} transactions)"
            for idx, item in enumerate(top_items)
        ])
        
        subject = f"Stock Movement Report - {business.name} (Last {period_days} Days)"
        message = f"""
Hello {business.owner.name},

Here's your stock movement report for the last {period_days} days:

TOP SELLING ITEMS:
{items_list}

Total Sales: {sales.count()} transactions
Total Revenue: ₵{sales.aggregate(total=Sum('total_amount'))['total'] or 0}

This report helps you track inventory turnover and identify your best-selling products.

Best regards,
POS Backend Team
"""
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [business.owner.email],
            fail_silently=False,
        )
        
        logger.info(f"Stock movement report sent to {business.owner.email}")
        
        return {
            'status': 'sent',
            'business_id': business_id,
            'period_days': period_days,
            'top_items_count': len(top_items),
            'total_sales': sales.count()
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending stock movement report: {str(e)}", exc_info=True)
        raise


@shared_task(name='inventory.check_expiring_products')
def check_expiring_products(business_id: str = None, days_threshold: int = 30):
    """
    Check for products approaching expiration and send alerts.
    
    Args:
        business_id: Optional specific business (if None, checks all)
        days_threshold: Alert when products expire within this many days
        
    Returns:
        dict: Check results
    """
    from accounts.models import Business
    from inventory.models import StockProduct
    from datetime import timedelta
    
    logger.info(f"Checking expiring products (threshold: {days_threshold} days)")
    
    try:
        expiry_cutoff = timezone.now() + timedelta(days=days_threshold)
        
        if business_id:
            businesses = [Business.objects.get(id=business_id)]
        else:
            businesses = Business.objects.filter(is_active=True)
        
        results = {
            'businesses_checked': len(businesses),
            'alerts_sent': 0,
            'total_expiring_items': 0
        }
        
        for business in businesses:
            # Find expiring stock (if expiry_date field exists)
            expiring_items = StockProduct.objects.filter(
                business=business,
                expiry_date__lte=expiry_cutoff,
                expiry_date__gte=timezone.now()  # Not already expired
            ).select_related('product')
            
            if not expiring_items.exists():
                continue
            
            results['total_expiring_items'] += expiring_items.count()
            
            # Prepare alert
            items_list = "\n".join([
                f"- {item.product.name}: Expires {item.expiry_date.strftime('%Y-%m-%d')} ({item.calculated_quantity} units)"
                for item in expiring_items[:20]
            ])
            
            subject = f"Product Expiration Alert - {business.name}"
            message = f"""
Hello {business.owner.name},

The following products are expiring within {days_threshold} days:

{items_list}

{f'...and {expiring_items.count() - 20} more items' if expiring_items.count() > 20 else ''}

Total expiring items: {expiring_items.count()}

Please review and take appropriate action (promotions, returns, etc.).

Best regards,
POS Backend Team
"""
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [business.owner.email],
                fail_silently=False,
            )
            
            results['alerts_sent'] += 1
            logger.info(f"Expiration alert sent to {business.owner.email} for {expiring_items.count()} items")
        
        logger.info(
            f"Expiration check complete: {results['alerts_sent']} alerts sent, "
            f"{results['total_expiring_items']} expiring items"
        )
        
        return results
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error checking expiring products: {str(e)}", exc_info=True)
        raise
