"""
Celery Tasks for Export Automation (Phase 5)

Scheduled tasks for:
- Running due export schedules
- Cleaning up old export files
- Sending scheduled export reports
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='reports.check_and_run_scheduled_exports')
def check_and_run_scheduled_exports():
    """
    Periodic task to check for and execute due export schedules.
    
    This task should be configured in Celery Beat to run every 5-15 minutes.
    It finds all active schedules that are due and executes them.
    
    Returns:
        dict: Summary of execution results
    """
    from reports.services import ScheduledExportRunner
    
    logger.info("Checking for due scheduled exports...")
    
    try:
        runner = ScheduledExportRunner()
        results = runner.run_due_schedules()
        
        logger.info(
            f"Scheduled export check complete: "
            f"{results['total_found']} found, "
            f"{results['successful']} successful, "
            f"{results['failed']} failed"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error checking scheduled exports: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.execute_single_export')
def execute_single_export(schedule_id: str, trigger: str = 'SCHEDULED'):
    """
    Execute a single export schedule asynchronously.
    
    Args:
        schedule_id: UUID of the ExportSchedule to execute
        trigger: How this execution was triggered (SCHEDULED, MANUAL, API)
        
    Returns:
        dict: Export execution results
    """
    from reports.models import ExportSchedule
    from reports.services import ScheduledExportRunner
    
    logger.info(f"Executing export schedule {schedule_id} (trigger: {trigger})...")
    
    try:
        schedule = ExportSchedule.objects.get(id=schedule_id)
        runner = ScheduledExportRunner()
        
        history = runner.execute_schedule(schedule, trigger=trigger)
        
        logger.info(
            f"Export {schedule_id} completed: "
            f"status={history.status}, "
            f"records={history.record_count}, "
            f"size={history.file_size_mb:.2f}MB"
        )
        
        return {
            'schedule_id': str(schedule.id),
            'history_id': str(history.id),
            'status': history.status,
            'record_count': history.record_count,
            'file_size_mb': history.file_size_mb
        }
        
    except ExportSchedule.DoesNotExist:
        logger.error(f"Export schedule {schedule_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error executing export {schedule_id}: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.cleanup_old_exports')
def cleanup_old_exports(days_to_keep: int = 30):
    """
    Clean up export files older than specified days.
    
    This task should be configured in Celery Beat to run daily.
    It removes old export files from storage to free up space.
    
    Args:
        days_to_keep: Number of days to keep export files (default: 30)
        
    Returns:
        dict: Cleanup results
    """
    from reports.services import ExportFileStorage
    
    logger.info(f"Starting cleanup of exports older than {days_to_keep} days...")
    
    try:
        storage = ExportFileStorage()
        results = storage.cleanup_old_exports(days_to_keep=days_to_keep)
        
        logger.info(
            f"Cleanup complete: "
            f"{results['deleted']} files deleted, "
            f"{results['failed']} failed, "
            f"{results['space_freed_mb']:.2f}MB freed"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.send_export_summary_report')
def send_export_summary_report(business_id: str = None):
    """
    Send a summary report of recent export activity.
    
    This task can be scheduled weekly or monthly to provide businesses
    with a summary of their export usage and statistics.
    
    Args:
        business_id: Optional specific business to send report for.
                    If None, sends to all businesses.
        
    Returns:
        dict: Summary of reports sent
    """
    from reports.models import ExportHistory, ExportSchedule
    from accounts.models import Business
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from datetime import timedelta
    
    logger.info("Generating export summary reports...")
    
    try:
        # Get businesses to report on
        if business_id:
            businesses = Business.objects.filter(id=business_id)
        else:
            businesses = Business.objects.filter(
                export_schedules__isnull=False
            ).distinct()
        
        results = {
            'total_businesses': businesses.count(),
            'reports_sent': 0,
            'reports_failed': 0
        }
        
        # Get date range (last 7 days)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)
        
        for business in businesses:
            try:
                # Get export statistics for this business
                exports = ExportHistory.objects.filter(
                    business=business,
                    created_at__gte=start_date,
                    created_at__lte=end_date
                )
                
                if not exports.exists():
                    continue  # Skip if no activity
                
                stats = {
                    'total_exports': exports.count(),
                    'successful': exports.filter(status__in=['COMPLETED', 'EMAILED']).count(),
                    'failed': exports.filter(status='FAILED').count(),
                    'total_records': sum(e.record_count or 0 for e in exports),
                    'total_size_mb': sum(e.file_size_mb or 0 for e in exports)
                }
                
                # Get active schedules
                active_schedules = ExportSchedule.objects.filter(
                    business=business,
                    is_active=True
                ).count()
                
                # Get notification settings for email recipients
                from reports.models import ExportNotificationSettings
                try:
                    notification_settings = ExportNotificationSettings.objects.get(
                        business=business
                    )
                    recipients = notification_settings.default_recipients
                    
                    if not recipients:
                        continue  # Skip if no recipients configured
                    
                except ExportNotificationSettings.DoesNotExist:
                    continue  # Skip if no settings
                
                # Render email
                context = {
                    'business_name': business.name,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'stats': stats,
                    'active_schedules': active_schedules
                }
                
                html_message = render_to_string(
                    'reports/emails/export_summary.html',
                    context
                )
                
                # Send email
                email = EmailMessage(
                    subject=f"Export Activity Summary - {business.name}",
                    body=html_message,
                    from_email='noreply@possystem.com',
                    to=recipients
                )
                email.content_subtype = 'html'
                email.send(fail_silently=False)
                
                results['reports_sent'] += 1
                logger.info(f"Summary report sent to {business.name}")
                
            except Exception as e:
                results['reports_failed'] += 1
                logger.error(
                    f"Failed to send summary for {business.name}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Summary reports complete: "
            f"{results['reports_sent']} sent, "
            f"{results['reports_failed']} failed"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error generating summary reports: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.retry_failed_exports')
def retry_failed_exports(max_retries: int = 3):
    """
    Retry recently failed exports.
    
    This task finds exports that failed in the last 24 hours and retries them
    if they haven't exceeded the maximum retry count.
    
    Args:
        max_retries: Maximum number of retry attempts
        
    Returns:
        dict: Retry results
    """
    from reports.models import ExportHistory, ExportSchedule
    from reports.services import ScheduledExportRunner
    from datetime import timedelta
    
    logger.info("Checking for failed exports to retry...")
    
    try:
        # Find failed exports from last 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        failed_exports = ExportHistory.objects.filter(
            status='FAILED',
            created_at__gte=cutoff_time,
            schedule__isnull=False  # Only retry scheduled exports
        ).select_related('schedule')
        
        results = {
            'total_failed': failed_exports.count(),
            'retried': 0,
            'retry_successful': 0,
            'retry_failed': 0,
            'skipped': 0
        }
        
        for failed_export in failed_exports:
            # Count previous retry attempts for this schedule
            retry_count = ExportHistory.objects.filter(
                schedule=failed_export.schedule,
                created_at__gte=cutoff_time,
                status='FAILED'
            ).count()
            
            if retry_count >= max_retries:
                results['skipped'] += 1
                logger.info(
                    f"Skipping retry for schedule {failed_export.schedule.id}: "
                    f"max retries ({max_retries}) exceeded"
                )
                continue
            
            try:
                results['retried'] += 1
                
                runner = ScheduledExportRunner()
                history = runner.execute_schedule(
                    failed_export.schedule,
                    trigger='SCHEDULED'
                )
                
                if history.status in ['COMPLETED', 'EMAILED']:
                    results['retry_successful'] += 1
                    logger.info(f"Retry successful for schedule {failed_export.schedule.id}")
                else:
                    results['retry_failed'] += 1
                    logger.warning(f"Retry failed for schedule {failed_export.schedule.id}")
                    
            except Exception as e:
                results['retry_failed'] += 1
                logger.error(
                    f"Error retrying export {failed_export.id}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Retry complete: "
            f"{results['retry_successful']} successful, "
            f"{results['retry_failed']} failed, "
            f"{results['skipped']} skipped"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error in retry task: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.generate_sales_report')
def generate_sales_report(business_id: str, start_date: str, end_date: str, format: str = 'pdf', user_id: str = None):
    """
    Generate a sales report asynchronously.
    
    This task generates comprehensive sales reports in the background to avoid
    blocking API requests during heavy data processing.
    
    Args:
        business_id: UUID of the business
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)
        format: Export format ('pdf', 'excel', 'csv')
        user_id: Optional user ID who requested the report
        
    Returns:
        dict: Report generation results with file URL
    """
    from accounts.models import Business
    from sales.models import Sale
    from reports.pdf_exporters import SalesPDFExporter
    from reports.csv_exporters import SalesCSVExporter
    from reports.exporters import SalesExcelExporter
    from django.core.files.base import ContentFile
    from django.utils.dateparse import parse_date
    import io
    
    logger.info(f"Generating sales report for business {business_id} ({start_date} to {end_date})")
    
    try:
        business = Business.objects.get(id=business_id)
        start = parse_date(start_date)
        end = parse_date(end_date)
        
        # Query sales data
        sales = Sale.objects.filter(
            business=business,
            created_at__date__gte=start,
            created_at__date__lte=end
        ).select_related('customer', 'storefront').prefetch_related('sale_items__product')
        
        # Generate report based on format
        if format == 'pdf':
            exporter = SalesPDFExporter()
            file_content = exporter.export(sales, business, start, end)
            filename = f"sales_report_{start_date}_{end_date}.pdf"
            content_type = 'application/pdf'
        elif format == 'excel':
            exporter = SalesExcelExporter()
            file_content = exporter.export(sales, business, start, end)
            filename = f"sales_report_{start_date}_{end_date}.xlsx"
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:  # csv
            exporter = SalesCSVExporter()
            file_content = exporter.export(sales, business, start, end)
            filename = f"sales_report_{start_date}_{end_date}.csv"
            content_type = 'text/csv'
        
        # Save to media storage
        from django.core.files.storage import default_storage
        file_path = f"reports/sales/{business_id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        file_url = default_storage.url(saved_path)
        
        logger.info(f"Sales report generated successfully: {file_url}")
        
        return {
            'status': 'completed',
            'file_url': file_url,
            'filename': filename,
            'record_count': sales.count(),
            'format': format
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error generating sales report: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.generate_inventory_report')
def generate_inventory_report(business_id: str, format: str = 'excel', include_zero_stock: bool = False):
    """
    Generate an inventory report asynchronously.
    
    Args:
        business_id: UUID of the business
        format: Export format ('excel', 'csv', 'pdf')
        include_zero_stock: Whether to include items with zero stock
        
    Returns:
        dict: Report generation results with file URL
    """
    from accounts.models import Business
    from inventory.models import StockProduct
    from reports.exporters import InventoryExcelExporter
    from reports.csv_exporters import InventoryCSVExporter
    from django.core.files.base import ContentFile
    
    logger.info(f"Generating inventory report for business {business_id}")
    
    try:
        business = Business.objects.get(id=business_id)
        
        # Query inventory data
        stock_products = StockProduct.objects.filter(
            business=business
        ).select_related('product', 'supplier')
        
        if not include_zero_stock:
            stock_products = stock_products.exclude(calculated_quantity=0)
        
        # Generate report
        if format == 'excel':
            exporter = InventoryExcelExporter()
            file_content = exporter.export(stock_products, business)
            filename = f"inventory_report_{timezone.now().strftime('%Y%m%d')}.xlsx"
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:  # csv
            exporter = InventoryCSVExporter()
            file_content = exporter.export(stock_products, business)
            filename = f"inventory_report_{timezone.now().strftime('%Y%m%d')}.csv"
            content_type = 'text/csv'
        
        # Save to storage
        from django.core.files.storage import default_storage
        file_path = f"reports/inventory/{business_id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        file_url = default_storage.url(saved_path)
        
        logger.info(f"Inventory report generated successfully: {file_url}")
        
        return {
            'status': 'completed',
            'file_url': file_url,
            'filename': filename,
            'record_count': stock_products.count(),
            'format': format
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error generating inventory report: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.export_customers_to_csv')
def export_customers_to_csv(business_id: str):
    """
    Export customer list to CSV asynchronously.
    
    Args:
        business_id: UUID of the business
        
    Returns:
        dict: Export results with file URL
    """
    from accounts.models import Business
    from sales.models import Customer
    from django.core.files.base import ContentFile
    import csv
    import io
    
    logger.info(f"Exporting customers for business {business_id}")
    
    try:
        business = Business.objects.get(id=business_id)
        
        # Query customers
        customers = Customer.objects.filter(business=business).order_by('name')
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Name', 'Email', 'Phone', 'Address', 'Credit Limit',
            'Current Balance', 'Total Purchases', 'Created Date'
        ])
        
        # Write data
        for customer in customers:
            writer.writerow([
                customer.name,
                customer.email or '',
                customer.phone or '',
                customer.address or '',
                customer.credit_limit or 0,
                customer.current_balance or 0,
                customer.total_purchases or 0,
                customer.created_at.strftime('%Y-%m-%d')
            ])
        
        # Save to storage
        from django.core.files.storage import default_storage
        filename = f"customers_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = f"exports/customers/{business_id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(output.getvalue().encode('utf-8')))
        file_url = default_storage.url(saved_path)
        
        logger.info(f"Customers exported successfully: {file_url}")
        
        return {
            'status': 'completed',
            'file_url': file_url,
            'filename': filename,
            'record_count': customers.count()
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error exporting customers: {str(e)}", exc_info=True)
        raise


@shared_task(name='reports.export_transactions_to_excel')
def export_transactions_to_excel(business_id: str, start_date: str, end_date: str):
    """
    Export financial transactions to Excel asynchronously.
    
    Args:
        business_id: UUID of the business
        start_date: Start date in ISO format
        end_date: End date in ISO format
        
    Returns:
        dict: Export results with file URL
    """
    from accounts.models import Business
    from sales.models import Sale, Payment
    from django.utils.dateparse import parse_date
    from openpyxl import Workbook
    from django.core.files.base import ContentFile
    import io
    
    logger.info(f"Exporting transactions for business {business_id}")
    
    try:
        business = Business.objects.get(id=business_id)
        start = parse_date(start_date)
        end = parse_date(end_date)
        
        # Create workbook
        wb = Workbook()
        
        # Sales sheet
        ws_sales = wb.active
        ws_sales.title = "Sales"
        ws_sales.append(['Date', 'Reference', 'Customer', 'Total Amount', 'Payment Status', 'Created By'])
        
        sales = Sale.objects.filter(
            business=business,
            created_at__date__gte=start,
            created_at__date__lte=end
        ).select_related('customer', 'created_by')
        
        for sale in sales:
            ws_sales.append([
                sale.created_at.strftime('%Y-%m-%d %H:%M'),
                sale.reference_number,
                sale.customer.name if sale.customer else 'Walk-in',
                float(sale.total_amount),
                sale.payment_status,
                sale.created_by.name if sale.created_by else ''
            ])
        
        # Payments sheet
        ws_payments = wb.create_sheet("Payments")
        ws_payments.append(['Date', 'Reference', 'Customer', 'Amount', 'Method', 'Status'])
        
        payments = Payment.objects.filter(
            business=business,
            created_at__date__gte=start,
            created_at__date__lte=end
        ).select_related('customer')
        
        for payment in payments:
            ws_payments.append([
                payment.created_at.strftime('%Y-%m-%d %H:%M'),
                payment.reference or '',
                payment.customer.name if payment.customer else '',
                float(payment.amount),
                payment.payment_method,
                payment.status
            ])
        
        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        # Save to storage
        from django.core.files.storage import default_storage
        filename = f"transactions_{start_date}_{end_date}.xlsx"
        file_path = f"exports/transactions/{business_id}/{filename}"
        saved_path = default_storage.save(file_path, ContentFile(buffer.read()))
        file_url = default_storage.url(saved_path)
        
        logger.info(f"Transactions exported successfully: {file_url}")
        
        return {
            'status': 'completed',
            'file_url': file_url,
            'filename': filename,
            'sales_count': sales.count(),
            'payments_count': payments.count()
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error exporting transactions: {str(e)}", exc_info=True)
        raise
