#!/bin/bash

# Manual Testing Script for Catalog Filtering
# Run this after server is running: python manage.py runserver

# Configuration
BASE_URL="http://localhost:8000"
TOKEN="your-auth-token-here"  # Replace with actual token
STOREFRONT_ID="your-storefront-id"  # Replace with actual storefront ID
CATEGORY_ID="your-category-id"  # Replace with actual category ID

echo "======================================"
echo "Catalog Filtering Manual Tests"
echo "======================================"
echo ""

# Function to make authenticated request
function api_call() {
    local endpoint=$1
    local description=$2
    
    echo "----------------------------------------"
    echo "TEST: $description"
    echo "URL: $BASE_URL$endpoint"
    echo "----------------------------------------"
    
    curl -s \
        -H "Authorization: Token $TOKEN" \
        -H "Content-Type: application/json" \
        "$BASE_URL$endpoint" | python3 -m json.tool | head -50
    
    echo ""
    echo ""
}

# Test 1: Basic catalog (no filters)
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/" \
    "Basic Catalog (No Filters)"

# Test 2: Search by name
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?search=sugar" \
    "Search for 'sugar'"

# Test 3: Filter by category
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?category=$CATEGORY_ID" \
    "Filter by Category"

# Test 4: Price range
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?min_price=10&max_price=50" \
    "Price Range (10-50)"

# Test 5: Combined filters
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?search=rice&max_price=25" \
    "Combined: Search + Price"

# Test 6: Pagination
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?page=1&page_size=10" \
    "Pagination (Page 1, Size 10)"

# Test 7: Include out-of-stock
api_call "/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?in_stock_only=false" \
    "Include Out-of-Stock Products"

# Test 8: Multi-storefront catalog
api_call "/inventory/api/storefronts/multi-storefront-catalog/?search=sugar" \
    "Multi-Storefront Search"

# Test 9: Multi-storefront with pagination
api_call "/inventory/api/storefronts/multi-storefront-catalog/?page=1&page_size=5" \
    "Multi-Storefront Pagination"

# Test 10: Check pagination metadata
echo "----------------------------------------"
echo "TEST: Verify Pagination Metadata"
echo "----------------------------------------"
curl -s \
    -H "Authorization: Token $TOKEN" \
    "$BASE_URL/inventory/api/storefronts/$STOREFRONT_ID/sale-catalog/?page=1&page_size=5" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Count:', data.get('count'))
print('Page Size:', data.get('page_size'))
print('Total Pages:', data.get('total_pages'))
print('Current Page:', data.get('current_page'))
print('Next:', data.get('next'))
print('Previous:', data.get('previous'))
print('Products:', len(data.get('products', [])))
"

echo ""
echo "======================================"
echo "Tests Complete!"
echo "======================================"
