# SaaS POS Backend System

A comprehensive Django-based Point of Sale (POS) backend system designed for SaaS deployment with multi-user support, inventory management, sales processing, bookkeeping, and subscription management.

## Features

### Core Features
- **Multi-user support** with role-based access control (Admin, Manager, Cashier, Warehouse Staff)
- **Secure authentication** with token-based authentication
- **Multi-warehouse inventory management** with batch tracking
- **Retail and wholesale sales processing**
- **Customer management** with credit line tracking
- **Double-entry bookkeeping** and accounting
- **Subscription management** with multiple payment gateways
- **Comprehensive reporting** and analytics
- **Audit trail** for all critical operations

### Technical Features
- **REST API** built with Django REST Framework
- **PostgreSQL** database with UUID primary keys
- **Redis** for caching and background task queuing
- **Celery** for background task processing
- **Docker** containerization support
- **Comprehensive logging** and error handling

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django API    │    │   Database      │
│   (React/Vue)   │◄──►│   (REST API)    │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Celery        │◄──►│   Redis         │
                       │   (Background)  │    │   (Cache/Queue) │
                       └─────────────────┘    └─────────────────┘
```

## Database Schema

The system includes the following main models:

### User Management
- **Roles**: User roles (Admin, Manager, Cashier, Warehouse Staff)
- **Users**: Custom user model with role-based permissions
- **UserProfiles**: Extended user information
- **AuditLogs**: Complete audit trail

### Inventory Management
- **Categories**: Product categorization
- **Warehouses**: Storage locations
- **StoreFronts**: Retail locations
- **Batches**: Imported goods tracking
- **Products**: Product catalog (metadata only; selling prices now live on stock items)
- **BatchProducts**: Products within batches
- **Inventory**: Current stock levels
- **Transfers**: Warehouse to storefront transfers
- **StockAlerts**: Low stock notifications

### Sales Management
- **Customers**: Customer information and credit management
- **Sales**: Sales transactions
- **SalesItems**: Individual sale items
- **Payments**: Payment tracking
- **Refunds**: Return processing
- **CreditTransactions**: Customer credit history

### Bookkeeping
- **AccountTypes**: Chart of accounts structure
- **Accounts**: Financial accounts
- **JournalEntries**: Double-entry journal entries
- **LedgerEntries**: Individual ledger lines
- **TrialBalance**: Financial period summaries
- **Budgets**: Budget planning and tracking

### Subscriptions
- **SubscriptionPlans**: Available plans
- **Subscriptions**: User subscriptions
- **SubscriptionPayments**: Payment processing
- **PaymentGatewayConfig**: Gateway configurations
- **WebhookEvents**: Payment webhook handling
- **UsageTracking**: Usage limits monitoring
- **Invoices**: Billing and invoicing

## Quick Start

### Platform Owner Superuser

Set the `PLATFORM_OWNER_EMAIL` environment variable to the email address of the platform owner. After migrations run, that user is automatically granted the `Admin` role along with Django `is_staff` and `is_superuser` flags, guaranteeing full access without hidden backdoors. Example for local development:

```bash
export PLATFORM_OWNER_EMAIL=owner@example.com
```

### Development API throttling

API throttling is disabled automatically while `DEBUG` is `True` so that local development and automated tests aren’t blocked by rate limits. Set `ENABLE_API_THROTTLE=true` in your environment if you need to exercise the production throttling behavior locally.

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+
- Redis 7+

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pos-backend
   ```

2. **Start the services**
   ```bash
   docker-compose up -d
   ```

3. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

4. **Initialize the system**
   ```bash
   docker-compose exec web python manage.py init_system
   ```

5. **Seed demo businesses and transactional data (optional)**
   ```bash
   docker-compose exec web python manage.py seed_demo_data --owners 5
   ```
   This command provisions realistic demo records including business owners, warehouses, storefronts, stock, sales, and active subscriptions. Default owner passwords are set to `DemoPass123!` for quick logins.

5. **Create a superuser (optional)**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

The API will be available at `http://localhost:8000`

### Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up PostgreSQL and Redis**
   ```bash
   # Install and start PostgreSQL
   createdb pos_db
   createuser pos_user
   
   # Install and start Redis
   redis-server
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

4. **Initialize the system**
   ```bash
   python manage.py init_system --admin-email=admin@example.com --admin-password=admin123
   ```

5. **Seed demo businesses and transactional data (optional)**
   ```bash
   python manage.py seed_demo_data --owners 5
   ```
   Adjust `--owners`, `--max-warehouses`, and `--max-storefronts` to control dataset size. Each generated owner receives the password `DemoPass123!`.

6. **Start the development server**
   ```bash
   python manage.py runserver
   ```

7. **Start Celery worker (in another terminal)**
   ```bash
   celery -A app worker -l info
   ```

8. **Start Celery beat (in another terminal)**
   ```bash
   celery -A app beat -l info
   ```

## API Endpoints

### Authentication
- `POST /accounts/api/auth/login/` - User login
- `POST /accounts/api/auth/logout/` - User logout
- `POST /accounts/api/auth/change-password/` - Change password

### User Management
- `GET /accounts/api/roles/` - List roles
- `GET /accounts/api/users/` - List users
- `GET /accounts/api/users/me/` - Current user profile
- `POST /accounts/api/users/` - Create user

### Inventory Management
- `GET /inventory/api/warehouses/` - List warehouses
- `GET /inventory/api/products/` - List products
- `GET /inventory/api/batches/` - List batches
- `GET /inventory/api/inventory/` - Current inventory levels
- `POST /inventory/api/transfers/` - Create transfer

### Sales Management
- `GET /sales/api/customers/` - List customers
- `POST /sales/api/sales/` - Create sale
- `GET /sales/api/payments/` - List payments
- `GET /sales/api/reports/sales/` - Sales reports

### Bookkeeping
- `GET /bookkeeping/api/accounts/` - Chart of accounts
- `POST /bookkeeping/api/journal-entries/` - Create journal entry
- `GET /bookkeeping/api/trial-balances/` - Trial balance

### Subscriptions
- `GET /subscriptions/api/plans/` - Available plans
- `POST /subscriptions/api/subscriptions/` - Create subscription
- `POST /subscriptions/api/webhooks/payment/` - Payment webhooks

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgres://pos_user:pos_password@localhost:5432/pos_db
REDIS_URL=redis://localhost:6379/0

# Payment Gateway Settings
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_SECRET_KEY=sk_test_...

# Email Settings
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password
```

### Role-Based Access Control

The system implements four main roles:

1. **Admin**: Full system access, user management, system configuration
2. **Manager**: Store management, reporting, inventory oversight
3. **Cashier**: Sales processing, customer management, basic reporting
4. **Warehouse Staff**: Inventory management, transfers, batch processing

## API Documentation

The API documentation is available at:
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- ReDoc: `http://localhost:8000/api/schema/redoc/`
- OpenAPI Schema: `http://localhost:8000/api/schema/`

## Testing

Run the test suite:

```bash
# Using Docker
docker-compose exec web python manage.py test

# Local development
python manage.py test
```

## Background Tasks

The system uses Celery for background processing:

- **User management**: Welcome emails, account cleanup
- **Inventory**: Stock level monitoring, low stock alerts
- **Sales**: Receipt generation, inventory updates, expired reservation cleanup
- **Subscriptions**: Renewal notifications, payment processing
- **Reporting**: Periodic report generation
- **Stock reservations**: `sales.tasks.release_expired_reservations` runs via Celery beat every 15 minutes to free stale holds. Trigger manually anytime with `python manage.py release_expired_reservations` (use `--dry-run` to preview).

## Monitoring and Logging

Logs are stored in the `logs/` directory and include:
- Application logs (`django.log`)
- Individual app logs
- Celery task logs
- Error tracking

## Security Features

- **Token-based authentication**
- **Role-based access control**
- **Input validation and sanitization**
- **SQL injection protection**
- **XSS protection**
- **CSRF protection**
- **Rate limiting**
- **Complete audit trail**

## Deployment

### Production Deployment

1. **Set production environment variables**
2. **Use PostgreSQL and Redis**
3. **Configure SSL/TLS**
4. **Set up monitoring**
5. **Configure backups**

### Scaling

The system is designed to scale horizontally:
- **Database**: PostgreSQL with read replicas
- **Cache**: Redis Cluster
- **Application**: Multiple Django instances behind load balancer
- **Background tasks**: Multiple Celery workers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

---

**Note**: This is a comprehensive backend system. Make sure to properly configure security settings, payment gateways, and monitoring before deploying to production.