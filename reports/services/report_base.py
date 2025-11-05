"""
Base Report Builder Classes

Provides foundation for all analytical reports with common patterns.
"""

from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import date
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import QuerySet
from rest_framework import status as http_status

# Subscription enforcement
from subscriptions.permissions import RequiresSubscriptionForReports

from reports.utils.response import ReportResponse, ReportError, ReportMetadata
from reports.utils.date_utils import DateRangeValidator


class BusinessFilterMixin:
    """Mixin to ensure all queries are scoped to user's business"""
    
    def get_business_id(self, request) -> Optional[int]:
        """
        Get the business ID for the current user
        
        Args:
            request: DRF request object
            
        Returns:
            Business ID or None
        """
        from accounts.models import BusinessMembership
        
        user = request.user
        
        # Use the same approach as working ViewSets
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            return membership.business.id
        
        return None
    
    def get_business_or_error(self, request) -> Tuple[Optional[int], Optional[Dict]]:
        """
        Get business ID or return error response data
        
        Args:
            request: DRF request object
            
        Returns:
            Tuple of (business_id, error_dict)
        """
        business_id = self.get_business_id(request)
        
        if not business_id:
            error = ReportError.create(
                ReportError.BUSINESS_NOT_FOUND,
                "No business associated with this user",
                {}
            )
            return None, error
        
        return business_id, None
    
    def filter_by_business(self, queryset: QuerySet, business_id: int) -> QuerySet:
        """
        Filter queryset by business
        
        Args:
            queryset: Django queryset
            business_id: Business ID to filter by
            
        Returns:
            Filtered queryset
        """
        return queryset.filter(business_id=business_id)


class DateRangeFilterMixin:
    """Mixin to handle date range filtering"""
    
    def get_date_range(
        self,
        request,
        start_param: str = 'start_date',
        end_param: str = 'end_date',
        default_days: int = 30,
        max_days: int = 365
    ) -> Tuple[Optional[date], Optional[date], Optional[Dict]]:
        """
        Extract and validate date range from request
        
        Args:
            request: DRF request object
            start_param: Query param name for start date
            end_param: Query param name for end date
            default_days: Default range if dates not provided
            max_days: Maximum allowed range
            
        Returns:
            Tuple of (start_date, end_date, error_dict)
        """
        start_str = request.query_params.get(start_param)
        end_str = request.query_params.get(end_param)
        
        # If no dates provided, use default range
        if not start_str or not end_str:
            start_date, end_date = DateRangeValidator.get_default_range(default_days)
            return start_date, end_date, None
        
        # Validate date range
        is_valid, error_msg, start_date, end_date = DateRangeValidator.validate(
            start_str, end_str, max_days=max_days
        )
        
        if not is_valid:
            error = ReportError.invalid_date_range(start_str, end_str, error_msg)
            return None, None, error
        
        return start_date, end_date, None


class PaginationMixin:
    """Mixin to handle pagination for reports"""
    
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 500
    
    def get_pagination_params(
        self,
        request,
        page_param: str = 'page',
        page_size_param: str = 'page_size'
    ) -> Tuple[int, int]:
        """
        Extract pagination parameters from request
        
        Args:
            request: DRF request object
            page_param: Query param name for page number
            page_size_param: Query param name for page size
            
        Returns:
            Tuple of (page, page_size)
        """
        try:
            page = int(request.query_params.get(page_param, 1))
            page = max(1, page)  # Ensure page >= 1
        except (ValueError, TypeError):
            page = 1
        
        try:
            page_size = int(request.query_params.get(page_size_param, self.DEFAULT_PAGE_SIZE))
            page_size = min(max(1, page_size), self.MAX_PAGE_SIZE)  # Clamp between 1 and max
        except (ValueError, TypeError):
            page_size = self.DEFAULT_PAGE_SIZE
        
        return page, page_size
    
    def paginate_queryset(
        self,
        queryset: QuerySet,
        page: int,
        page_size: int
    ) -> Tuple[QuerySet, int]:
        """
        Paginate a queryset
        
        Args:
            queryset: Django queryset
            page: Page number (1-indexed)
            page_size: Items per page
            
        Returns:
            Tuple of (paginated_queryset, total_count)
        """
        total_count = queryset.count()
        offset = (page - 1) * page_size
        paginated = queryset[offset:offset + page_size]
        
        return paginated, total_count


class BaseReportView(APIView, BusinessFilterMixin, DateRangeFilterMixin, PaginationMixin):
    """
    Base class for all analytical report views
    
    Provides:
    - Business filtering
    - Date range handling
    - Pagination
    - Standard response formatting
    - Subscription enforcement (requires active subscription with grace period for read-only)
    """
    
    permission_classes = [IsAuthenticated, RequiresSubscriptionForReports]
    
    def build_summary(self, queryset: QuerySet, **kwargs) -> Dict[str, Any]:
        """
        Build summary metrics for the report
        
        Override this in subclasses to provide specific summary calculations
        
        Args:
            queryset: Filtered queryset
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of summary metrics
        """
        raise NotImplementedError("Subclasses must implement build_summary()")
    
    def build_results(self, queryset: QuerySet, **kwargs) -> List[Dict[str, Any]]:
        """
        Build detailed results for the report
        
        Override this in subclasses to provide specific result formatting
        
        Args:
            queryset: Filtered queryset
            **kwargs: Additional parameters
            
        Returns:
            List of result dictionaries
        """
        raise NotImplementedError("Subclasses must implement build_results()")
    
    def get_base_queryset(self) -> QuerySet:
        """
        Get the base queryset for this report
        
        Override this in subclasses to specify the base queryset
        
        Returns:
            Django queryset
        """
        raise NotImplementedError("Subclasses must implement get_base_queryset()")
    
    def apply_filters(self, queryset: QuerySet, request, **kwargs) -> QuerySet:
        """
        Apply additional filters to queryset
        
        Override this in subclasses to add custom filtering logic
        
        Args:
            queryset: Base queryset
            request: DRF request object
            **kwargs: Additional parameters
            
        Returns:
            Filtered queryset
        """
        return queryset
    
    def build_metadata(
        self,
        start_date: date,
        end_date: date,
        filters: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build metadata for the report
        
        Can be overridden in subclasses to add custom metadata
        
        Args:
            start_date: Report period start
            end_date: Report period end
            filters: Applied filters
            **kwargs: Additional metadata
            
        Returns:
            Metadata dictionary
        """
        return ReportMetadata.create(
            period_start=str(start_date),
            period_end=str(end_date),
            filters_applied=filters or {},
            additional=kwargs
        )

    def parse_filters(
        self,
        request,
        *,
        start_param: str = 'start_date',
        end_param: str = 'end_date',
        default_days: Optional[int] = None,
        max_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Parse common filters (business + optional date range) from request.

        Returns a dictionary containing:
        - business_id: The scoped business identifier
        - start_date / end_date: Optional date range (when provided or defaulted)
        - error_response: DRF Response to return immediately if validation fails
        """

        filters: Dict[str, Any] = {}

        # Resolve business scope first
        business_id, business_error = self.get_business_or_error(request)
        if business_error:
            filters['error_response'] = ReportResponse.error(business_error)
            return filters
        filters['business_id'] = business_id

        # Determine date handling preferences
        effective_default_days = default_days
        if effective_default_days is None:
            effective_default_days = getattr(self, 'default_date_range_days', None)

        effective_max_days = max_days
        if effective_max_days is None:
            effective_max_days = getattr(self, 'max_date_range_days', 365)

        start_str = request.query_params.get(start_param)
        end_str = request.query_params.get(end_param)

        if start_str and end_str:
            start_date, end_date, date_error = self.get_date_range(
                request,
                start_param=start_param,
                end_param=end_param,
                default_days=effective_default_days or 0,
                max_days=effective_max_days or 365
            )
            if date_error:
                filters['error_response'] = ReportResponse.error(date_error)
                return filters
            filters['start_date'] = start_date
            filters['end_date'] = end_date
        elif start_str or end_str:
            missing_param = start_param if not start_str else end_param
            filters['error_response'] = ReportResponse.error(
                ReportError.missing_param(missing_param)
            )
            return filters
        elif effective_default_days:
            start_date, end_date = DateRangeValidator.get_default_range(effective_default_days)
            filters['start_date'] = start_date
            filters['end_date'] = end_date

        return filters

    def get_storefront_filters(
        self,
        request,
        *,
        business_id: Optional[int] = None,
        enforce_access: bool = True,
        include_names: bool = True,
    ) -> Tuple[Dict[str, Any], Optional[Response]]:
        """Parse storefront filters and optionally enforce access permissions."""

        primary = request.query_params.get('storefront_id')

        raw_values: List[str] = []

        multi_params = request.query_params.getlist('storefront_ids')
        if not multi_params:
            single_multi = request.query_params.get('storefront_ids')
            if single_multi:
                multi_params = [single_multi]

        for raw_entry in multi_params:
            segments = [segment.strip() for segment in raw_entry.split(',') if segment.strip()]
            if segments:
                raw_values.extend(segments)

        if primary:
            raw_values.append(primary.strip())

        seen: Set[str] = set()
        unique_ids: List[str] = []
        for value in raw_values:
            if value not in seen:
                seen.add(value)
                unique_ids.append(value)

        filters: Dict[str, Any] = {
            'primary': primary.strip() if primary else None,
            'ids': unique_ids,
        }

        if include_names:
            filters['names'] = []

        if not unique_ids:
            return filters, None

        accessible_storefronts = request.user.get_accessible_storefronts()
        if business_id is not None:
            accessible_storefronts = accessible_storefronts.filter(
                business_link__business_id=business_id,
                business_link__is_active=True,
            )

        permitted_storefronts = list(accessible_storefronts.filter(id__in=unique_ids))
        permitted_ids = {str(storefront.id) for storefront in permitted_storefronts}

        if enforce_access and len(permitted_ids) != len(unique_ids):
            missing_ids = [storefront_id for storefront_id in unique_ids if storefront_id not in permitted_ids]
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                "Storefront not found or inaccessible for this user.",
                {'storefront_ids': missing_ids}
            )
            return filters, ReportResponse.error(error, http_status=http_status.HTTP_404_NOT_FOUND)

        if include_names:
            name_map = {str(storefront.id): storefront.name for storefront in permitted_storefronts}
            filters['names'] = [name_map.get(storefront_id, storefront_id) for storefront_id in unique_ids]

        return filters, None

    @staticmethod
    def resolve_storefront_names(storefront_ids: List[str]) -> List[str]:
        """Map storefront identifiers to display names while preserving order."""

        if not storefront_ids:
            return []

        from inventory.models import StoreFront

        storefront_qs = StoreFront.objects.filter(id__in=storefront_ids)
        name_map = {str(storefront.id): storefront.name for storefront in storefront_qs}

        ordered_names: List[str] = []
        for storefront_id in storefront_ids:
            name = name_map.get(storefront_id)
            if name:
                ordered_names.append(name)

        return ordered_names


class BaseReportBuilder:
    """
    Base class for report builder services
    
    Separates business logic from view layer
    """
    
    def __init__(self, business_id: int, start_date: date, end_date: date):
        """
        Initialize report builder
        
        Args:
            business_id: Business ID to build report for
            start_date: Report period start
            end_date: Report period end
        """
        self.business_id = business_id
        self.start_date = start_date
        self.end_date = end_date
    
    def get_base_queryset(self) -> QuerySet:
        """
        Get base queryset for this report
        
        Override in subclasses
        """
        raise NotImplementedError("Subclasses must implement get_base_queryset()")
    
    def apply_date_filter(self, queryset: QuerySet, date_field: str = 'created_at') -> QuerySet:
        """
        Apply date range filter to queryset
        
        Args:
            queryset: Base queryset
            date_field: Field to filter on
            
        Returns:
            Filtered queryset
        """
        return queryset.filter(
            **{
                f'{date_field}__date__gte': self.start_date,
                f'{date_field}__date__lte': self.end_date,
            }
        )
    
    def filter_by_business(self, queryset: QuerySet) -> QuerySet:
        """
        Filter queryset by business
        
        Args:
            queryset: Base queryset
            
        Returns:
            Filtered queryset
        """
        return queryset.filter(business_id=self.business_id)
    
    def build_report(self) -> Dict[str, Any]:
        """
        Build complete report
        
        Override in subclasses to implement report logic
        
        Returns:
            Dictionary with summary and results
        """
        raise NotImplementedError("Subclasses must implement build_report()")
