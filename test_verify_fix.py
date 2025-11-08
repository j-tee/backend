#!/usr/bin/env python
"""Test the verify endpoint directly"""
import requests

# Get a token first - you'll need to replace this with a real token
# or get it from localStorage in the browser
TOKEN = ""  # Add token here

def main():
    if not TOKEN:
        print("❌ Please add a token to test")
        print("Get it from browser localStorage or login via API")
        exit(1)

    reference = "AI-CREDIT-1762542056443-08ed01c0"

    response = requests.get(
        f"http://localhost:8000/ai/api/credits/verify/?reference={reference}",
        headers={"Authorization": f"Token {TOKEN}"}
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    main()
