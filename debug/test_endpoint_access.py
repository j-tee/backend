"""
Test endpoint access directly
"""
import requests

# Test with session (like the browser)
session = requests.Session()

# Login first
login_url = 'http://localhost:8000/accounts/api/login/'
login_data = {
    'email': 'mikedlt009@gmail.com',
    'password': 'your_password_here'  # Replace with actual password
}

print("Testing Report Endpoint Access")
print("="*60)

# Try to login
print("\n1. Attempting login...")
try:
    response = session.post(login_url, json=login_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Login successful")
        data = response.json()
        token = data.get('token')
        if token:
            print(f"   Token: {token[:20]}...")
    else:
        print(f"   ❌ Login failed: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test report endpoint with session
print("\n2. Testing /reports/api/sales/summary/ with session...")
report_url = 'http://localhost:8000/reports/api/sales/summary/'
try:
    response = session.get(report_url)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Success!")
        print(f"   Data keys: {list(response.json().keys())}")
    elif response.status_code == 403:
        print(f"   ❌ 403 Forbidden")
        print(f"   Response: {response.text[:200]}")
    else:
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test with token authentication
if 'token' in locals():
    print("\n3. Testing with Token authentication...")
    headers = {'Authorization': f'Token {token}'}
    try:
        response = requests.get(report_url, headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Success!")
            data = response.json()
            print(f"   Data keys: {list(data.keys())}")
        elif response.status_code == 403:
            print(f"   ❌ 403 Forbidden")
            print(f"   Response: {response.text[:200]}")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("Test complete")
