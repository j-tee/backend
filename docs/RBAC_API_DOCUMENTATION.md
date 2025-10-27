# RBAC & Account Management API Documentation

## Overview
Complete backend API implementation for Role-Based Access Control (RBAC) and Account Management.

## Implementation Date
October 14, 2025

## New Files Created

### Serializers
1. **`accounts/rbac_serializers.py`** - RBAC model serializers
   - PermissionSerializer
   - RoleSerializer, RoleListSerializer, CreateRoleSerializer
   - AssignPermissionsSerializer
   - UserRoleSerializer, AssignUserRoleSerializer
   - UserWithRolesSerializer

2. **`accounts/account_serializers.py`** - Account management serializers
   - UpdateProfileSerializer
   - ProfilePictureSerializer
   - ChangePasswordSerializer
   - UserPreferencesSerializer
   - NotificationSettingsSerializer
   - UserProfileSerializer
   - Enable2FASerializer, Disable2FASerializer

### Views
3. **`accounts/rbac_views.py`** - RBAC API views
   - PermissionViewSet (read-only)
   - RoleViewSet (full CRUD)
   - UserRoleViewSet (full CRUD)
   - UserWithRolesViewSet (read-only with custom actions)

4. **`accounts/account_views.py`** - Account management API views
   - user_profile (GET/POST)
   - upload_profile_picture (POST)
   - change_password (POST)
   - enable_2fa (POST)
   - disable_2fa (POST)
   - user_preferences (GET/PATCH)
   - notification_settings (GET/PATCH)

### URL Configuration
5. **`accounts/rbac_urls.py`** - RBAC URL routing
6. **`accounts/account_urls.py`** - Account management URL routing
7. **`accounts/urls.py`** - Updated main URL configuration

## API Endpoints

### RBAC Management Endpoints

#### Permissions
```
GET    /accounts/api/permissions/
GET    /accounts/api/permissions/{id}/
```

**Query Parameters:**
- `category` - Filter by category (SALES, INVENTORY, etc.)
- `action` - Filter by action (CREATE, READ, UPDATE, etc.)

**Response Example:**
```json
{
  "count": 21,
  "results": [
    {
      "id": 1,
      "name": "Can Create Sales",
      "codename": "can_create_sales",
      "description": "Allows creating new sales transactions",
      "category": "SALES",
      "action": "CREATE",
      "resource": "sales",
      "is_active": true,
      "created_at": "2025-10-14T10:00:00Z",
      "updated_at": "2025-10-14T10:00:00Z"
    }
  ]
}
```

#### Roles
```
GET    /accounts/api/roles/
POST   /accounts/api/roles/
GET    /accounts/api/roles/{id}/
PATCH  /accounts/api/roles/{id}/
DELETE /accounts/api/roles/{id}/
POST   /accounts/api/roles/{id}/permissions/
```

**Query Parameters:**
- `level` - Filter by level (PLATFORM, BUSINESS, STOREFRONT)
- `is_active` - Filter by active status (true/false)

**Create Role Request:**
```json
{
  "name": "Sales Manager",
  "description": "Manages sales operations",
  "level": "BUSINESS",
  "permission_ids": [1, 2, 3, 4, 5],
  "is_active": true
}
```

**Assign Permissions Request:**
```json
{
  "permission_ids": [1, 2, 3, 4, 5, 6]
}
```

**Response Example:**
```json
{
  "id": 1,
  "name": "Sales Manager",
  "description": "Manages sales operations",
  "level": "BUSINESS",
  "permissions": [
    {
      "id": 1,
      "name": "Can Create Sales",
      "codename": "can_create_sales",
      "category": "SALES"
    }
  ],
  "permission_count": 5,
  "is_system_role": false,
  "is_active": true,
  "created_at": "2025-10-14T10:00:00Z",
  "updated_at": "2025-10-14T10:00:00Z"
}
```

#### User Role Assignments
```
GET    /accounts/api/user-roles/
POST   /accounts/api/user-roles/
DELETE /accounts/api/user-roles/{id}/
```

**Query Parameters:**
- `user_id` - Filter by user
- `role_id` - Filter by role
- `scope` - Filter by scope (PLATFORM, BUSINESS, STOREFRONT)
- `active_only` - Filter active only (true/false)

**Assign Role Request:**
```json
{
  "user_id": 2,
  "role_id": 3,
  "scope": "BUSINESS",
  "business_id": 1,
  "storefront_id": null,
  "expires_at": "2026-01-01T00:00:00Z"
}
```

**Response Example:**
```json
{
  "id": 1,
  "user": 2,
  "user_email": "manager@business.com",
  "role": 3,
  "role_details": {
    "id": 3,
    "name": "Manager",
    "level": "BUSINESS",
    "permission_count": 10
  },
  "scope": "BUSINESS",
  "business": 1,
  "storefront": null,
  "assigned_by": 1,
  "assigned_by_email": "alphalogiquetechnologies@gmail.com",
  "assigned_at": "2025-10-14T10:00:00Z",
  "expires_at": "2026-01-01T00:00:00Z",
  "is_active": true
}
```

#### Users with Roles
```
GET    /accounts/api/users/
GET    /accounts/api/users/{id}/
GET    /accounts/api/users/{id}/roles/
GET    /accounts/api/users/{id}/permissions/
```

**Get User Permissions Response:**
```json
{
  "permissions": [
    {
      "id": 1,
      "codename": "can_create_sales",
      "name": "Can Create Sales",
      "category": "SALES"
    }
  ]
}
```

### Account Management Endpoints

#### User Profile
```
GET    /accounts/api/profile/
POST   /accounts/api/profile/
```

**Update Profile Request:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+233123456789",
  "address": "123 Main St, Accra"
}
```

**Response Example:**
```json
{
  "id": 1,
  "email": "alphalogiquetechnologies@gmail.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+233123456789",
  "address": "123 Main St, Accra",
  "profile_picture": "/media/profile_pictures/1/profile.jpg",
  "platform_role": "SUPER_USER",
  "is_active": true,
  "date_joined": "2025-10-14T10:00:00Z",
  "preferences": {
    "language": "en",
    "timezone": "Africa/Accra",
    "date_format": "DD/MM/YYYY",
    "time_format": "24h"
  },
  "notification_settings": {
    "sales_email": true,
    "sales_push": true
  }
}
```

#### Profile Picture
```
POST   /accounts/api/profile/picture/
```

**Request (multipart/form-data):**
```
profile_picture: [binary file data]
```

**Response:**
```json
{
  "message": "Profile picture uploaded successfully",
  "profile_picture_url": "/media/profile_pictures/1/profile.jpg"
}
```

#### Change Password
```
POST   /accounts/api/change-password/
```

**Request:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!",
  "confirm_password": "NewPassword456!"
}
```

**Response:**
```json
{
  "message": "Password changed successfully"
}
```

#### Two-Factor Authentication
```
POST   /accounts/api/2fa/enable/
POST   /accounts/api/2fa/disable/
```

**Enable 2FA Response:**
```json
{
  "message": "2FA enabled successfully",
  "qr_code": "data:image/png;base64,...",
  "secret": "JBSWY3DPEHPK3PXP",
  "backup_codes": ["12345678", "23456789", ...]
}
```

**Disable 2FA Request:**
```json
{
  "password": "MyPassword123!"
}
```

#### User Preferences
```
GET    /accounts/api/preferences/
PATCH  /accounts/api/preferences/
```

**Update Preferences Request:**
```json
{
  "language": "en",
  "timezone": "Africa/Accra",
  "date_format": "DD/MM/YYYY",
  "time_format": "24h",
  "currency": "GHS"
}
```

#### Notification Settings
```
GET    /accounts/api/notifications/
PATCH  /accounts/api/notifications/
```

**Update Notifications Request:**
```json
{
  "sales_email": true,
  "sales_push": true,
  "sales_sms": false,
  "inventory_email": true,
  "inventory_push": false
}
```

## Permission Requirements

### RBAC Endpoints
**Required Permission:** Super Admin (`has_role_new('SUPER_USER')`)

All RBAC management endpoints (permissions, roles, user-roles, users) require the user to have the SUPER_USER role.

### Account Management Endpoints
**Required Permission:** Authenticated User

All account management endpoints require authentication but are accessible to all authenticated users for their own account.

## Authentication

All endpoints require token authentication:

```
Headers:
Authorization: Token <your_token_here>
```

Get token via login:
```
POST /accounts/api/auth/login/
{
  "email": "user@example.com",
  "password": "password"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "field_name": ["Error message"]
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

## Testing

### Using the Test Script
```bash
cd ~/Documents/Projects/pos/backend
source venv/bin/activate
python3 test_rbac_api.py
```

### Using curl
```bash
# Login
curl -X POST http://localhost:8000/accounts/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"alphalogiquetechnologies@gmail.com","password":"Admin@2024!"}'

# Get permissions
curl -X GET http://localhost:8000/accounts/api/permissions/ \
  -H "Authorization: Token YOUR_TOKEN"

# Get roles
curl -X GET http://localhost:8000/accounts/api/roles/ \
  -H "Authorization: Token YOUR_TOKEN"

# Get user profile
curl -X GET http://localhost:8000/accounts/api/profile/ \
  -H "Authorization: Token YOUR_TOKEN"
```

## Notes

- System roles (is_system_role=True) cannot be deleted
- Profile picture uploads are limited to 5MB
- Supported image formats: JPEG, PNG, GIF, WebP
- Password must meet Django's password validation requirements
- User preferences and notification settings use default values (stored in model in future)
- 2FA implementation is placeholder (integrate with django-otp or similar)

## Next Steps

1. Add user preferences and notification settings to User model or create separate models
2. Implement actual 2FA with TOTP (use django-otp)
3. Add pagination to list endpoints
4. Add filtering and search capabilities
5. Add rate limiting for security endpoints
6. Implement audit logging for sensitive operations
7. Add email notifications for password changes
8. Add session management endpoint for viewing/revoking active sessions

## Platform Owner Credentials
```
Email: alphalogiquetechnologies@gmail.com
Password: Admin@2024!
Role: SUPER_USER (all 21 permissions)
```
