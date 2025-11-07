"""
Query Intelligence Service
Handles natural language queries about business data.
Answers questions like "How many Samsung TVs were sold between January and March?"
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone

from sales.models import Sale, SaleItem, Customer
from inventory.models import Product, Stock, StoreFront
from .openai_service import get_openai_service


class QueryIntelligenceService:
    """Process natural language queries about business data"""
    
    QUERY_TYPES = [
        'sales',  # Sales-related queries
        'product',  # Product performance queries
        'customer',  # Customer-related queries
        'inventory',  # Stock and inventory queries
        'financial',  # Revenue, profit, expenses
        'general',  # General business questions
    ]
    
    def __init__(self, business_id: str, storefront_id: Optional[str] = None):
        """
        Initialize query intelligence service
        
        Args:
            business_id: Business UUID
            storefront_id: Optional storefront UUID for filtering
        """
        self.business_id = business_id
        self.storefront_id = storefront_id
        self.openai = get_openai_service()
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query and return answer with data
        
        Args:
            query: Natural language question
        
        Returns:
            Dict with answer, data, visualizations, and follow-up questions
        """
        # Step 1: Classify query type
        query_type = self._classify_query(query)
        
        # Step 2: Extract parameters (dates, filters, etc.)
        parameters = self._extract_parameters(query, query_type)
        
        # Step 3: Fetch relevant data
        data = self._fetch_data(query_type, parameters)
        
        # Step 4: Generate natural language answer
        answer = self._generate_answer(query, query_type, data)
        
        # Step 5: Format response
        response = self._format_response(answer, data, query_type)
        
        return response
    
    def _classify_query(self, query: str) -> str:
        """Classify the type of query using OpenAI"""
        system_prompt = f"""You are a query classifier for a point-of-sale system.
Classify the following query into one of these types: {', '.join(self.QUERY_TYPES)}

Examples:
- "How many Samsung TVs were sold?" → product
- "What were my total sales last month?" → sales
- "Who are my top customers?" → customer
- "What products are out of stock?" → inventory
- "What's my profit this month?" → financial

Respond with ONLY the query type, nothing else."""
        
        try:
            result = self.openai.generate_text(
                prompt=query,
                system_prompt=system_prompt,
                feature='natural_language_query',
                temperature=0.3,
                max_tokens=10
            )
            
            query_type = result['content'].strip().lower()
            
            # Validate
            if query_type not in self.QUERY_TYPES:
                query_type = 'general'
            
            return query_type
            
        except Exception:
            return 'general'  # Fallback
    
    def _extract_parameters(self, query: str, query_type: str) -> Dict[str, Any]:
        """Extract parameters like date ranges, product names, customer names, etc."""
        system_prompt = """Extract relevant parameters from this query.
Return JSON with these fields (use null if not mentioned):
{
  "date_start": "YYYY-MM-DD or null",
  "date_end": "YYYY-MM-DD or null",
  "product_name": "product name or null",
  "customer_name": "customer name or null",
  "category": "category name or null",
  "limit": "number or null (for 'top N' queries)",
  "time_period": "today/yesterday/this_week/this_month/last_month/this_year or null"
}

Examples:
- "Sales in January" → {"date_start": "2025-01-01", "date_end": "2025-01-31", "time_period": "custom"}
- "Top 10 products" → {"limit": 10}
- "Samsung TV sales" → {"product_name": "Samsung TV"}"""
        
        try:
            result = self.openai.generate_json(
                prompt=f"Query: {query}\nQuery type: {query_type}",
                system_prompt=system_prompt,
                feature='natural_language_query',
                temperature=0.3
            )
            
            parameters = result['data']
            
            # Process time periods
            if parameters.get('time_period'):
                dates = self._convert_time_period(parameters['time_period'])
                if dates:
                    parameters['date_start'] = dates['start']
                    parameters['date_end'] = dates['end']
            
            return parameters
            
        except Exception:
            return {}
    
    def _convert_time_period(self, period: str) -> Optional[Dict[str, str]]:
        """Convert time period strings to actual dates"""
        now = timezone.now()
        today = now.date()
        
        if period == 'today':
            return {'start': str(today), 'end': str(today)}
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return {'start': str(yesterday), 'end': str(yesterday)}
        elif period == 'this_week':
            start = today - timedelta(days=today.weekday())
            return {'start': str(start), 'end': str(today)}
        elif period == 'this_month':
            start = today.replace(day=1)
            return {'start': str(start), 'end': str(today)}
        elif period == 'last_month':
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return {'start': str(last_month_start), 'end': str(last_month_end)}
        elif period == 'this_year':
            start = today.replace(month=1, day=1)
            return {'start': str(start), 'end': str(today)}
        
        return None
    
    def _fetch_data(self, query_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch relevant data from database based on query type"""
        if query_type == 'product':
            return self._fetch_product_data(parameters)
        elif query_type == 'sales':
            return self._fetch_sales_data(parameters)
        elif query_type == 'customer':
            return self._fetch_customer_data(parameters)
        elif query_type == 'inventory':
            return self._fetch_inventory_data(parameters)
        elif query_type == 'financial':
            return self._fetch_financial_data(parameters)
        else:
            return {}
    
    def _fetch_product_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch product sales data"""
        # Base queryset
        query = SaleItem.objects.filter(
            sale__business_id=self.business_id,
            sale__status='COMPLETED'
        )
        
        # Apply storefront filter
        if self.storefront_id:
            query = query.filter(sale__storefront_id=self.storefront_id)
        
        # Apply date filters
        if parameters.get('date_start'):
            query = query.filter(sale__date__gte=parameters['date_start'])
        if parameters.get('date_end'):
            query = query.filter(sale__date__lte=parameters['date_end'])
        
        # Apply product name filter
        if parameters.get('product_name'):
            query = query.filter(
                Q(product__name__icontains=parameters['product_name']) |
                Q(product__sku__icontains=parameters['product_name'])
            )
        
        # Aggregate by product
        products = query.values(
            'product__id',
            'product__name',
            'product__sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price')),
            transaction_count=Count('sale__id', distinct=True)
        ).order_by('-total_quantity')
        
        # Apply limit
        limit = parameters.get('limit', 10)
        products = products[:limit]
        
        return {
            'products': list(products),
            'total_products': len(products)
        }
    
    def _fetch_sales_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch sales summary data"""
        query = Sale.objects.filter(
            business_id=self.business_id,
            status='COMPLETED'
        )
        
        if self.storefront_id:
            query = query.filter(storefront_id=self.storefront_id)
        
        if parameters.get('date_start'):
            query = query.filter(date__gte=parameters['date_start'])
        if parameters.get('date_end'):
            query = query.filter(date__lte=parameters['date_end'])
        
        # Aggregate
        stats = query.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_sale_value=Avg('total_amount')
        )
        
        return {
            'total_sales': stats['total_sales'] or 0,
            'total_revenue': float(stats['total_revenue'] or 0),
            'average_sale_value': float(stats['avg_sale_value'] or 0)
        }
    
    def _fetch_customer_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch customer data"""
        query = Customer.objects.filter(business_id=self.business_id)
        
        # Get customers with their purchase data
        customers = query.annotate(
            total_purchases=Sum('sales__total_amount'),
            purchase_count=Count('sales', filter=Q(sales__status='COMPLETED'))
        ).order_by('-total_purchases')
        
        limit = parameters.get('limit', 10)
        customers = customers[:limit]
        
        customer_list = []
        for customer in customers:
            customer_list.append({
                'id': str(customer.id),
                'name': customer.name,
                'total_purchases': float(customer.total_purchases or 0),
                'purchase_count': customer.purchase_count,
                'customer_type': customer.customer_type,
                'outstanding_balance': float(customer.outstanding_balance)
            })
        
        return {
            'customers': customer_list,
            'total_customers': len(customer_list)
        }
    
    def _fetch_inventory_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch inventory/stock data"""
        # This would query your inventory models
        # Simplified for now
        return {
            'message': 'Inventory data fetching not fully implemented yet'
        }
    
    def _fetch_financial_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch financial data"""
        # Similar to sales data but with profit calculations
        sales_data = self._fetch_sales_data(parameters)
        
        # Add profit calculations here based on your cost data
        return sales_data
    
    def _generate_answer(self, query: str, query_type: str, data: Dict[str, Any]) -> str:
        """Generate natural language answer using OpenAI"""
        system_prompt = """You are a business intelligence assistant for a retail/wholesale business in Ghana.
Analyze the data provided and answer the user's question in a clear, concise, and professional manner.

Guidelines:
- Use GHS for currency (e.g., "GHS 15,000")
- Be specific with numbers
- Provide insights beyond just numbers
- Use bullet points for multiple items
- Keep it brief but informative
- If data is empty or insufficient, say so clearly"""
        
        # Format data for OpenAI
        data_str = json.dumps(data, indent=2, default=str)
        
        prompt = f"""User Question: {query}
Query Type: {query_type}

Data Retrieved:
{data_str}

Please provide a comprehensive answer to the user's question based on this data."""
        
        try:
            result = self.openai.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                feature='natural_language_query',
                temperature=0.7,
                max_tokens=500
            )
            
            return result['content']
            
        except Exception as e:
            return f"I found the data but couldn't generate a proper answer. Error: {str(e)}"
    
    def _format_response(self, answer: str, data: Dict[str, Any], query_type: str) -> Dict[str, Any]:
        """Format the final response with answer, data, and suggestions"""
        return {
            'answer': answer,
            'query_type': query_type,
            'data': data,
            'follow_up_questions': self._generate_follow_ups(query_type),
            'visualization_hints': self._get_visualization_hints(query_type, data)
        }
    
    def _generate_follow_ups(self, query_type: str) -> List[str]:
        """Generate relevant follow-up questions"""
        follow_ups = {
            'product': [
                "Which products have the highest profit margins?",
                "Show me slow-moving products",
                "What products need restocking?"
            ],
            'sales': [
                "How do sales compare to last month?",
                "What day of the week has highest sales?",
                "Show me sales by category"
            ],
            'customer': [
                "Which customers haven't purchased in 90 days?",
                "Show me customers with outstanding balances",
                "Who are my wholesale vs retail customers?"
            ],
            'inventory': [
                "What products are out of stock?",
                "Show me overstocked items",
                "What's my total inventory value?"
            ],
            'financial': [
                "What's my profit margin?",
                "How much profit did I make?",
                "Show me revenue by category"
            ]
        }
        
        return follow_ups.get(query_type, [
            "What were my total sales this month?",
            "Show me top products",
            "Who are my top customers?"
        ])
    
    def _get_visualization_hints(self, query_type: str, data: Dict[str, Any]) -> Dict[str, str]:
        """Suggest appropriate visualizations for the data"""
        if query_type == 'product' and 'products' in data:
            return {
                'type': 'bar_chart',
                'x_axis': 'product_name',
                'y_axis': 'total_quantity',
                'title': 'Product Sales Comparison'
            }
        elif query_type == 'sales':
            return {
                'type': 'line_chart',
                'title': 'Sales Trend'
            }
        elif query_type == 'customer' and 'customers' in data:
            return {
                'type': 'table',
                'title': 'Top Customers'
            }
        
        return {
            'type': 'none',
            'title': ''
        }
