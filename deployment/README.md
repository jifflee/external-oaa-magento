# Magento CE 2.4.7 — MVP Test Deployment

## Objective

Stand up a live Magento 2.4.7 store on AWS EC2 to validate that data can be extracted via REST and GraphQL APIs. This is a **disposable test environment** — stand it up, validate, tear it down.

## Architecture

```
              Internet
                 |
         [Public IP — changes on stop/start]
                 |
        +--------+--------+
        |   EC2 Instance  |    Default VPC · Public Subnet
        |   t3.medium     |
        |   4GB RAM       |
        |   30GB GP3      |
        |                 |
        |   Nginx 1.28    |
        |   PHP-FPM 8.2   |
        |   MariaDB 10.5  |
        |   Redis 6       |
        |   OpenSearch 2.x|
        |   Magento 2.4.7 |
        +-----------------+

Access: SSM Session Manager (no SSH required)
Idle:   Auto-stop after 10 min CPU < 5%
SG:     Ingress SSH from admin IP only
        Egress 443/80/53 (HTTPS, HTTP, DNS)
```

All services run locally on a single EC2 — no managed services, no RDS, no ElastiCache.

## Current State

| Resource | Count | Notes |
|----------|-------|-------|
| Customers | 10 | 5 General, 3 Wholesale, 2 Retailer |
| Products | 12 | Across 6 categories (Laptops, Phones, Mens, Womens) |
| Orders | 10 | One per customer |
| Categories | 7 | 2 top-level + 4 subcategories + Default |
| Customer Groups | 4 | NOT LOGGED IN, General, Wholesale, Retailer |
| REST Routes | 322 | Across 25+ resource groups |
| Modules | 358 | All CE modules |

**Instance:** `i-028422b8abdd9f6a4` (us-east-2)
**Admin:** `http://<public_ip>/admin` — admin / Admin123!@#
**Customer password:** Test1234!@#

## Files

| File | Purpose |
|------|---------|
| `main.tf` | Terraform: EC2, SG, IAM role (SSM), CloudWatch idle alarm |
| `terraform.tfvars` | Variables: key pair, IP, Magento repo keys |
| `setup-magento.sh` | All-in-one install: MariaDB, PHP, Nginx, Redis, OpenSearch, Magento |
| `seed-sample-data.sh` | Creates categories, products, and customers via REST API |
| `create-orders.sh` | Creates orders for all customers via REST API |
| `test-endpoints.sh` | Validates all REST and GraphQL endpoints |
| `activate.sh` | AWS SSO auth + SSL CA bundle for corporate proxy |
| `finish-magento-install.sh` | Standalone Magento setup:install (if needed separately) |

## Prerequisites

- AWS SSO access (profile: `magento-mvp`, account: `679626270023`)
- Terraform >= 1.5
- Magento Marketplace keys → [repo.magento.com](https://commercemarketplace.adobe.com/customer/accessKeys/)

## Deployment (~20 min)

### 1. Authenticate

```bash
source activate.sh
```

### 2. Provision infrastructure

```bash
terraform init
terraform apply
```

### 3. Disable idle alarm during setup

```bash
aws cloudwatch disable-alarm-actions --alarm-names "magento-mvp-idle-stop" \
  --profile magento-mvp --region us-east-2
```

### 4. Upload and run setup script via SSM

```bash
INSTANCE_ID=$(terraform output -raw magento_instance_id)

# Upload scripts to S3
aws s3 cp setup-magento.sh s3://magento-mvp-deploy-679626270023/ --profile magento-mvp --region us-east-2
aws s3 cp seed-sample-data.sh s3://magento-mvp-deploy-679626270023/ --profile magento-mvp --region us-east-2
aws s3 cp create-orders.sh s3://magento-mvp-deploy-679626270023/ --profile magento-mvp --region us-east-2

# Run Magento install (~15-20 min)
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --timeout-seconds 1800 \
  --parameters '{"commands":["aws s3 cp s3://magento-mvp-deploy-679626270023/setup-magento.sh /tmp/","bash /tmp/setup-magento.sh <public_key> <private_key> 2>&1 | tee /var/log/magento-setup.log"]}' \
  --profile magento-mvp --region us-east-2

# Seed sample data
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --timeout-seconds 300 \
  --parameters '{"commands":["aws s3 cp s3://magento-mvp-deploy-679626270023/seed-sample-data.sh /tmp/","bash /tmp/seed-sample-data.sh 2>&1"]}' \
  --profile magento-mvp --region us-east-2

# Create orders
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --timeout-seconds 300 \
  --parameters '{"commands":["aws s3 cp s3://magento-mvp-deploy-679626270023/create-orders.sh /tmp/","bash /tmp/create-orders.sh 2>&1"]}' \
  --profile magento-mvp --region us-east-2
```

### 5. Re-enable idle alarm

```bash
aws cloudwatch enable-alarm-actions --alarm-names "magento-mvp-idle-stop" \
  --profile magento-mvp --region us-east-2
```

### 6. Update base URL after IP change

If the instance was stopped and restarted (new public IP):

```bash
aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["export HOME=/root && export COMPOSER_ALLOW_SUPERUSER=1 && cd /var/www/magento && PUBLIC_IP=$(curl -s -H \"X-aws-ec2-metadata-token: $(curl -s -X PUT http://169.254.169.254/latest/api/token -H X-aws-ec2-metadata-token-ttl-seconds:60)\" http://169.254.169.254/latest/meta-data/public-ipv4) && php bin/magento config:set web/unsecure/base_url http://$PUBLIC_IP/ && php bin/magento cache:flush && echo Base URL: http://$PUBLIC_IP/"]}' \
  --profile magento-mvp --region us-east-2
```

## Available REST API Endpoints (CE)

### Working Endpoints (tested)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/rest/V1/integration/admin/token` | POST | None | Get admin JWT token |
| `/rest/V1/store/websites` | GET | Admin | List store websites |
| `/rest/V1/store/storeGroups` | GET | Admin | List store groups |
| `/rest/V1/store/storeViews` | GET | Admin | List store views |
| `/rest/V1/modules` | GET | Admin | List installed modules (358) |
| `/rest/V1/customers/search` | GET | Admin | Search customers (10 seeded) |
| `/rest/V1/customerGroups/search` | GET | Admin | List customer groups (4) |
| `/rest/V1/products` | GET | Admin | Search products (12 seeded) |
| `/rest/V1/categories` | GET | Admin | Category tree (7 categories) |
| `/rest/V1/orders` | GET | Admin | Search orders (10 seeded) |
| `/rest/V1/cmsPage/search` | GET | Admin | CMS pages (4 default) |
| `/rest/V1/inventory/sources` | GET | Admin | Inventory sources (1 default) |

### Top Route Groups (322 total routes)

| Resource | Routes | Examples |
|----------|--------|----------|
| products | 56 | CRUD, attributes, media, links, options |
| carts | 44 | Cart management, items, shipping, payment |
| inventory | 31 | Sources, stocks, reservations |
| guest-carts | 22 | Guest checkout flow |
| customers | 21 | CRUD, search, addresses, groups |
| orders | 12 | Search, comments, invoices, shipments |
| categories | 10 | Tree, products, assignments |

### Full schema available at:
```
GET /rest/all/schema?services=all   (Swagger/OpenAPI JSON)
```

## Available GraphQL Queries (CE)

| Query | Auth | Description |
|-------|------|-------------|
| `storeConfig` | None | Store name, URL, currency, locale, timezone |
| `products(search, filters)` | None | Product catalog with prices, categories |
| `categories(filters)` | None | Category tree with product counts |
| `cmsPage(identifier)` | None | CMS page content by identifier |
| `customer` | Customer token | Authenticated customer profile |
| `cart` | Customer token | Customer cart details |

### Example GraphQL Queries

```bash
# Store config (no auth)
curl -s -X POST http://<ip>/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ storeConfig { store_name base_url base_currency_code locale } }"}'

# Products (no auth)
curl -s -X POST http://<ip>/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ products(search: \"\", pageSize: 5) { total_count items { sku name price_range { minimum_price { regular_price { value currency } } } } } }"}'

# Categories (no auth)
curl -s -X POST http://<ip>/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ categories { total_count items { id name product_count children { id name } } } }"}'
```

## CE vs B2B Extension — What's Different

### B2B Endpoints (NOT available on CE — return 404)

| Endpoint | What It Does | Required For |
|----------|-------------|--------------|
| `/rest/V1/company/` | Company CRUD | Company management |
| `/rest/V1/company/role/` | B2B role definitions | Role-based access control |
| `/rest/V1/hierarchy/{companyId}` | Org chart tree | Company structure |
| `/rest/V1/team/{id}` | Team details | Team management |
| `/rest/V1/sharedCatalog/` | Shared catalogs | B2B pricing |
| `/rest/V1/negotiableQuote/` | Negotiable quotes | B2B quoting |
| `/rest/V1/purchaseorder/` | Purchase orders | B2B procurement |

### B2B GraphQL (NOT available on CE)

| Query | What It Does |
|-------|-------------|
| `company` | Company details, structure, admin |
| `company.structure.items` | Org hierarchy nodes |
| `customer.role` | Customer's B2B role |
| `customer.team` | Customer's team |
| `role.permissions` | Role permission tree (allow/deny per ACL resource) |

### How to Get B2B

B2B features require **Adobe Commerce** (formerly Magento Enterprise). To enable:

1. Get Adobe Commerce license keys from [Adobe Commerce Marketplace](https://commercemarketplace.adobe.com/customer/accessKeys/)
2. In `setup-magento.sh`, change `project-community-edition` to `project-enterprise-edition`
3. The `composer require magento/extension-b2b` command will succeed with Commerce keys
4. B2B modules (Company, SharedCatalog, NegotiableQuote, PurchaseOrder) will be installed and enabled automatically

**Current repo keys** (`f5ca292c...`) only have Community Edition access. The B2B install step is skipped gracefully.

## Sample Data Reference

### Customers

| Email | Name | Group | Password |
|-------|------|-------|----------|
| john.doe@example.com | John Doe | General | Test1234!@# |
| jane.smith@example.com | Jane Smith | General | Test1234!@# |
| bob.wilson@example.com | Bob Wilson | General | Test1234!@# |
| alice.johnson@example.com | Alice Johnson | General | Test1234!@# |
| charlie.brown@example.com | Charlie Brown | General | Test1234!@# |
| wholesale.buyer@acmecorp.com | David Miller | Wholesale | Test1234!@# |
| procurement@techstart.io | Sarah Chen | Wholesale | Test1234!@# |
| orders@bulkbuy.com | Michael Taylor | Wholesale | Test1234!@# |
| store.manager@retailhub.com | Emily Davis | Retailer | Test1234!@# |
| buyer@fashionoutlet.com | Robert Anderson | Retailer | Test1234!@# |

### Products

| SKU | Name | Price | Category |
|-----|------|-------|----------|
| LAPTOP-PRO-15 | ProBook 15 Laptop | $1,299.99 | Laptops |
| LAPTOP-AIR-13 | AirLight 13 Laptop | $899.99 | Laptops |
| LAPTOP-WORK-17 | WorkStation 17 Pro | $2,199.99 | Laptops |
| PHONE-ULTRA-X | Ultra X Smartphone | $999.99 | Phones |
| PHONE-LITE-S | Lite S Phone | $499.99 | Phones |
| PHONE-PRO-MAX | Pro Max Phone | $1,499.99 | Phones |
| SHIRT-M-BLUE | Blue Oxford Shirt - Men | $59.99 | Mens |
| PANTS-M-KHAKI | Khaki Chinos - Men | $79.99 | Mens |
| JACKET-M-BLK | Black Blazer - Men | $199.99 | Mens |
| DRESS-W-RED | Red Evening Dress | $149.99 | Womens |
| BLOUSE-W-WHT | White Silk Blouse | $89.99 | Womens |
| SKIRT-W-NVY | Navy Pencil Skirt | $69.99 | Womens |

### Categories

```
Default Category
├── Electronics
│   ├── Laptops (3 products)
│   └── Phones (3 products)
└── Clothing
    ├── Mens (3 products)
    └── Womens (3 products)
```

## Operational Notes

### Starting the instance after idle stop

```bash
source activate.sh
aws ec2 start-instances --instance-ids i-028422b8abdd9f6a4 \
  --profile magento-mvp --region us-east-2
# Wait ~60s, then update base URL (see step 6 above)
```

### Key fixes applied during setup

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `mysql-server` not found | AL2023 uses MariaDB | Changed to `mariadb105-server` |
| PHP config path wrong | AL2023 uses `/etc/php.d/` | Fixed from `/etc/php.ini.d/` |
| Composer HOME not set | SSM sessions don't set HOME | Added `export HOME=/root` |
| Composer security block | Magento 2.4.7 advisory PKSA-db8d-773v-rd1n | `composer config --global audit.block-insecure false` |
| Project files not deployed | Composer plugins disabled for root | Added `export COMPOSER_ALLOW_SUPERUSER=1` |
| SSH/SCP timeout | Corporate network blocks port 22 | Switched to S3 + SSM send-command |
| Products not orderable | Not assigned to website | Added website assignment step |
| B2B extension unavailable | Requires Adobe Commerce keys | Graceful skip, CE-only |

## On-Prem Instance Validation & Extraction

Scripts in `test/` validate a target Adobe Commerce instance and extract B2B data. Both are standalone bash scripts requiring only `curl` and `jq` — no Python needed.

### Prerequisites

- Network access to the target Magento instance
- B2B company admin credentials (email + password)
- Magento admin credentials (username + password)
- **Bash scripts** (macOS/Linux): `curl` and `jq`
- **Python scripts** (Windows/macOS/Linux): Python 3.9+ and `requests` (`pip install requests`)

### Credentials

All scripts accept the same env vars (or prompt interactively):

```bash
export MAGENTO_URL=https://magento.customer.com
export COMPANY_ADMIN_EMAIL=admin@company.com
export COMPANY_ADMIN_PASSWORD=secret
export MAGENTO_ADMIN_USER=admin
export MAGENTO_ADMIN_PASS=secret
```

### Step 1: Validate the instance

```bash
cd deployment/test

# Bash (macOS/Linux)
./validate-instance.sh

# Python (Windows/macOS/Linux)
python validate_instance.py
```

Runs 5 fail-fast stages:

| Stage | What it checks | Fails on |
|-------|---------------|----------|
| 1. Connectivity | `GET /rest/V1/store/storeConfigs` returns JSON | Timeout, non-200, invalid JSON |
| 2. Authentication | Customer token for the B2B company admin | 401, bad credentials |
| 3. B2B Module | REST `/company/role` + GraphQL `{ company { name } }` | 404, schema error (B2B not installed) |
| 4. GraphQL Extraction | Full `VezaExtraction` query (same as connector) | GraphQL errors, empty structure |
| 5. REST Permissions | `GET /rest/V1/company/role` with ACL details | Warns but doesn't fail (supplementary) |

Prints a color-coded summary at the end. All 5 stages must pass before running extraction.

### Step 2: Extract B2B data (50-record sample)

```bash
# Bash (macOS/Linux)
./run-extraction.sh

# Python (Windows/macOS/Linux)
python run_extraction.py
```

Pulls B2B data directly via curl with a 50-record limit per entity type. Saves each entity as a separate JSON file in a timestamped output folder.

**Output folder:** `deployment/test/output/YYYYMMDD_HHMM_B2B_Extraction/`

| File | Contents |
|------|----------|
| `company.json` | Company metadata: id, name, legal_name, email, company_admin |
| `users.json` | Up to 50 users with email, name, job_title, status, role, team |
| `teams.json` | Up to 50 teams with id, name, description, hierarchy position |
| `structure.json` | Up to 50 hierarchy nodes (id → parent_id → type) |
| `roles.json` | Up to 50 roles (raw REST response with full permission arrays) |
| `permissions.json` | Derived: per-role allow/deny resource lists |
| `extraction_metadata.json` | Timestamp, store URL, entity counts, file manifest |

**Example output:**

```
deployment/test/output/20260312_1430_B2B_Extraction/
├── company.json               (1 company)
├── users.json                 (12 users, capped at 50)
├── teams.json                 (3 teams)
├── structure.json             (15 hierarchy nodes)
├── roles.json                 (4 roles with permissions)
├── permissions.json           (4 roles → allow/deny lists)
└── extraction_metadata.json   (run metadata)
```

### Files

| File | Purpose |
|------|---------|
| `test/validate-instance.sh` | 5-stage instance validation — bash (macOS/Linux) |
| `test/validate_instance.py` | 5-stage instance validation — Python (cross-platform) |
| `test/run-extraction.sh` | 50-record B2B extraction — bash (macOS/Linux) |
| `test/run_extraction.py` | 50-record B2B extraction — Python (cross-platform) |

## Teardown

```bash
source activate.sh
terraform destroy
# Also clean up S3 bucket:
aws s3 rm s3://magento-mvp-deploy-679626270023/ --recursive --profile magento-mvp --region us-east-2
```

## Cost

Instance runs ~$0.04/hr (t3.medium). With 10-min idle auto-stop, cost is minimal. Estimated <$5 per test session.
