"""
Standardized Response Utilities for Reports

Provides consistent response formats across all analytical reports.
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status


class ReportError:
    """Standard error response structure"""
    
    # Error codes
    INVALID_DATE_RANGE = 'INVALID_DATE_RANGE'
    MISSING_REQUIRED_PARAM = 'MISSING_REQUIRED_PARAM'
    BUSINESS_NOT_FOUND = 'BUSINESS_NOT_FOUND'
    INSUFFICIENT_DATA = 'INSUFFICIENT_DATA'
    INVALID_FILTER = 'INVALID_FILTER'
    DATABASE_ERROR = 'DATABASE_ERROR'
    PERMISSION_DENIED = 'PERMISSION_DENIED'
    
    @staticmethod
    def create(code: str, message: str, details: Optional[Dict] = None) -> Dict:
        """
        Create standardized error response
        
        Args:
            code: Error code from class constants
            message: Human-readable error message
            details: Additional error details
            
        Returns:
            Dict containing error information
        """
        return {
            'success': False,
            'data': None,
            'error': {
                'code': code,
                'message': message,
                'details': details or {},
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        }
    
    @staticmethod
    def invalid_date_range(start_date: str, end_date: str, reason: str = None) -> Dict:
        """Create invalid date range error"""
        message = reason or "Invalid date range provided"
        return ReportError.create(
            ReportError.INVALID_DATE_RANGE,
            message,
            {'start_date': start_date, 'end_date': end_date}
        )
    
    @staticmethod
    def missing_param(param_name: str) -> Dict:
        """Create missing parameter error"""
        return ReportError.create(
            ReportError.MISSING_REQUIRED_PARAM,
            f"Required parameter '{param_name}' is missing",
            {'parameter': param_name}
        )
    
    @staticmethod
    def insufficient_data(message: str = None) -> Dict:
        """Create insufficient data error"""
        return ReportError.create(
            ReportError.INSUFFICIENT_DATA,
            message or "Insufficient data to generate report",
            {}
        )


class ReportResponse:
    """Standard report response builder"""
    
    @staticmethod
    def success(
        summary: Dict[str, Any],
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> Response:
        """
        Create successful report response
        
        Args:
            summary: Aggregated metrics (totals, averages, etc.)
            results: Detailed breakdown/list of items
            metadata: Report metadata (period, filters, etc.)
            
        Returns:
            DRF Response object with standardized structure
        """
        response_data = {
            'success': True,
            'data': {
                'summary': summary,
                'results': results,
                'metadata': {
                    'generated_at': datetime.utcnow().isoformat() + 'Z',
                    'total_records': len(results),
                    **metadata
                }
            },
            'error': None
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    @staticmethod
    def error(error_dict: Dict, http_status: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """
        Create error response
        
        Args:
            error_dict: Error dictionary from ReportError
            http_status: HTTP status code
            
        Returns:
            DRF Response object with error
        """
        return Response(error_dict, status=http_status)
    
    @staticmethod
    def paginated(
        summary: Dict[str, Any],
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        page: int,
        page_size: int,
        total_count: int
    ) -> Response:
        """
        Create paginated report response
        
        Args:
            summary: Aggregated metrics
            results: Current page of results
            metadata: Report metadata
            page: Current page number
            page_size: Items per page
            total_count: Total items available
            
        Returns:
            DRF Response with pagination info
        """
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
        
        response_data = {
            'success': True,
            'data': {
                'summary': summary,
                'results': results,
                'metadata': {
                    'generated_at': datetime.utcnow().isoformat() + 'Z',
                    'total_records': total_count,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_previous': page > 1
                    },
                    **metadata
                }
            },
            'error': None
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ReportMetadata:
    """Helper for building report metadata"""
    
    @staticmethod
    def create(
        period_start: str = None,
        period_end: str = None,
        filters_applied: Dict = None,
        additional: Dict = None
    ) -> Dict:
        """
        Create standard metadata dictionary
        
        Args:
            period_start: Start date of report period
            period_end: End date of report period
            filters_applied: Dictionary of applied filters
            additional: Any additional metadata
            
        Returns:
            Metadata dictionary
        """
        metadata = {}
        
        if period_start or period_end:
            metadata['period'] = {}
            if period_start:
                metadata['period']['start'] = period_start
            if period_end:
                metadata['period']['end'] = period_end
        
        if filters_applied:
            metadata['filters_applied'] = filters_applied
        
        if additional:
            metadata.update(additional)
        
        return metadata
