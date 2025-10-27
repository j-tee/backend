# Frontend Integration Notes

This document summarizes the current backend contracts and expectations needed to align the frontend registration, verification, and authentication flows.

---

## 1. Registration

### Endpoint
- `POST /accounts/api/auth/register/`

### Request Body
```json
{
  "name": "Ama Mensah",
  "email": "ama@example.com",
  "password": "<strong-password>",
  "account_type": "OWNER" | "EMPLOYEE"
}
```
- `account_type` defaults to `OWNER` when omitted.
- Employees must already have a pending invitation keyed by email.

### Success Response
- **Status:** `201 Created`
```json
{
  "message": "Account created. Check your email for the verification link.",
  "user_id": "<uuid>",
  "account_type": "OWNER" | "EMPLOYEE"
}
```

### Error Responses
- `400 Bad Request` with standard DRF error shapes. Examples:
  - Existing email:
    ```json
    { "email": ["A user with this email already exists."] }
    ```
  - Employee without invitation:
    ```json
    { "email": ["No pending employee invitation found for this email. Contact your business administrator."] }
    ```
  - Invitation expired:
    ```json
    { "email": ["The invitation for this email has expired. Request a new invitation from your administrator."] }
    ```
  - Email delivery failure:
    ```json
    { "email": ["Unable to send verification email. Please try again later."] }
    ```

---

## 2. Email Verification

### Endpoint
- `POST /accounts/api/auth/verify-email/`
- `GET /accounts/api/auth/verify-email/?token=<token>`

### POST Request Body
```json
{ "token": "<verification-token>" }
```

- Do **not** include an `Authorization` header or CSRF token—this endpoint is anonymous and explicitly CSRF-exempt for both POST and GET flows.

### Success Response
- **Status:** `200 OK`
```json
{
  "message": "Email verified successfully. You can now log in.",
  "user_id": "<uuid>",
  "account_type": "OWNER" | "EMPLOYEE"
}
```

### Error Responses (400)
- Invalid/unknown token:
  ```json
  { "token": ["Invalid or expired verification token."] }
  ```
- Already used token:
  ```json
  { "token": ["This verification token has already been used."] }
  ```
- Expired token:
  ```json
  { "token": ["This verification token has expired. Please register again to receive a new link."] }
  ```
- Employee missing a valid invitation at verification time:
  ```json
  { "non_field_errors": ["No valid employee invitation is available for this account."] }
  ```

- Verification email contains **one** frontend link (`<FRONTEND_URL>/verify-email?token=...`) and the raw token for manual entry. There is no second backend URL fallback anymore.
- **GET behaviour:** navigating to `/accounts/api/auth/verify-email/?token=...` still works for manual testing, but the email no longer surfaces this link to avoid confusion.

---

## 3. Login

### Endpoint
- `POST /accounts/api/auth/login/`

### Request Body
```json
{ "email": "...", "password": "..." }
```

### Success Response
- **Status:** `200 OK`
```json
{
  "token": "<auth-token>",
  "user": {
    "id": "<uuid>",
    "name": "...",
    "email": "...",
    "account_type": "OWNER" | "EMPLOYEE",
    "email_verified": true,
    "is_active": true,
    "role": null,
    "role_name": null,
    "subscription_status": "Inactive",
    "picture_url": null,
    "created_at": "...",
    "updated_at": "..."
    // plus other fields from UserSerializer
  }
}
```

### Error Responses (400)
Messages appear under `"non_field_errors"`:
- Email unverified: `"Email not verified. Please check your inbox for the verification link."`
- Account inactive: `"User account is disabled."`
- Invalid credentials: `"Invalid email or password."`

> Login never returns partial success. If authentication fails, no token is issued.

---

## 4. Invitation Handshake
- Employees must be invited before registering. Invitation lookup is automatic; no extra field is required in the registration payload.
- On verification success, the backend:
  - Marks the invitation as accepted.
  - Creates/updates `BusinessMembership` with role/admin flags from the invitation.
- Registration errors already cover missing/expired invitations.
- Verification errors cover invitations revoked between registration and verification.

---

## 5. Token Lifecycle & Reset

### Email Verification Tokens
- Valid for 48 hours.
- Error messages distinguish invalid, expired, and already used tokens.

### Password Reset
1. `POST /accounts/api/auth/password-reset/request/` with `{ "email": "..." }`
   - Always returns `200` with message; errors surface only when the email exists but is unverified or inactive.
2. `POST /accounts/api/auth/password-reset/confirm/`
   ```json
   { "token": "<reset-token>", "new_password": "<new-password>" }
   ```
   - Success `200`: `{ "message": "Password updated successfully. You can now sign in." }`
   - Errors mirror verification: invalid/expired/already used token, or new password matches old one (`{"new_password": ["The new password must be different from the current password."]}`).

---

## 6. Headers & CSRF
- Registration, verification, login, and password reset endpoints allow anonymous access and don’t require CSRF tokens. Simple JSON POSTs are fine from the SPA.
- Authenticated endpoints use `Authorization: Token <key>` header (DRF authtoken). No HTTP-only cookies by default.

---

## 7. Environment & CORS
- Base API URL defaults to the Django host (e.g., `http://localhost:8000`).
- `CORS_ALLOWED_ORIGINS` must include the frontend origin. Defaults cover `http://localhost:3000` and `http://localhost:5173`.
- Email delivery relies on the configured `EMAIL_BACKEND`. During development, switch to the console backend if SMTP credentials aren’t available.

---

## 8. Frontend To-Do Checklist
- **Registration:** Submit the payload above, display validation errors verbatim, prompt employees to request invitations when none exist.
- **Verification screen:** Handle redirect params from GET links; offer a manual token entry fallback via POST.
- **Login:** Surface backend messages (unverified, inactive, invalid credentials) and don’t store tokens on failure.
- **Invitation flows:** Include UX to resend or request invitations when registration fails for employees.
- **Password reset:** Implement request + confirm forms; handle error states for expired/invalid tokens.
- **Environment:** Ensure the frontend points at the correct API base and includes the token in Authorization headers post-login.

---

For any clarification or new flows, please reach out so we can expand this document.
