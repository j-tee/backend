from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Sum, Count
from .models import (
    Category, Warehouse, StoreFront, Batch, Product, 
    BatchProduct, Inventory, Transfer, StockAlert,
    BusinessWarehouse, BusinessStoreFront, StoreFrontEmployee, WarehouseEmployee
)
from .serializers import (
    CategorySerializer, WarehouseSerializer, StoreFrontSerializer, 
    BatchSerializer, ProductSerializer, BatchProductSerializer,
    InventorySerializer, TransferSerializer, StockAlertSerializer,
    InventorySummarySerializer, BatchArrivalReportSerializer,
    BusinessWarehouseSerializer, BusinessStoreFrontSerializer,
    StoreFrontEmployeeSerializer, WarehouseEmployeeSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class WarehouseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing warehouses"""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]


class StoreFrontViewSet(viewsets.ModelViewSet):
    """ViewSet for managing store fronts"""
    queryset = StoreFront.objects.all()
    serializer_class = StoreFrontSerializer
    permission_classes = [permissions.IsAuthenticated]


class BatchViewSet(viewsets.ModelViewSet):
    """ViewSet for managing batches"""
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing products"""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class BatchProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing batch products"""
    queryset = BatchProduct.objects.all()
    serializer_class = BatchProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing inventory"""
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAuthenticated]


class TransferViewSet(viewsets.ModelViewSet):
    """ViewSet for managing transfers"""
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    permission_classes = [permissions.IsAuthenticated]


class StockAlertViewSet(viewsets.ModelViewSet):
    """ViewSet for managing stock alerts"""
    queryset = StockAlert.objects.all()
    serializer_class = StockAlertSerializer
    permission_classes = [permissions.IsAuthenticated]


class BusinessWarehouseViewSet(viewsets.ModelViewSet):
    """Manage warehouse-business associations"""
    queryset = BusinessWarehouse.objects.select_related('business', 'warehouse').all()
    serializer_class = BusinessWarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]


class BusinessStoreFrontViewSet(viewsets.ModelViewSet):
    """Manage storefront-business associations"""
    queryset = BusinessStoreFront.objects.select_related('business', 'storefront', 'storefront__user').all()
    serializer_class = BusinessStoreFrontSerializer
    permission_classes = [permissions.IsAuthenticated]


class StoreFrontEmployeeViewSet(viewsets.ModelViewSet):
    """Manage storefront employee assignments"""
    queryset = StoreFrontEmployee.objects.select_related('business', 'storefront', 'user').all()
    serializer_class = StoreFrontEmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]


class WarehouseEmployeeViewSet(viewsets.ModelViewSet):
    """Manage warehouse employee assignments"""
    queryset = WarehouseEmployee.objects.select_related('business', 'warehouse', 'user').all()
    serializer_class = WarehouseEmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]


class InventorySummaryView(APIView):
    """View for inventory summary reports"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Basic implementation - can be expanded
        data = []
        return Response(data)


class BatchArrivalReportView(APIView):
    """View for batch arrival reports"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Basic implementation - can be expanded
        data = []
        return Response(data)
