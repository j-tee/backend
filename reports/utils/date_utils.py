"""
Date Range Utilities for Reports

Handles date validation, parsing, and preset period calculations.
"""

from datetime import datetime, timedelta, date
from typing import Tuple, Optional, Dict
from django.utils import timezone


class DateRangeValidator:
    """Validate and normalize date ranges for reports"""
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """
        Parse date string to date object
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            date object or None if invalid
        """
        if not date_str:
            return None
        
        try:
            # Try parsing ISO format
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            try:
                # Try parsing datetime format
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except (ValueError, TypeError):
                return None
    
    @staticmethod
    def validate(
        start_date: str,
        end_date: str,
        max_days: int = 365,
        allow_future: bool = False
    ) -> Tuple[bool, Optional[str], Optional[date], Optional[date]]:
        """
        Validate date range
        
        Args:
            start_date: Start date string
            end_date: End date string
            max_days: Maximum allowed days in range
            allow_future: Whether future dates are allowed
            
        Returns:
            Tuple of (is_valid, error_message, parsed_start, parsed_end)
        """
        # Parse dates
        start = DateRangeValidator.parse_date(start_date)
        end = DateRangeValidator.parse_date(end_date)
        
        # Check if dates are valid
        if not start:
            return False, "Invalid start_date format. Use YYYY-MM-DD", None, None
        
        if not end:
            return False, "Invalid end_date format. Use YYYY-MM-DD", None, None
        
        # Check if start is before end
        if start > end:
            return False, "start_date must be before or equal to end_date", start, end
        
        # Check if dates are not in the future (if not allowed)
        today = timezone.now().date()
        if not allow_future:
            if start > today:
                return False, "start_date cannot be in the future", start, end
            if end > today:
                return False, "end_date cannot be in the future", start, end
        
        # Check if range doesn't exceed max_days
        date_diff = (end - start).days
        if date_diff > max_days:
            return False, f"Date range cannot exceed {max_days} days", start, end
        
        return True, None, start, end
    
    @staticmethod
    def get_default_range(days: int = 30) -> Tuple[date, date]:
        """
        Get default date range (last N days)
        
        Args:
            days: Number of days to go back
            
        Returns:
            Tuple of (start_date, end_date)
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date


def get_date_range_presets() -> Dict[str, Tuple[date, date]]:
    """
    Get predefined date range presets
    
    Returns:
        Dictionary of preset names to (start_date, end_date) tuples
    """
    today = timezone.now().date()
    
    # Get start of current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    
    # Get start of current month
    start_of_month = today.replace(day=1)
    
    # Get start of current year
    start_of_year = today.replace(month=1, day=1)
    
    # Get start of previous month
    first_of_current_month = today.replace(day=1)
    last_day_prev_month = first_of_current_month - timedelta(days=1)
    start_of_prev_month = last_day_prev_month.replace(day=1)
    
    return {
        'today': (today, today),
        'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
        'last_7_days': (today - timedelta(days=7), today),
        'last_30_days': (today - timedelta(days=30), today),
        'last_90_days': (today - timedelta(days=90), today),
        'this_week': (start_of_week, today),
        'this_month': (start_of_month, today),
        'last_month': (start_of_prev_month, last_day_prev_month),
        'this_year': (start_of_year, today),
        'last_365_days': (today - timedelta(days=365), today),
    }


def get_preset_range(preset_name: str) -> Optional[Tuple[date, date]]:
    """
    Get date range for a preset
    
    Args:
        preset_name: Name of the preset
        
    Returns:
        Tuple of (start_date, end_date) or None if preset not found
    """
    presets = get_date_range_presets()
    return presets.get(preset_name)


def format_date_for_display(date_obj: date) -> str:
    """
    Format date for display in reports
    
    Args:
        date_obj: Date object
        
    Returns:
        Formatted date string
    """
    return date_obj.strftime('%Y-%m-%d')


def get_period_description(start_date: date, end_date: date) -> str:
    """
    Get human-readable period description
    
    Args:
        start_date: Period start
        end_date: Period end
        
    Returns:
        Description string
    """
    days = (end_date - start_date).days
    
    if days == 0:
        return f"{start_date.strftime('%B %d, %Y')}"
    elif days == 1:
        return f"{start_date.strftime('%B %d')} - {end_date.strftime('%d, %Y')}"
    elif days <= 7:
        return f"{days + 1} days ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    elif days <= 31:
        return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    else:
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
