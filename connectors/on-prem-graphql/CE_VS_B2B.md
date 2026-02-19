# Magento CE vs Adobe Commerce (B2B) — What You Can and Can't Do

## The Two Versions of Magento

There are two versions of Magento, and the difference matters a lot for what data we can extract:

| | Magento Open Source (CE) | Adobe Commerce (AC) |
|---|---|---|
| **Cost** | Free, open source | Paid license from Adobe |
| **Also called** | Community Edition, Magento CE | Magento Enterprise, Magento EE, Adobe Commerce |
| **Target** | Small/mid stores, developers | Mid/large B2B enterprises |
| **B2B features** | None | Companies, teams, roles, shared catalogs, purchase orders, negotiable quotes |
| **What we have** | This is what's on the EC2 instance | Requires Adobe Commerce marketplace keys |

**Bottom line:** CE is a regular online store. Adobe Commerce adds the entire B2B organizational layer on top.

## What CE Can Do

CE gives you everything needed to run a store. Our extraction script (`extract_ce.py`) can pull all of this:

| Data | GraphQL Query | Auth Required | What You Get |
|------|--------------|---------------|--------------|
| Store config | `storeConfig` | No | Store name, locale, currency, timezone |
| Products | `products(search: "")` | No | Full catalog — SKU, name, price, stock status, categories |
| Categories | `categories` | No | Category tree with hierarchy and product counts |
| CMS pages | `cmsPage(identifier: "home")` | No | Homepage and other CMS content |
| Customer profile | `customer` | Customer token | Email, name, addresses of the logged-in customer |
| Orders | `customer { orders }` | Customer token | Order history — items, totals, shipping, status |

This data is real and useful, but it's all **store data**, not **authorization data**.

## What Only Adobe Commerce Can Do

This is the data Veza actually needs, and **none of it exists on CE**:

| Data | What It Is | Why Veza Needs It |
|------|-----------|-------------------|
| **Companies** | B2B organizational entities (like tenants) | Top-level grouping for users |
| **Company structure** | Hierarchical tree of teams and users | Shows who reports to whom |
| **Teams** | Groups within a company | Maps to Veza groups |
| **Roles** | Named permission sets (e.g., "Buyer", "Manager") | Defines what users can do |
| **ACL permissions** | 34 granular permissions across 5 namespaces | The actual allow/deny rules |
| **Shared catalogs** | Product catalogs restricted by company | Controls what companies can see/buy |
| **Negotiable quotes** | B2B price negotiation workflows | Business process data |
| **Purchase orders** | Approval-based ordering workflows | Business process data |
| **Purchase order rules** | Auto-approval rules (amount thresholds, etc.) | Authorization rules |

If you try to query `company` or `companyRoles` on CE, you'll get a GraphQL error — those types simply don't exist in the schema.

## Why This Matters for Veza

Veza maps **who can do what** in an application. For Magento B2B, that means:

- **Users** (company members) mapped to **Roles** (permission sets)
- **Roles** grant/deny **34 ACL permissions** (place orders, view quotes, manage users, etc.)
- **Teams** group users within a company hierarchy

**CE has users but no roles, no permissions, no company structure.** A CE customer can browse products and place orders, but there's no authorization model to map.

The extraction script proves the data pipeline works:
1. Authentication works (customer token via REST)
2. GraphQL queries execute and return real data
3. Pagination, error handling, and output formatting all work
4. When B2B is available, we add the B2B queries — the plumbing is proven

## What You Need for B2B

To get the B2B data Veza needs:

1. **Adobe Commerce marketplace keys** — Get these from https://marketplace.magento.com (requires an Adobe Commerce license or trial)
2. **Install B2B extension:**
   ```bash
   composer require magento/extension-b2b
   bin/magento setup:upgrade
   bin/magento setup:di:compile
   ```
3. **Enable B2B features** in Admin > Stores > Configuration > General > B2B Features
4. **Create test data** — At least one company with teams, roles, and users

The current EC2 instance uses Community Edition keys (`f5ca292c...`). B2B endpoints return 404 because the extension isn't installed.

## Authentication: Two Types

Both CE and Adobe Commerce support the same two authentication methods:

### Customer Token
```
POST /rest/V1/integration/customer/token
Body: {"username": "customer@email.com", "password": "..."}
```
- Authenticates as a specific customer
- Can query: own profile, own orders, products, categories, CMS
- On Adobe Commerce: can also query company data **if the customer belongs to a company**
- This is what the B2B connector uses — a company admin's token sees the full company structure

### Admin Token
```
POST /rest/V1/integration/admin/token
Body: {"username": "admin", "password": "..."}
```
- Authenticates as a Magento admin user
- Can query: everything a customer can, plus admin-only REST endpoints
- GraphQL support is more limited for admin tokens (some queries are customer-only)
- Useful for REST-based extraction but not the primary path for the GraphQL connector

The extraction script supports both (`--admin` flag).

## This Extraction Script

`extract_ce.py` does one thing: pull all available CE data and save it as JSON.

**What it does:**
1. Authenticates (customer or admin token)
2. Runs 6 queries: store config, products, categories, CMS page, customer profile, orders
3. Saves raw per-query JSON files + a combined `ce_payload.json` + an `extraction_summary.json`

**What it outputs:**
```
output/YYYYMMDD_HHMM_ce_extraction/
├── raw/
│   ├── store_config.json
│   ├── products_page_1.json
│   ├── categories.json
│   ├── cms_home.json
│   ├── customer.json
│   └── orders_page_1.json
├── ce_payload.json              Everything combined in one file
└── extraction_summary.json      Timing, counts, errors
```

**What it does NOT do:**
- No OAA/Veza integration — no `oaaclient`, no push
- No B2B queries — those would fail on CE
- No modification of the existing connector code

**How to extend when B2B is available:**
The existing connector (`run.py` + `core/`) already handles B2B extraction and OAA mapping. Once the B2B extension is installed, use `run.py --dry-run` instead of this script. This script is specifically for validating the pipeline on CE.
