"""
AI Features URL Configuration
"""

from django.urls import path
from . import views

app_name = 'ai_features'

urlpatterns = [
    # Credit Management
    path('api/credits/balance/', views.get_credit_balance, name='credit-balance'),
    path('api/credits/purchase/', views.purchase_credits, name='purchase-credits'),
    path('api/credits/verify/', views.verify_payment, name='verify-payment'),
    path('api/usage/stats/', views.get_usage_stats, name='usage-stats'),
    path('api/transactions/', views.get_transactions, name='transactions'),
    path('api/check-availability/', views.check_feature_availability, name='check-availability'),
    
    # Webhooks
    path('api/webhooks/paystack/', views.paystack_webhook, name='paystack-webhook'),
    
    # Natural Language Query
    path('api/query/', views.natural_language_query, name='natural-language-query'),
    
    # Product Features
    path('api/products/generate-description/', views.generate_product_description, name='generate-description'),
    
    # Report Narrative
    path('api/reports/narrative/', views.generate_report_narrative, name='generate-report-narrative'),
    
    # Inventory Forecasting
    path('api/inventory/forecast/', views.generate_inventory_forecast, name='inventory-forecast'),
    
    # Smart Collections
    path('api/collections/message/', views.generate_collection_message, name='collection-message'),
    path('api/credit/assess/', views.assess_credit_risk, name='assess-credit'),
]
