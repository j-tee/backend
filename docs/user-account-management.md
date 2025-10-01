# User Account Management Guide

This guide explains how the backend handles user registration, invitations, profile management, and password flows so that frontend clients can integrate the experience end to end.

---

## 1. Account Types & Roles

| Concept | Description |
| --- | --- |
| **Account Type** | Either `OWNER` (business owner) or `EMPLOYEE`. Provided at registration and stored on `accounts.User.account_type`. |
| **Role** | Optional fine-grained platform role (`Admin`, `Manager`, `Cashier`, etc.) referenced through `accounts.Role`. |
| **Business Membership** | Active association between a user and a business (`accounts.BusinessMembership`). Roles `OWNER` and `ADMIN` are considered **business managers** and can administer employee accounts within their business. |

---

## 2. Registration Flow

### 2.1 Business Owner Registration

1. Call **POST** `/accounts/api/auth/register/` with payload:
   ```json
   {
     "name": "Ama Mensah",
     "email": "ama@example.com",
     "password": "<strong-password>",
     "account_type": "OWNER"
   }
   ```
  > 🔒 Do **not** send an `Authorization` header here—registration ignores authentication on purpose and stale tokens will be rejected.
2. Backend creates the user as inactive and sends an email verification link.
3. User confirms via **GET** or **POST** `/accounts/api/auth/verify-email/?token=<token>`.
4. After verification the owner can register a business using **POST** `/accounts/api/auth/register-business/`.

### 2.2 Employee Registration & Invitation Validation

1. Business owners/admins invite an employee via the `BusinessInvitation` flow (not covered in this document). Invitation stores email, role, status `PENDING`, and expiry.
2. Employee receives invitation email and proceeds to register:
   ```json
   {
     "name": "Yaw Owusu",
     "email": "yaw.employee@example.com",
     "password": "<strong-password>",
     "account_type": "EMPLOYEE"
   }
   ```
3. The backend validates:
   - Email is not already registered.
   - There is a **pending invitation** for that email.
   - Invitation is not expired.
4. After registration, verification email is sent. When the employee confirms the email:
   - `BusinessInvitation.status` becomes `ACCEPTED`.
   - `BusinessMembership` is created/updated to link the employee to the business with the invited role.
   - The new user is activated.

> ✅ Employees **cannot** successfully register without a pending invitation. Owners/admins must invite them first.

---

## 3. Authentication & Sessions

| Endpoint | Method | Notes |
| --- | --- | --- |
| `/accounts/api/auth/login/` | POST | Returns auth token when email verified & account active. |
| `/accounts/api/auth/logout/` | POST | Deletes the user’s auth tokens. |
| `/accounts/api/auth/change-password/` | POST | Authenticated users change their own password (requires old password). |

---

## 4. Password Reset Flow (Forgot Password)

### 4.1 Request Reset

- **Endpoint:** `POST /accounts/api/auth/password-reset/request/`
- **Body:**
  ```json
  { "email": "user@example.com" }
  ```
- **Behaviour:** Always returns HTTP 200 with a generic confirmation. If the email exists, verified, and active, the backend sends a password reset email containing:
  - A token for backend submission.
  - A direct link (`<FRONTEND_URL>/reset-password?token=...`).

### 4.2 Confirm Reset

- **Endpoint:** `POST /accounts/api/auth/password-reset/confirm/`
- **Body:**
  ```json
  {
    "token": "<token-from-email>",
    "new_password": "<new-strong-password>"
  }
  ```
- **Behaviour:**
  - Validates the token (unused & unexpired).
  - Updates the user password.
  - Invalidates all authentication tokens (forces re-login).
  - Returns HTTP 200 on success.

> 💡 Tokens expire after 2 hours (`PasswordResetToken.expires_at`). Frontend should surface error messages returned by the API.

---

## 5. Profile & User Management Permissions

### 5.1 Effective Rules

| Actor | Allowed Operations |
| --- | --- |
| User (self) | View & update own `User` record and `UserProfile`; change password; request password reset. |
| Business Owner/Admin | In addition to self-management, can view and modify `User` & `UserProfile` records for users who belong to the same business(es). |
| Global Admin / Superuser | Full access to all users and profiles. |

### 5.2 API Behaviour

- `GET /accounts/api/users/`
  - Employees see only themselves.
  - Owners/Admins see themselves + members of their managed businesses.
  - Global Admins/Superusers see everyone.
- `PATCH /accounts/api/users/{id}/`
  - Same access rules as above. Attempting to update a user outside permitted scope returns HTTP 403.
- `GET /accounts/api/profiles/`
  - Mirrors user permissions; results filtered with `.distinct()`.
- `PATCH /accounts/api/profiles/{id}/`
  - Same permission enforcement; unauthorized updates return HTTP 403.

---

## 6. Password Change (Authenticated)

- Endpoint: `POST /accounts/api/auth/change-password/`
- Body:
  ```json
  {
    "old_password": "<current>",
    "new_password": "<new>"
  }
  ```
- Validates that `old_password` matches and `new_password` differs from the old one.
- On success, the backend revokes existing auth tokens.

---

## 7. Email Verification

- Users are created as inactive until they verify via `/accounts/api/auth/verify-email/` (GET with query parameter or POST body containing token).
- Employee verification also activates their business membership and marks the invitation as accepted.
- ⚙️ **Email backend configuration:** ensure `EMAIL_BACKEND`, `EMAIL_HOST`, and related credentials are valid. In development the default console backend prints messages to the server logs. When SMTP credentials are invalid the API now returns a friendly validation error instead of crashing; surface that message to the user and allow retries.

---

## 8. Frontend Integration Checklist

1. **Registration Form**
   - Collect `name`, `email`, `password`, `account_type`.
   - For employee sign up, ensure an invitation email precedes registration.
2. **Email Verification Screen**
   - Handle redirect states: `success` or `error` query params.
3. **Login Screen**
   - Display validation errors returned by `/login/` (unverified email, inactive account, etc.).
4. **Forgot Password**
   - Form for `/password-reset/request/`.
   - Reset screen consuming `token` query parameter posting to `/password-reset/confirm/`.
5. **Profile Management UI**
   - Non-owners: edit only personal profile.
   - Owners/Admins: add UI for selecting & editing employees inside same business.
6. **Admin Dashboards**
   - Use `/users` and `/profiles` endpoints to list/manipulate team members.

---

## 9. Reference Models

- `accounts.User`
- `accounts.UserProfile`
- `accounts.Business`
- `accounts.BusinessMembership`
- `accounts.BusinessInvitation`
- `accounts.EmailVerificationToken`
- `accounts.PasswordResetToken`

Ensure migrations are applied (`python manage.py migrate`) before integrating with the frontend.
