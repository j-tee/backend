# GitHub Secrets Setup Guide

## What We Found
- ✅ Your SSH key pair is: `~/.ssh/gha_ci` (private) and `~/.ssh/gha_ci.pub` (public)
- ✅ This key already works with your server (tested successfully)
- ✅ The public key is already in your server's authorized_keys

## Step-by-Step Instructions

### Step 1: Go to GitHub Repository Settings
1. Open your browser and go to: https://github.com/j-tee/backend
2. Click on **Settings** (top menu)
3. In the left sidebar, scroll down to **Security** section
4. Click **Secrets and variables** → **Actions**

### Step 2: Add SSH_PRIVATE_KEY Secret
1. Click the green **"New repository secret"** button
2. Name: `SSH_PRIVATE_KEY`
3. Value: Copy the ENTIRE content from the section below (including BEGIN and END lines)

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBEvxY3GMRLmZRBhYQKp0xFmVi+lTcmq9+lwk05LJOz0gAAAJg1WmHwNVph
8AAAAAtzc2gtZWQyNTUxOQAAACBEvxY3GMRLmZRBhYQKp0xFmVi+lTcmq9+lwk05LJOz0g
AAAEByO43IR3ugyRpPz9JHxDC6pJJWtZEag1E0xBh9P7zoB0S/FjcYxEuZlEGFhAqnTEWZ
WL6VNyar36XCTTksk7PSAAAADmdpdGh1Yi1hY3Rpb25zAQIDBAUGBw==
-----END OPENSSH PRIVATE KEY-----
```

4. Click **"Add secret"**

### Step 3: Add VPS_HOST Secret
1. Click **"New repository secret"** again
2. Name: `VPS_HOST`
3. Value: `68.66.251.79`
4. Click **"Add secret"**

### Step 4: Add VPS_USERNAME Secret
1. Click **"New repository secret"** again
2. Name: `VPS_USERNAME`
3. Value: `deploy`
4. Click **"Add secret"**

### Step 5: Add VPS_PORT Secret
1. Click **"New repository secret"** again
2. Name: `VPS_PORT`
3. Value: `7822`
4. Click **"Add secret"**

### Step 6: Verify Your Secrets
After adding all 4 secrets, you should see them listed:
- SSH_PRIVATE_KEY
- VPS_HOST
- VPS_USERNAME
- VPS_PORT

**Note:** You won't be able to view the secret values after saving (GitHub hides them for security).

### Step 7: Test the Deployment
1. Go to the **Actions** tab in your repository
2. Find the failed "Deploy to Production" workflow
3. Click on it
4. Click **"Re-run all jobs"** button
5. Watch it run - the deploy step should now work!

## Questions?
- **Q: What if I make a mistake entering a secret?**
  - A: You can click on the secret name and choose "Update" to change it.

- **Q: Do I need to update the deploy.yml file?**
  - A: No! The file is already configured correctly. You just need to add the secrets.

- **Q: Is it safe to have the private key in this file?**
  - A: Delete this file after you're done setting up the secrets. Run: `rm GITHUB_SECRETS_SETUP.md`
