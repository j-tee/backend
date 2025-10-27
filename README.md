# POS Backend - Django REST API

A comprehensive Point of Sale (POS) backend system built with Django REST Framework, featuring multi-tenant architecture, role-based access control (RBAC), inventory management, sales tracking, and subscription management.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Git

### Local Development Setup

```bash
# Clone the repository
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.production.example .env.development
# Edit .env.development with your local settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Running with Docker

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f
```

## 📋 Features

### Core Functionality
- **Multi-Tenant Architecture** - Complete business isolation with user-business relationships
- **RBAC (Role-Based Access Control)** - Fine-grained permissions system
- **Inventory Management** - Stock tracking, transfers, adjustments, and reconciliation
- **Sales Management** - Retail and wholesale sales with payment tracking
- **Subscription System** - Plan management and feature access control
- **Reporting & Analytics** - Comprehensive business reports and exports
- **Settings Management** - Business-specific configurations

### Key Modules

#### Accounts (`accounts/`)
- User authentication and authorization
- Business and employment management
- Role and permission management
- Multi-tenant user isolation

#### Inventory (`inventory/`)
- Product catalog management
- Stock level tracking with batch support
- Stock transfers between warehouses/storefronts
- Stock adjustments and reconciliation
- Movement history tracking

#### Sales (`sales/`)
- Sale creation and management (retail/wholesale)
- Payment tracking (cash, credit, mixed)
- Credit management and receivables
- Sale history and filtering
- Receipt generation (HTML, PDF)

#### Reports (`reports/`)
- Financial summaries
- Product performance analytics
- Sales reports with filtering
- Stock movement reports
- Export functionality (CSV, PDF, Excel)

#### Subscriptions (`subscriptions/`)
- Subscription plan management
- Feature access control
- Usage tracking and limits

#### Settings (`settings/`)
- Business-specific settings
- Tax and currency configuration
- Receipt customization
- System preferences

## 🏗️ Architecture

### Technology Stack
- **Framework**: Django 5.2.6 + Django REST Framework 3.14.0
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Task Queue**: Celery 5.3.4
- **Web Server**: Gunicorn 21.2.0 + Nginx
- **Authentication**: Token-based + Session

### Project Structure

```
backend/
├── accounts/           # User, business, RBAC
├── inventory/          # Products, stock, transfers
├── sales/              # Sales, payments, receipts
├── reports/            # Analytics and exports
├── subscriptions/      # Plans and billing
├── settings/           # Business settings
├── app/                # Django project settings
├── deployment/         # Deployment scripts and configs
├── docs/               # Documentation
├── logs/               # Application logs
├── media/              # User uploads
└── staticfiles/        # Static assets
```

## 🔒 Security Features

- ✅ Token-based authentication
- ✅ Row-level permissions with Django Guardian
- ✅ Business data isolation
- ✅ HTTPS/SSL ready
- ✅ CORS configuration
- ✅ Rate limiting
- ✅ Secure password hashing (Argon2)
- ✅ Environment-based configuration

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test inventory

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

## 📊 API Documentation

The API is built with Django REST Framework and includes:

- **Authentication**: `/api/auth/login/`, `/api/auth/logout/`
- **Accounts**: `/api/accounts/`, `/api/rbac/`
- **Inventory**: `/api/inventory/products/`, `/api/inventory/stock/`
- **Sales**: `/api/sales/`, `/api/sales/payments/`
- **Reports**: `/api/reports/sales/`, `/api/reports/financial/`
- **Settings**: `/api/settings/`

For detailed API documentation, see [`docs/API_ENDPOINTS_REFERENCE.md`](docs/API_ENDPOINTS_REFERENCE.md)

## 🚀 Deployment

### Production Deployment with CI/CD

We use GitHub Actions for automated deployment to a VPS.

**Quick deployment:**

1. Configure GitHub secrets (VPS details, SSH key)
2. Push to `main` branch
3. GitHub Actions automatically:
   - Runs tests
   - Deploys to VPS
   - Restarts services

**Detailed guides:**
- 📖 [Deployment Index](docs/DEPLOYMENT_INDEX.md) - **All deployment docs in one place!**
- 📖 [Complete Deployment Guide](docs/DEPLOYMENT_SETUP_COMPLETE.md) - Start here!
- 📖 [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Step-by-step instructions
- 📖 [Quick Reference](docs/QUICK_REFERENCE.md) - Common commands
- 📖 [Architecture](docs/ARCHITECTURE.md) - System architecture
- 📖 [Nginx Setup](docs/NGINX_SOURCE_SETUP.md) - Nginx configuration

### Manual Deployment

```bash
# SSH into server
ssh -p 7822 deploy@YOUR_SERVER_IP

# Navigate to project
cd /var/www/pos/backend

# Run deployment script
./deployment/deploy.sh
```

### Deployment Scripts

Located in `deployment/` folder:
- `initial_setup.sh` - First-time server setup
- `deploy.sh` - Manual deployment
- `ssl_setup.sh` - SSL certificate setup
- `health_check.sh` - System health verification
- `nginx_control.sh` - Nginx management (works with any installation)

## 🛠️ Configuration

### Environment Variables

Create `.env.development` or `.env.production` based on `.env.production.example`:

**Key settings:**
```env
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_NAME=pos_production
DB_USER=pos_user
DB_PASSWORD=your-password
DB_HOST=localhost

REDIS_URL=redis://localhost:6379
USE_REDIS_CACHE=True

FRONTEND_URL=https://your-frontend.com
CORS_ALLOWED_ORIGINS=https://your-frontend.com
```

See [`.env.production.example`](.env.production.example) for all available options.

## 📁 Key Files

### Configuration
- `app/settings.py` - Django settings
- `app/urls.py` - Main URL routing
- `requirements.txt` - Python dependencies
- `.env.production.example` - Environment template

### Deployment
- `Dockerfile` - Docker container configuration
- `docker-compose.yml` - Multi-container setup
- `nginx.conf` - Nginx web server config
- `.github/workflows/deploy.yml` - CI/CD pipeline
- `deployment/` - Deployment scripts and service files

### Utilities
- `scripts/` - Utility and data management scripts
- `debug/` - Debug and test scripts
- `tests/` - Django unit tests

### Documentation
All documentation is in the [`docs/`](docs/) folder

## 🤝 Contributing

### Development Workflow

1. Create a feature branch from `development`
2. Make your changes
3. Write/update tests
4. Run tests: `python manage.py test`
5. Create pull request to `development`
6. After review, merge to `main` for deployment

### Code Style

- Follow PEP 8
- Use meaningful variable names
- Add docstrings to functions and classes
- Keep functions small and focused
- Write tests for new features

## 📝 License

This project is proprietary software. All rights reserved.

## 📞 Support

For issues or questions:
- Check the [documentation](docs/)
- Review [troubleshooting guide](docs/DEPLOYMENT_GUIDE.md#troubleshooting)
- Contact the development team

## 🔗 Related Projects

- Frontend: [Link to frontend repo]
- Mobile App: [Link to mobile repo]

## 📚 Documentation Index

### Deployment Documentation
- [Deployment Index](docs/DEPLOYMENT_INDEX.md) 📑 **All deployment docs organized!**
- [Deployment Setup Complete](docs/DEPLOYMENT_SETUP_COMPLETE.md) ⭐ **Start here for deployment!**
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Quick Reference](docs/QUICK_REFERENCE.md)

### Architecture & Setup
- [System Architecture](docs/ARCHITECTURE.md)
- [Nginx Source Setup](docs/NGINX_SOURCE_SETUP.md)
- [Deployment Scripts](docs/DEPLOYMENT_README.md)

### API Documentation
- [API Endpoints Reference](docs/API_ENDPOINTS_REFERENCE.md)
- [RBAC Documentation](docs/RBAC_API_DOCUMENTATION.md)

### Feature Documentation
- [Stock Integrity System](docs/COMPLETE_STOCK_INTEGRITY_SYSTEM.md)
- [Subscription System](docs/SUBSCRIPTION_BACKEND_COMPLETE.md)
- [Credit Sales Tracking](docs/CREDIT_SALES_TRACKING_IMPLEMENTATION_COMPLETE.md)
- [Receipt System](docs/RECEIPT_SYSTEM_IMPLEMENTATION.md)
- [Reports System](docs/REPORTS_README.md)

### Frontend Integration
- [Frontend Integration Guide](docs/FRONTEND_INTEGRATION_GUIDE.md)
- [Frontend Quick Start](docs/FRONTEND_QUICK_START.md)

---

**Version**: 1.0.0  
**Last Updated**: October 27, 2025  
**Maintained by**: POS Development Team
