# Process Dashboard API

**Business Process Monitoring & Management Platform**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-2019+-red?logo=microsoft-sql-server)](https://microsoft.com/sql-server)

> A REST API solution for real-time business process visualization, monitoring, and management.

---

## **Summary**

The Process Dashboard API provides a platform for:

- **Integration** - RESTful design for seamless third-party integration
- **Real-time Process Monitoring** - Track business process execution across multiple systems
- **Retry Management** - Automated failure recovery with configurable retry strategies  
- **Security** - Role-based API authentication with audit trails
- **Data Retention** - Configurable retention policies with GDPR-compliant data neutralization
- **Pagination** - Standardized pagination with RFC 8288 Link headers
- **Features** - Advanced filtering, search, and dashboard capabilities

## **System Architecture**

### **Technology Foundation**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client Apps   │───>│   FastAPI Core   │───>│   SQL Server    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Docker Runtime  │
                       └──────────────────┘
```

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Framework** | FastAPI 0.104+ | High-performance async web framework |
| **Data Layer** | SQLModel + SQLAlchemy | Type-safe ORM with automatic validation |
| **Database** | Microsoft SQL Server | Enterprise-grade persistence layer |
| **Authentication** | Custom JWT + API Keys | Multi-tier security with role-based access |
| **Pagination** | fastapi-pagination | RFC 8288 compliant pagination with Link headers |
| **Deployment** | Docker + Compose | Containerized deployment and scaling |
| **Package Management** | UV | Fast Python dependency resolution |

### **Security Architecture**

```mermaid
graph TD
    A[Client Request] --> B{API Key Valid?}
    B -->|No| C[401 Unauthorized]
    B -->|Yes| D{Role Check}
    D -->|Admin| E[Full Access]
    D -->|User| F[Data Access Only]
    E --> G[Resource Access]
    F --> G[Resource Access]
    G --> H[Audit Log]
```

## **Getting Started**

### **Prerequisites**
- Docker Desktop 4.0+
- Git
- Network access to SQL Server instance

### **Quick Deployment**

1. **Clone and Configure**
   ```bash
   git clone https://github.com/AAK-MBU/Process_Dashboard_API.git
   cd Process_Dashboard_API
   
   # Configure environment
   cp .env.example .env
   # Edit .env with your database connection details
   ```

2. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

3. **Run Database Migrations** (if upgrading from older version)
   ```bash
   # Connect to your SQL Server and run migration scripts
   sqlcmd -S your-server -d process_monitor -i scripts/migrations/001_add_soft_delete_and_retention.sql
   
   # Or use Azure Data Studio / SQL Server Management Studio
   # See scripts/migrations/README.md for details
   ```

4. **Initialize Security**
   ```bash
   # Create admin API key
   docker exec process-visualization-api uv run python scripts/add_api_key_roles.py
   
   # Note the returned admin key for initial setup
   ```

5. **Verify Installation**
   ```bash
   curl -H "X-API-Key: YOUR_ADMIN_KEY" \
        http://localhost:8000/api/v1/auth/verify
   ```

### **Environment Configuration**

```bash
# .env file example
DATABASE_URL=mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+18+for+SQL+Server
DEBUG=false
CORS_ORIGINS='["http://localhost:3000","http://localhost:8080"]'
```

---

## **Authentication & Authorization**

### **Access Control Model**

The API implements a two-tier role-based access control system:

| Role | Capabilities | Use Cases |
|------|-------------|-----------|
| **Administrator** | • Full API access<br>• API key management<br>• User administration<br>• System configuration | System administrators, DevOps teams |
| **User** | • Process data access<br>• Read/write operations<br>• Dashboard access<br>• Monitoring capabilities | Applications, end users, integrations |

### **API Key Management**

#### **Create API Key** (Administrator Only)
```http
POST /api/v1/api-keys/
X-API-Key: {ADMIN_KEY}
Content-Type: application/json

{
  "name": "Production Application Key",
  "description": "API key for production dashboard application",
  "role": "user",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**Response:**
```json
{
  "id": 5,
  "name": "Production Application Key",
  "role": "user",
  "key_prefix": "Secrect_key_prefix",
  "key": "Secrect_key_",
  "created_at": "2025-10-03T10:30:00Z",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

> **Security Notice**: API keys are only displayed once during creation. Store them securely.

#### **List API Keys** (Administrator Only)
```http
GET /api/v1/api-keys/
X-API-Key: {ADMIN_KEY}
```

#### **Revoke API Key** (Administrator Only)
```http
DELETE /api/v1/api-keys/{key_id}
X-API-Key: {ADMIN_KEY}
```

### **Authentication Endpoints**

#### **Verify API Key**
```http
GET /api/v1/auth/verify
X-API-Key: {API_KEY}
```

**Response:**
```json
{
  "status": "valid",
  "message": "API key is valid",
  "key_info": {
    "id": 5,
    "name": "Production Application Key",
    "role": "user",
    "usage_count": 127,
    "last_used_at": "2025-10-03T10:29:45Z",
    "is_active": true
  }
}
```

#### **Get Current Key Details**
```http
GET /api/v1/auth/me
X-API-Key: {API_KEY}
```

---

## **Data Retention & Privacy Management**

### **Overview**

The API implements comprehensive data retention and privacy management capabilities to support GDPR compliance and data lifecycle management.

### **Key Features**

- **Soft Delete** - Recoverable deletion with retention periods. Soft-deleted items are automatically hidden from all API responses.
- **Configurable Retention** - Set custom retention periods per process (e.g., 6, 12, 48 months)
- **Automatic Neutralization** - Scheduled removal of personally identifiable information (PII)
- **Audit Trail** - Complete tracking of all deletion and neutralization operations

### **Retention Policy Management**

#### **Set Retention Period for Process**
```http
PUT /api/v1/processes/{process_id}/retention
X-API-Key: {ADMIN_KEY}
Content-Type: application/json

{
  "retention_months": 12
}
```

**Common Retention Periods:**
- `6` - 6 months (short-term operational data)
- `12` - 1 year (standard business processes)
- `48` - 4 years (regulatory compliance requirements)
- `null` - No automatic retention (manual cleanup only)

#### **Soft Delete Process**
```http
DELETE /api/v1/processes/{process_id}
X-API-Key: {ADMIN_KEY}
```

**Behavior:**
- Process marked as deleted (not permanently removed)
- All associated runs and steps marked as deleted
- Soft-deleted items are automatically hidden from all list endpoints and queries
- Accessing a soft-deleted item by ID returns 404 (not found)
- Data remains recoverable until retention period expires
- Use the restore endpoint to make the process visible again

#### **Restore Deleted Process**
```http
POST /api/v1/processes/{process_id}/restore
X-API-Key: {ADMIN_KEY}
```

#### **Soft Delete Process Run**
```http
DELETE /api/v1/runs/{run_id}
X-API-Key: {ADMIN_KEY}
```

#### **Restore Deleted Run**
```http
POST /api/v1/runs/{run_id}/restore
X-API-Key: {ADMIN_KEY}
```

### **Data Neutralization**

#### **Neutralize Run Data** (Remove PII)
```http
POST /api/v1/runs/{run_id}/neutralize
X-API-Key: {ADMIN_KEY}
```

**Neutralization Process:**
1. `entity_id` - Replaced with "NEUTRALIZED_{run_id}"
2. `entity_name` - Set to null
3. `meta` - Sensitive fields removed from JSON metadata
4. `is_neutralized` - Flag set to true (irreversible)

**Example Before:**
```json
{
  "entity_id": "12345678-1234",
  "entity_name": "John Doe",
  "meta": {
    "email": "john.doe@example.com",
    "phone": "+45 12 34 56 78",
    "address": "Main Street 123"
  }
}
```

**Example After:**
```json
{
  "entity_id": "NEUTRALIZED_42",
  "entity_name": null,
  "meta": {
    "department": "Sales",
    "region": "EMEA"
  },
  "is_neutralized": true
}
```

### **Administrative Cleanup**

#### **Get Cleanup Statistics**
```http
GET /api/v1/admin/cleanup/stats?limit=10
X-API-Key: {ADMIN_KEY}
```

**Response:**
```json
{
  "total_due_for_neutralization": 150,
  "sample_run_ids": [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
}
```

#### **Trigger Batch Neutralization**
```http
POST /api/v1/admin/cleanup/neutralize?limit=100&dry_run=false
X-API-Key: {ADMIN_KEY}
```

**Parameters:**
- `limit` - Maximum number of runs to process (default: 100, max: 1000)
- `dry_run` - Preview only without making changes (default: true)

**Response:**
```json
{
  "neutralized_count": 87,
  "failed_count": 0,
  "neutralized_run_ids": [42, 43, 44, ...],
  "failed_run_ids": []
}
```

### **Retention Workflow**

```
Process Run Created
        │
        ▼
[scheduled_deletion_at = created_at + retention_months]
        │
        ▼
    Time Passes
        │
        ▼
[scheduled_deletion_at reached]
        │
        ▼
Admin Triggers Cleanup
        │
        ▼
[PII Neutralized - Irreversible]
        │
        ▼
[Run retained for statistical/audit purposes]
```

---

## **Core API Reference**

### **Process Management**

#### **List Processes**
```http
GET /api/v1/processes/
X-API-Key: {API_KEY}

# Pagination Parameters
?page=1&size=50
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Customer Onboarding",
      "meta": {...},
      "created_at": "2025-10-03T10:00:00Z",
      "updated_at": "2025-10-03T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 50,
  "pages": 3
}
```

**Response Headers:**
```
Link: <http://api/v1/processes/?page=1&size=50>; rel="first", 
      <http://api/v1/processes/?page=3&size=50>; rel="last",
      <http://api/v1/processes/?page=2&size=50>; rel="next"
X-Total-Count: 150
X-Page: 1
X-Page-Size: 50
X-Total-Pages: 3
```

**Pagination Parameters:**
- `page` - Page number (default: 1, minimum: 1)
- `size` - Items per page (default: 50, maximum: 100)

**Note:** Only returns active (non-deleted) processes. Soft-deleted processes are automatically excluded.

#### **Create Process**
```http
POST /api/v1/processes/
X-API-Key: {API_KEY}
Content-Type: application/json

{
  "name": "Customer Onboarding",
  "meta": {
    "description": "Automated customer onboarding workflow",
    "department": "Customer Success",
    "owner": "system.automation",
    "version": "2.1.0"
  }
}
```

#### **Get Process Details**
```http
GET /api/v1/processes/{process_id}
X-API-Key: {API_KEY}
```

### **Process Execution Management**

#### **Start Process Execution**
```http
POST /api/v1/runs/
X-API-Key: {API_KEY}
Content-Type: application/json

{
  "process_id": 1,
  "entity_id": "CUST-20251003-001",
  "entity_name": "Acme Corporation",
  "meta": {
    "initiated_by": "api.integration",
    "priority": "high",
    "environment": "production",
    "correlation_id": "req-20251003-12345"
  }
}
```

#### **Query Process Runs**
```http
GET /api/v1/runs/
X-API-Key: {API_KEY}

# Advanced Filtering with Pagination
?entity_name=Acme
&status=completed
&created_after=2025-10-01T00:00:00Z
&created_before=2025-10-31T23:59:59Z
&meta_filter=priority:high
&meta_filter=environment:production
&order_by=created_at
&sort_direction=desc
&page=1
&size=50
```

**Response:**
```json
{
  "items": [
    {
      "id": 42,
      "process_id": 1,
      "entity_id": "CUST-20251003-001",
      "entity_name": "Acme Corporation",
      "status": "completed",
      "meta": {...},
      "started_at": "2025-10-03T10:00:00Z",
      "finished_at": "2025-10-03T10:15:00Z"
    }
  ],
  "total": 250,
  "page": 1,
  "size": 50,
  "pages": 5
}
```

**Query Parameters:**
- **Filters:**
  - `process_id` - Filter by process ID
  - `entity_id` - Filter by entity ID
  - `entity_name` - Partial match on entity name
  - `status` - Filter by run status
  - `started_after`, `started_before` - Date filters (ISO 8601 format)
  - `finished_after`, `finished_before` - Date filters (ISO 8601 format)
  - `meta_filter` - Filter by metadata (format: `field:value`). Can be specified multiple times for multiple filters. Multiple values for the same field are OR'd together, different fields are AND'd together.
- **Sorting:**
  - `order_by` - Field to sort by (default: `created_at`)
  - `sort_direction` - Sort direction: `asc` or `desc` (default: `desc`)
- **Pagination:**
  - `page` - Page number (default: 1)
  - `size` - Items per page (default: 50, maximum: 100)

**Note:** Only returns active (non-deleted) runs. Soft-deleted runs are automatically excluded from results.

#### **Get Process Run Details**
```http
GET /api/v1/runs/{run_id}
X-API-Key: {API_KEY}
```

### **Step Management**

#### **List Process Steps**
```http
GET /api/v1/steps/process/{process_id}
X-API-Key: {API_KEY}
```

**Note:** Only returns active (non-deleted) steps. Soft-deleted steps are automatically excluded.

#### **Get Rerunnable Steps**
```http
GET /api/v1/steps/process/{process_id}/rerunnable
X-API-Key: {API_KEY}
```

**Note:** Only returns active (non-deleted) steps. Soft-deleted steps are automatically excluded.

### **Step Execution Management**

#### **Update Step Execution Status**
```http
PATCH /api/v1/step-runs/{step_run_id}
X-API-Key: {API_KEY}
Content-Type: application/json

{
  "status": "success",
  "started_at": "2025-10-03T10:15:00Z",
  "finished_at": "2025-10-03T10:17:30Z",
  "meta": {
    "processing_time_ms": 150000,
    "records_processed": 1247,
    "error_details": null,
    "output_location": "s3://bucket/outputs/run-123.json"
  }
}
```

#### **Rerun Failed Step**
```http
POST /api/v1/step-runs/{step_run_id}/rerun
X-API-Key: {API_KEY}
Content-Type: application/json

{
  "meta": {
    "rerun_reason": "Temporary network issue resolved",
    "initiated_by": "admin.user",
    "rerun_strategy": "full_retry"
  }
}
```

**Response:**
```json
{
  "id": 156,
  "original_step_run_id": 123,
  "status": "pending",
  "created_at": "2025-10-03T10:30:00Z",
  "message": "Step rerun initiated successfully"
}
```

---

## **Rerun System Architecture**

### **Configurable Rerun Strategy**

Process steps can be configured for intelligent rerun capabilities:

```json
{
  "is_rerunnable": true,
  "rerun_config": {
    "subprocess_id": "data_extraction_v2",
    "api_endpoint": "https://api.external-system.com/process",
    "timeout_seconds": 300,
    "max_retries": 3,
    "retry_delays": [60, 120, 300],
    "failure_conditions": ["network_error", "timeout", "rate_limit"]
  }
}
```

### **Rerun Workflow**

```mermaid
sequenceDiagram
    participant U as User
    participant API as Process API
    participant DB as Database
    participant EXT as External System
    
    U->>API: POST /step-runs/{id}/rerun
    API->>DB: Validate step is rerunnable
    API->>DB: Create new StepRun record
    API->>EXT: Execute configured subprocess
    EXT-->>API: Return results
    API->>DB: Update step status
    API->>U: Return rerun status
```

### **Dashboard Integration**

```http
GET /api/v1/dashboard/process/{process_id}
X-API-Key: {API_KEY}
```

**Note:** Dashboard only shows active (non-deleted) runs. Soft-deleted runs are automatically excluded.

**Response:**
```json
{
  "process": {
    "id": 1,
    "name": "Customer Onboarding",
    "total_steps": 8
  },
  "runs": [
    {
      "id": 123,
      "entity_name": "Acme Corp",
      "status": "completed",
      "success_rate": 87.5
    }
  ],
  "statistics": {
    "total_runs": 1247,
    "completed_runs": 1156,
    "failed_runs": 45,
    "running_runs": 46,
    "average_completion_time": "00:14:32"
  }
}
```

---

## **Configuration & Environment**

### **Environment Variables**

Create a `.env` file in your project root:

```bash
# Database Configuration
DATABASE_URL=mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+17+for+SQL+Server

# Application Configuration
DEBUG=false
API_V1_PREFIX=/api/v1

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000","https://dashboard.company.com"]

```

### **Docker Environment**

For Docker deployments, use environment variables:

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    environment:
      - DATABASE_URL=mssql+pyodbc://sa:YourPassword@db/ProcessDashboard?driver=ODBC+Driver+18+for+SQL+Server
      - DEBUG=false
      - CORS_ORIGINS=["http://localhost:3000"]
    ports:
      - "8000:8000"
    depends_on:
      - db
    restart: unless-stopped
    
  db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - SA_PASSWORD=YourPassword123!
      - ACCEPT_EULA=Y
    ports:
      - "1433:1433"
```

---

## **Development & Deployment**

### **Local Development Setup**

```bash
# Clone repository
git clone https://github.com/AAK-MBU/Process_Dashboard_API.git
cd Process_Dashboard_API

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies with uv
uv sync

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python scripts/migrate_db.py

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **Production Deployment**

#### **Prerequisites**
- **Docker** & **Docker Compose**
- **SQL Server** (2019+ recommended)
- **SSL Certificate** (for HTTPS)
- **Load Balancer** (for high availability)

#### **Database Setup**
```sql
-- Create database
CREATE DATABASE ProcessDashboard;

-- Create application user
CREATE LOGIN process_api WITH PASSWORD = 'SecurePassword123!';
USE ProcessDashboard;
CREATE USER process_api FOR LOGIN process_api;
EXEC sp_addrolemember 'db_datareader', 'process_api';
EXEC sp_addrolemember 'db_datawriter', 'process_api';
EXEC sp_addrolemember 'db_ddladmin', 'process_api';
```

#### **Initial Admin Setup**
```bash
# Create first admin API key
docker exec -it process-dashboard-api python -c "
from app.database import get_session
from app.models import ApiKey

session = next(get_session())
admin_key = ApiKey.create_key(
    name='Initial Admin Key',
    description='Bootstrap admin key for initial setup',
    role='admin'
)
session.add(admin_key)
session.commit()
print(f'Admin Key: {admin_key.key}')
"
```

---

## **Pagination**

### **Overview**

All list endpoints support standardized pagination using the `page` and `size` query parameters. The API returns pagination metadata in both the response body and HTTP headers.

### **Paginated Endpoints**

The following endpoints support pagination:

- `GET /api/v1/processes/` - List all processes
- `GET /api/v1/runs/` - List all process runs
- `GET /api/v1/admin/api-keys/` - List all API keys (admin only)

### **Query Parameters**

| Parameter | Type | Default | Maximum | Description |
|-----------|------|---------|---------|-------------|
| `page` | integer | 1 | - | Page number (1-indexed) |
| `size` | integer | 50 | 100 | Number of items per page |

### **Response Format**

All paginated endpoints return a consistent response structure:

```json
{
  "items": [
    {
      "id": 1,
      "...": "..."
    }
  ],
  "total": 150,
  "page": 1,
  "size": 50,
  "pages": 3
}
```

**Fields:**
- `items` - Array of data objects for the current page
- `total` - Total number of records matching the query
- `page` - Current page number
- `size` - Number of items per page
- `pages` - Total number of pages available

### **Response Headers**

#### **Link Header (RFC 8288)**

The `Link` header provides navigation URLs for pagination:

```
Link: <http://api/v1/resource?page=1&size=50>; rel="first",
      <http://api/v1/resource?page=5&size=50>; rel="last",
      <http://api/v1/resource?page=1&size=50>; rel="prev",
      <http://api/v1/resource?page=3&size=50>; rel="next"
```

**Relations:**
- `first` - URL to the first page
- `last` - URL to the last page
- `prev` - URL to the previous page (omitted if on first page)
- `next` - URL to the next page (omitted if on last page)

**Note:** The Link header preserves all query parameters (filters, sorting, etc.) for easy navigation.

#### **Custom Headers**

Additional headers provide quick access to pagination metadata:

| Header | Description | Example |
|--------|-------------|---------|
| `X-Total-Count` | Total number of records | `150` |
| `X-Page` | Current page number | `2` |
| `X-Page-Size` | Items per page | `50` |
| `X-Total-Pages` | Total number of pages | `3` |

### **Usage Examples**

#### **Basic Pagination**

```http
GET /api/v1/processes/?page=1&size=25
X-API-Key: {API_KEY}
```

#### **With Filters and Sorting**

```http
GET /api/v1/runs/?page=2&size=10&process_id=1&order_by=created_at&sort_direction=desc
X-API-Key: {API_KEY}
```

---

## **Monitoring & Observability**

### **Health Checks**

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-03T10:30:00Z",
  "version": "1.0.0",
  "database": "connected",
  "uptime": "7d 12h 30m"
}
```

### **System Information**

```http
GET /
```

**Response:**
```json
{
  "name": "Process Dashboard API",
  "version": "1.0.0",
  "description": "Enterprise process monitoring and management API",
  "environment": "production",
  "features": [
    "api_key_authentication",
    "role_based_access",
    "step_rerun_system",
    "metadata_filtering"
  ]
}
```

### **Usage Analytics**

```http
GET /api/v1/auth/usage-stats
X-API-Key: {API_KEY}
```

**Response:**
```json
{
  "key_id": 5,
  "usage_count": 1247,
  "last_used_at": "2025-10-03T10:29:45Z",
  "daily_usage": 156,
  "weekly_usage": 892,
  "top_endpoints": [
    {"endpoint": "/api/v1/runs/", "count": 45},
    {"endpoint": "/api/v1/processes/", "count": 12}
  ]
}
```

---

## **Troubleshooting**

### **Common Issues**

#### **Database Connection Issues**

```bash
# Test database connectivity
docker exec -it process-dashboard-api python -c "
from app.database import engine
try:
    engine.connect()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
"
```

**Solutions:**
- Verify connection string format
- Check SQL Server authentication mode
- Ensure ODBC driver 18+ is installed
- Verify network connectivity and firewall rules

#### **API Key Authentication Errors**

```json
{
  "detail": "Invalid or expired API key"
}
```

**Debugging Steps:**
1. Verify key format starts with `pd_`
2. Check key expiration date with `/api/v1/auth/verify`
3. Verify key is active in database
4. Check rate limiting status

#### **Migration Issues**

```bash
# Manual migration execution
docker exec -it process-dashboard-api python scripts/migrate_db.py

# Add role support to existing installation
docker exec -it process-dashboard-api python scripts/add_api_key_roles.py
```

**Common Fixes:**
- Ensure database user has DDL permissions
- Check for table name conflicts
- Verify SQL Server compatibility mode

### **Error Response Format**

```json
{
  "detail": "Descriptive error message",
  "status_code": 400,
  "error_type": "validation_error",
  "timestamp": "2025-10-03T10:30:00Z"
}
```

### **Common Status Codes**
- **200** - Success
- **201** - Created
- **400** - Bad Request / Validation Error
- **401** - Invalid or Missing API Key
- **403** - Insufficient Permissions (Wrong Role)
- **404** - Resource Not Found
- **422** - Unprocessable Entity
- **429** - Rate Limited
- **500** - Internal Server Error

---

## **Security Best Practices**

### **API Key Management**

1. **Storage Security**
   - Never log full API keys
   - Use secure key management systems
   - Implement key escrow for critical operations

2. **Access Control**
   - Follow principle of least privilege
   - Separate admin and user keys by function
   - Regular access reviews and audits

### **Network Security**

1. **HTTPS Only**
   - Force SSL/TLS encryption
   - Use HSTS headers
   - Implement certificate pinning

---

## **API Documentation**

### **Interactive Documentation**

When the server is running, access:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### **Advanced Filtering Examples**

#### **Metadata Filtering**
```http
# Filter by custom metadata fields
# Multiple filters: same field = OR, different fields = AND
GET /api/v1/runs/?meta_filter=department:Sales&meta_filter=priority:high&meta_filter=region:EMEA
X-API-Key: {API_KEY}

# Example: Filter by multiple values for the same field (OR logic)
GET /api/v1/runs/?meta_filter=department:Sales&meta_filter=department:Marketing
X-API-Key: {API_KEY}

# Values can contain commas
GET /api/v1/runs/?meta_filter=company:Acme, Inc&meta_filter=status:active
X-API-Key: {API_KEY}
```

#### **Date Range Filtering**
```http
# Filter by time periods
GET /api/v1/runs/?created_after=2025-10-01T00:00:00Z&created_before=2025-10-31T23:59:59Z
X-API-Key: {API_KEY}
```

#### **Searchable Fields Discovery**
```http
# Get available filterable fields for a process
GET /api/v1/processes/{process_id}/searchable-fields
X-API-Key: {API_KEY}
```

---

## **Version Management**

### **Current Version**

The project uses semantic versioning (MAJOR.MINOR.PATCH) with centralized version management.

**Version Location:** `pyproject.toml` (single source of truth)

### **Update Version**

Use the Python script to update version across all project files:

```bash
# Bump patch version (1.0.0 -> 1.0.1)
python scripts/update_version.py patch

# Bump minor version (1.0.0 -> 1.1.0)
python scripts/update_version.py minor

# Bump major version (1.0.0 -> 2.0.0)
python scripts/update_version.py major

# Set specific version
python scripts/update_version.py 2.1.0
```

**Updated Files:**
- `pyproject.toml` - Project metadata
- `.env.example` - Environment template
- `Dockerfile` - Container configuration

---

## **Support & Resources**

### **Documentation Links**
- **API Reference**: [Interactive Docs](http://localhost:8000/docs)

### **Development Resources**
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **SQLModel Guide**: https://sqlmodel.tiangolo.com/
- **Docker Best Practices**: https://docs.docker.com/develop/best-practices/

---

## **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
