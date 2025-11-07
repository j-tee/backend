#!/bin/bash
# Quick AI Credit Payment Recovery Script
# This script helps recover from the 500 error issue

echo "=================================="
echo "AI Credit Payment Recovery Tool"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Run this script from the backend directory"
    exit 1
fi

# Check for virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "Activating virtual environment..."
    source ../venv/bin/activate
elif [ -d "env" ]; then
    echo "Activating virtual environment..."
    source env/bin/activate
else
    echo "⚠️  Warning: No virtual environment found, using system Python"
fi

# Show menu
echo ""
echo "What would you like to do?"
echo "1) List all pending payments"
echo "2) Process a specific payment"
echo "3) Debug a specific payment"
echo "4) Check recent error logs"
echo "5) Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "Listing pending payments..."
        python3 manual_credit_processor.py --list
        ;;
    2)
        echo ""
        read -p "Enter payment reference (e.g., AI-CREDIT-xxx): " ref
        echo ""
        python3 manual_credit_processor.py "$ref"
        ;;
    3)
        echo ""
        read -p "Enter payment reference (e.g., AI-CREDIT-xxx): " ref
        echo ""
        python3 debug_ai_credit_payment.py "$ref"
        ;;
    4)
        echo ""
        echo "Recent AI credit verification errors:"
        echo "======================================"
        tail -100 logs/django.log | grep -B 2 -A 5 "credits/verify.*500"
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=================================="
echo "Done!"
echo "=================================="
