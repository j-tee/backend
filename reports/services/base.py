"""
Base export service for all data exporters
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any, List, Optional
from django.db.models import QuerySet
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

User = get_user_model()


class BaseDataExporter(ABC):
    """Base class for all data exporters"""
    
    def __init__(self, user):
        self.user = user
        self.business_ids = self._get_business_ids()
    
    def _get_business_ids(self) -> Optional[List]:
        """Get businesses accessible to user"""
        from accounts.models import BusinessMembership
        
        if self.user.is_superuser or getattr(self.user, 'is_platform_super_admin', False):
            return None  # Access all
        
        memberships = BusinessMembership.objects.filter(
            user=self.user,
            is_active=True
        ).values_list('business_id', flat=True)
        
        business_ids = list(memberships)
        
        if not business_ids:
            # User has no business access
            return []
        
        return business_ids
    
    @abstractmethod
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered queryset - implement in subclass"""
        pass
    
    @abstractmethod
    def serialize_data(self, queryset: QuerySet, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert queryset to export format - implement in subclass"""
        pass
    
    def export(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Main export method"""
        queryset = self.build_queryset(filters)
        data = self.serialize_data(queryset, filters)
        return data
