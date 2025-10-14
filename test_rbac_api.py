"""
Test script for RBAC and Account Management APIs
"""

import requests
import json

BASE_URL = 'http://localhost:8000/accounts/api'

# Test credentials
PLATFORM_OWNER = {
    'email': 'alphalogiquetechnologies@gmail.com',
    'password': 'Admin@2024!'
}

def login(email, password):
    """Login and get auth token"""
    response = requests.post(
        f'{BASE_URL}/auth/login/',
        json={'email': email, 'password': password}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get('token')
    else:
        print(f"Login failed: {response.status_code}")
        print(response.text)
        return None

def test_permissions(token):
    """Test fetching permissions"""
    print("\n" + "="*60)
    print("Testing: GET /api/permissions/")
    print("="*60)
    
    response = requests.get(
        f'{BASE_URL}/permissions/',
        headers={'Authorization': f'Token {token}'}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total Permissions: {len(data.get('results', data))}")
        if isinstance(data, dict) and 'results' in data:
            print(f"First 3 permissions:")
            for perm in data['results'][:3]:
                print(f"  - {perm['codename']} ({perm['category']})")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_roles(token):
    """Test fetching roles"""
    print("\n" + "="*60)
    print("Testing: GET /api/roles/")
    print("="*60)
    
    response = requests.get(
        f'{BASE_URL}/roles/',
        headers={'Authorization': f'Token {token}'}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', data)
        print(f"Total Roles: {len(results)}")
        print(f"Roles:")
        for role in results:
            print(f"  - {role['name']} ({role['level']}): {role['permission_count']} permissions")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_create_role(token):
    """Test creating a new role"""
    print("\n" + "="*60)
    print("Testing: POST /api/roles/ (Create Role)")
    print("="*60)
    
    new_role = {
        'name': 'Test Manager',
        'description': 'Test role for managers',
        'level': 'BUSINESS',
        'permission_ids': [1, 2, 3],  # First 3 permissions
        'is_active': True
    }
    
    response = requests.post(
        f'{BASE_URL}/roles/',
        headers={
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        },
        json=new_role
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"Created Role: {data['name']} (ID: {data['id']})")
        return data['id']
    else:
        print(f"Error: {response.text}")
        return None

def test_user_profile(token):
    """Test fetching user profile"""
    print("\n" + "="*60)
    print("Testing: GET /api/profile/")
    print("="*60)
    
    response = requests.get(
        f'{BASE_URL}/profile/',
        headers={'Authorization': f'Token {token}'}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"User: {data['email']}")
        print(f"Name: {data['first_name']} {data['last_name']}")
        print(f"Platform Role: {data['platform_role']}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_user_preferences(token):
    """Test fetching and updating user preferences"""
    print("\n" + "="*60)
    print("Testing: GET /api/preferences/")
    print("="*60)
    
    response = requests.get(
        f'{BASE_URL}/preferences/',
        headers={'Authorization': f'Token {token}'}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Language: {data.get('language')}")
        print(f"Timezone: {data.get('timezone')}")
        print(f"Date Format: {data.get('date_format')}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_user_roles(token):
    """Test fetching user role assignments"""
    print("\n" + "="*60)
    print("Testing: GET /api/user-roles/")
    print("="*60)
    
    response = requests.get(
        f'{BASE_URL}/user-roles/',
        headers={'Authorization': f'Token {token}'}
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', data)
        print(f"Total User Role Assignments: {len(results)}")
        for ur in results:
            print(f"  - {ur.get('user_email', 'N/A')} → {ur.get('role_details', {}).get('name', 'N/A')} ({ur['scope']})")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def main():
    print("="*60)
    print("RBAC & Account Management API Tests")
    print("="*60)
    
    # Login
    print("\nLogging in as platform owner...")
    token = login(PLATFORM_OWNER['email'], PLATFORM_OWNER['password'])
    
    if not token:
        print("❌ Login failed! Cannot proceed with tests.")
        return
    
    print(f"✅ Login successful! Token: {token[:20]}...")
    
    # Run tests
    results = {
        'Permissions': test_permissions(token),
        'Roles': test_roles(token),
        'Create Role': test_create_role(token) is not None,
        'User Profile': test_user_profile(token),
        'User Preferences': test_user_preferences(token),
        'User Roles': test_user_roles(token),
    }
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == '__main__':
    main()
