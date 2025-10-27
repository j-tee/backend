#!/usr/bin/env python3
"""
Integration Testing Script for RBAC and Account Management
Tests all API endpoints, 2FA flow, preferences, and pagination
"""

import requests
import json
import sys
import time
from io import BytesIO
from PIL import Image

# Configuration
BASE_URL = 'http://localhost:8000'
LOGIN_EMAIL = 'alphalogiquetechnologies@gmail.com'
LOGIN_PASSWORD = 'Admin@2024!'

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class IntegrationTester:
    def __init__(self):
        self.token = None
        self.headers = {}
        self.test_results = []
        self.two_fa_secret = None
        self.backup_codes = []
        
    def print_header(self, title):
        """Print a formatted section header"""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}{title.center(80)}{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")
    
    def print_test(self, name, passed, details=""):
        """Print test result"""
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        print(f"{status} - {name}")
        if details:
            print(f"    {details}")
        self.test_results.append((name, passed))
    
    def login(self):
        """Test 1: Login and get authentication token"""
        self.print_header("TEST 1: Authentication - Login")
        
        try:
            response = requests.post(
                f'{BASE_URL}/accounts/api/auth/login/',
                json={'email': LOGIN_EMAIL, 'password': LOGIN_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                self.headers = {'Authorization': f'Token {self.token}'}
                self.print_test("Login successful", True, f"Token: {self.token[:20]}...")
                return True
            else:
                self.print_test("Login failed", False, f"Status: {response.status_code}, Error: {response.text}")
                return False
        except Exception as e:
            self.print_test("Login error", False, str(e))
            return False
    
    def test_get_profile(self):
        """Test 2: Get user profile"""
        self.print_header("TEST 2: Profile Management - Get Profile")
        
        try:
            response = requests.get(f'{BASE_URL}/accounts/api/profile/', headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                self.print_test("Get profile", True)
                
                # Verify all expected fields exist
                expected_fields = ['id', 'email', 'name', 'preferences', 'notification_settings', 'two_factor_enabled']
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    self.print_test("Profile fields complete", False, f"Missing: {missing_fields}")
                else:
                    self.print_test("Profile fields complete", True)
                
                # Print profile details
                print(f"\n{YELLOW}Profile Details:{RESET}")
                print(f"  Email: {data.get('email')}")
                print(f"  Name: {data.get('name')}")
                print(f"  2FA Enabled: {data.get('two_factor_enabled')}")
                print(f"  Preferences: {json.dumps(data.get('preferences', {}), indent=2)}")
                
                return True
            else:
                self.print_test("Get profile", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.print_test("Get profile error", False, str(e))
            return False
    
    def test_update_profile(self):
        """Test 3: Update user profile"""
        self.print_header("TEST 3: Profile Management - Update Profile")
        
        try:
            # Update name
            response = requests.post(
                f'{BASE_URL}/accounts/api/profile/',
                headers=self.headers,
                json={'name': 'Platform Owner (Updated)'}
            )
            
            if response.status_code == 200:
                self.print_test("Update profile name", True)
                
                # Verify update
                verify = requests.get(f'{BASE_URL}/accounts/api/profile/', headers=self.headers)
                if verify.status_code == 200:
                    updated_name = verify.json().get('name')
                    if 'Updated' in updated_name:
                        self.print_test("Verify profile update", True, f"New name: {updated_name}")
                    else:
                        self.print_test("Verify profile update", False, "Name not updated")
                
                # Restore original name
                requests.post(
                    f'{BASE_URL}/accounts/api/profile/',
                    headers=self.headers,
                    json={'name': 'Platform Owner'}
                )
                return True
            else:
                self.print_test("Update profile", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.print_test("Update profile error", False, str(e))
            return False
    
    def test_preferences(self):
        """Test 4: Get and update preferences"""
        self.print_header("TEST 4: Preferences - Get and Update")
        
        try:
            # Get current preferences
            response = requests.get(f'{BASE_URL}/accounts/api/preferences/', headers=self.headers)
            
            if response.status_code == 200:
                self.print_test("Get preferences", True)
                current_prefs = response.json()
                print(f"\n{YELLOW}Current Preferences:{RESET}")
                print(f"  Language: {current_prefs.get('language')}")
                print(f"  Timezone: {current_prefs.get('timezone')}")
                print(f"  Date Format: {current_prefs.get('date_format')}")
                print(f"  Time Format: {current_prefs.get('time_format')}")
            else:
                self.print_test("Get preferences", False, f"Status: {response.status_code}")
                return False
            
            # Update preferences
            new_prefs = {
                'language': 'fr',
                'timezone': 'Europe/Paris',
                'date_format': 'MM/DD/YYYY',
                'time_format': '12h',
                'currency': 'EUR'
            }
            
            response = requests.patch(
                f'{BASE_URL}/accounts/api/preferences/',
                headers=self.headers,
                json=new_prefs
            )
            
            if response.status_code == 200:
                self.print_test("Update preferences", True)
                
                # Verify update
                verify = requests.get(f'{BASE_URL}/accounts/api/preferences/', headers=self.headers)
                if verify.status_code == 200:
                    updated = verify.json()
                    
                    all_match = all(updated.get(key) == value for key, value in new_prefs.items())
                    
                    if all_match:
                        self.print_test("Verify preferences persistence", True)
                        print(f"\n{YELLOW}Updated Preferences:{RESET}")
                        print(f"  Language: {updated.get('language')}")
                        print(f"  Timezone: {updated.get('timezone')}")
                        print(f"  Date Format: {updated.get('date_format')}")
                        print(f"  Time Format: {updated.get('time_format')}")
                        print(f"  Currency: {updated.get('currency')}")
                    else:
                        self.print_test("Verify preferences persistence", False, "Some preferences didn't update")
                
                # Restore defaults
                requests.patch(
                    f'{BASE_URL}/accounts/api/preferences/',
                    headers=self.headers,
                    json={
                        'language': 'en',
                        'timezone': 'Africa/Accra',
                        'date_format': 'DD/MM/YYYY',
                        'time_format': '24h',
                        'currency': 'GHS'
                    }
                )
                return True
            else:
                self.print_test("Update preferences", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Preferences error", False, str(e))
            return False
    
    def test_notification_settings(self):
        """Test 5: Get and update notification settings"""
        self.print_header("TEST 5: Notification Settings - Get and Update")
        
        try:
            # Get current settings
            response = requests.get(f'{BASE_URL}/accounts/api/notifications/', headers=self.headers)
            
            if response.status_code == 200:
                self.print_test("Get notification settings", True)
                current = response.json()
                print(f"\n{YELLOW}Current Notification Settings (sample):{RESET}")
                print(f"  Sales Email: {current.get('sales_email')}")
                print(f"  Sales Push: {current.get('sales_push')}")
                print(f"  Inventory Email: {current.get('inventory_email')}")
            else:
                self.print_test("Get notification settings", False, f"Status: {response.status_code}")
                return False
            
            # Update some settings
            new_settings = {
                'sales_email': False,
                'sales_push': False,
                'inventory_sms': True,
                'payments_email': False
            }
            
            response = requests.patch(
                f'{BASE_URL}/accounts/api/notifications/',
                headers=self.headers,
                json=new_settings
            )
            
            if response.status_code == 200:
                self.print_test("Update notification settings", True)
                
                # Verify update
                verify = requests.get(f'{BASE_URL}/accounts/api/notifications/', headers=self.headers)
                if verify.status_code == 200:
                    updated = verify.json()
                    
                    all_match = all(updated.get(key) == value for key, value in new_settings.items())
                    
                    if all_match:
                        self.print_test("Verify notification persistence", True)
                        print(f"\n{YELLOW}Updated Settings:{RESET}")
                        for key, value in new_settings.items():
                            print(f"  {key}: {value}")
                    else:
                        self.print_test("Verify notification persistence", False, "Some settings didn't update")
                        
                # Restore defaults
                requests.patch(
                    f'{BASE_URL}/accounts/api/notifications/',
                    headers=self.headers,
                    json={
                        'sales_email': True,
                        'sales_push': True,
                        'inventory_sms': False,
                        'payments_email': True
                    }
                )
                return True
            else:
                self.print_test("Update notification settings", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Notification settings error", False, str(e))
            return False
    
    def test_enable_2fa(self):
        """Test 6: Enable 2FA and get QR code"""
        self.print_header("TEST 6: Two-Factor Authentication - Enable")
        
        try:
            response = requests.post(f'{BASE_URL}/accounts/api/2fa/enable/', headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                self.two_fa_secret = data.get('secret')
                self.backup_codes = data.get('backup_codes', [])
                
                self.print_test("Enable 2FA", True)
                
                # Verify response structure
                if 'qr_code' in data and 'secret' in data and 'backup_codes' in data:
                    self.print_test("2FA response complete", True)
                    print(f"\n{YELLOW}2FA Setup:{RESET}")
                    print(f"  Secret: {self.two_fa_secret}")
                    print(f"  QR Code: {data['qr_code'][:50]}... (base64 PNG)")
                    print(f"  Backup Codes: {len(self.backup_codes)} codes generated")
                    print(f"  Sample codes: {self.backup_codes[:2]}")
                else:
                    self.print_test("2FA response complete", False, "Missing fields in response")
                
                return True
            elif response.status_code == 400 and '2FA is already enabled' in response.text:
                self.print_test("Enable 2FA", True, "2FA already enabled (expected if not disabled)")
                # Try to disable first
                self.test_disable_2fa()
                # Try again
                return self.test_enable_2fa()
            else:
                self.print_test("Enable 2FA", False, f"Status: {response.status_code}, Error: {response.text}")
                return False
                
        except Exception as e:
            self.print_test("Enable 2FA error", False, str(e))
            return False
    
    def test_verify_2fa(self):
        """Test 7: Verify 2FA code"""
        self.print_header("TEST 7: Two-Factor Authentication - Verify")
        
        if not self.two_fa_secret:
            self.print_test("Verify 2FA", False, "No 2FA secret available (enable first)")
            return False
        
        try:
            import pyotp
            
            # Generate current TOTP code
            totp = pyotp.TOTP(self.two_fa_secret)
            code = totp.now()
            
            print(f"{YELLOW}Generated TOTP code: {code}{RESET}")
            
            response = requests.post(
                f'{BASE_URL}/accounts/api/2fa/verify/',
                headers=self.headers,
                json={'code': code}
            )
            
            if response.status_code == 200:
                self.print_test("Verify 2FA code", True)
                
                # Verify 2FA is now enabled
                profile = requests.get(f'{BASE_URL}/accounts/api/profile/', headers=self.headers)
                if profile.status_code == 200:
                    is_enabled = profile.json().get('two_factor_enabled')
                    if is_enabled:
                        self.print_test("2FA activation confirmed", True)
                    else:
                        self.print_test("2FA activation confirmed", False, "Profile shows 2FA not enabled")
                
                return True
            else:
                self.print_test("Verify 2FA code", False, f"Status: {response.status_code}, Error: {response.text}")
                return False
                
        except ImportError:
            self.print_test("Verify 2FA", False, "pyotp not installed (pip install pyotp)")
            return False
        except Exception as e:
            self.print_test("Verify 2FA error", False, str(e))
            return False
    
    def test_disable_2fa(self):
        """Test 8: Disable 2FA"""
        self.print_header("TEST 8: Two-Factor Authentication - Disable")
        
        try:
            response = requests.post(
                f'{BASE_URL}/accounts/api/2fa/disable/',
                headers=self.headers,
                json={'password': LOGIN_PASSWORD}
            )
            
            if response.status_code == 200:
                self.print_test("Disable 2FA", True)
                
                # Verify 2FA is disabled
                profile = requests.get(f'{BASE_URL}/accounts/api/profile/', headers=self.headers)
                if profile.status_code == 200:
                    is_enabled = profile.json().get('two_factor_enabled')
                    if not is_enabled:
                        self.print_test("2FA deactivation confirmed", True)
                    else:
                        self.print_test("2FA deactivation confirmed", False, "Profile shows 2FA still enabled")
                
                return True
            elif response.status_code == 400 and '2FA is not enabled' in response.text:
                self.print_test("Disable 2FA", True, "2FA already disabled")
                return True
            else:
                self.print_test("Disable 2FA", False, f"Status: {response.status_code}, Error: {response.text}")
                return False
                
        except Exception as e:
            self.print_test("Disable 2FA error", False, str(e))
            return False
    
    def test_profile_picture_upload(self):
        """Test 9: Upload profile picture"""
        self.print_header("TEST 9: Profile Picture - Upload")
        
        try:
            # Create a test image
            img = Image.new('RGB', (200, 200), color='blue')
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            files = {'profile_picture': ('test_profile.png', img_bytes, 'image/png')}
            
            response = requests.post(
                f'{BASE_URL}/accounts/api/profile/picture/',
                headers=self.headers,
                files=files
            )
            
            if response.status_code == 200:
                self.print_test("Upload profile picture", True)
                data = response.json()
                
                # Verify picture URL is returned
                profile_pic_url = data.get('user', {}).get('profile_picture_url')
                if profile_pic_url:
                    self.print_test("Profile picture URL returned", True, f"URL: {profile_pic_url}")
                else:
                    self.print_test("Profile picture URL returned", False)
                
                return True
            else:
                self.print_test("Upload profile picture", False, f"Status: {response.status_code}, Error: {response.text}")
                return False
                
        except Exception as e:
            self.print_test("Profile picture upload error", False, str(e))
            return False
    
    def test_pagination_permissions(self):
        """Test 10: Pagination on permissions list"""
        self.print_header("TEST 10: Pagination - Permissions List")
        
        try:
            # Test default pagination
            response = requests.get(
                f'{BASE_URL}/accounts/api/rbac/permissions/',
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check pagination fields
                if 'count' in data and 'results' in data:
                    self.print_test("Pagination structure", True)
                    print(f"\n{YELLOW}Pagination Info:{RESET}")
                    print(f"  Total count: {data['count']}")
                    print(f"  Next page: {data.get('next')}")
                    print(f"  Previous page: {data.get('previous')}")
                    print(f"  Results in page: {len(data['results'])}")
                else:
                    self.print_test("Pagination structure", False, "Missing count or results")
                    return False
            else:
                self.print_test("Get permissions with pagination", False, f"Status: {response.status_code}")
                return False
            
            # Test custom page size
            response = requests.get(
                f'{BASE_URL}/accounts/api/rbac/permissions/?page_size=5',
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if len(data['results']) <= 5:
                    self.print_test("Custom page size works", True, f"Got {len(data['results'])} results")
                else:
                    self.print_test("Custom page size works", False, f"Expected ≤5, got {len(data['results'])}")
            
            # Test page navigation
            if data.get('next'):
                response = requests.get(data['next'], headers=self.headers)
                if response.status_code == 200:
                    self.print_test("Page navigation works", True)
                else:
                    self.print_test("Page navigation works", False)
            
            return True
                
        except Exception as e:
            self.print_test("Pagination error", False, str(e))
            return False
    
    def test_pagination_roles(self):
        """Test 11: Pagination on roles list"""
        self.print_header("TEST 11: Pagination - Roles List")
        
        try:
            response = requests.get(
                f'{BASE_URL}/accounts/api/rbac/roles/?page=1&page_size=3',
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                self.print_test("Get roles with pagination", True)
                print(f"\n{YELLOW}Roles Pagination:{RESET}")
                print(f"  Total roles: {data['count']}")
                print(f"  Page size: {len(data['results'])}")
                
                if data['results']:
                    print(f"\n{YELLOW}Sample Roles:{RESET}")
                    for role in data['results'][:2]:
                        print(f"  - {role['name']} ({role['level']})")
                
                return True
            else:
                self.print_test("Get roles with pagination", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("Roles pagination error", False, str(e))
            return False
    
    def test_pagination_user_roles(self):
        """Test 12: Pagination on user roles list"""
        self.print_header("TEST 12: Pagination - User Roles List")
        
        try:
            response = requests.get(
                f'{BASE_URL}/accounts/api/rbac/user-roles/?page=1',
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                self.print_test("Get user roles with pagination", True)
                print(f"\n{YELLOW}User Roles Pagination:{RESET}")
                print(f"  Total assignments: {data['count']}")
                print(f"  Page size: {len(data['results'])}")
                
                return True
            else:
                self.print_test("Get user roles with pagination", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test("User roles pagination error", False, str(e))
            return False
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")
        
        total = len(self.test_results)
        passed = sum(1 for _, result in self.test_results if result)
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        print(f"Success Rate: {(passed/total*100):.1f}%\n")
        
        if failed > 0:
            print(f"{RED}Failed Tests:{RESET}")
            for name, result in self.test_results:
                if not result:
                    print(f"  ❌ {name}")
        else:
            print(f"{GREEN}🎉 All tests passed!{RESET}")
        
        print()
    
    def run_all_tests(self):
        """Run all integration tests"""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}RBAC AND ACCOUNT MANAGEMENT - INTEGRATION TESTING{RESET}")
        print(f"{BLUE}{'='*80}{RESET}")
        
        # Authentication
        if not self.login():
            print(f"\n{RED}Cannot proceed without authentication. Exiting.{RESET}\n")
            return
        
        # Profile Management Tests
        self.test_get_profile()
        self.test_update_profile()
        
        # Preferences Tests
        self.test_preferences()
        self.test_notification_settings()
        
        # 2FA Tests
        self.test_enable_2fa()
        self.test_verify_2fa()
        self.test_disable_2fa()
        
        # Profile Picture Test
        self.test_profile_picture_upload()
        
        # Pagination Tests
        self.test_pagination_permissions()
        self.test_pagination_roles()
        self.test_pagination_user_roles()
        
        # Summary
        self.print_summary()


if __name__ == '__main__':
    tester = IntegrationTester()
    tester.run_all_tests()
