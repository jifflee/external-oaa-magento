# Magento B2B Authorization Connectors for Veza

Extract B2B authorization data (users, roles, permissions, teams, company hierarchy) from Adobe Commerce / Magento stores and push it to [Veza](https://www.veza.com) as OAA CustomApplications.

## Which Connector Do I Use?

```
What type of Magento do you have?
│
├─ Self-Hosted / On-Prem (Adobe Commerce or Magento Open Source*)
│  ├─ GraphQL enabled?  →  connectors/on-prem-graphql/   (RECOMMENDED)
│  └─ GraphQL blocked?  →  connectors/on-prem-rest/
│
└─ Adobe Commerce Cloud (*.magentosite.cloud)
   ├─ GraphQL enabled?  →  connectors/cloud-graphql/     (RECOMMENDED)
   └─ GraphQL blocked?  →  connectors/cloud-rest/
```

\* Magento Open Source (CE) does not include B2B endpoints. Connectors require **Adobe Commerce** with the B2B extension.

### Connector Comparison

| Connector | Directory | Auth | API Calls | User-Role Resolution |
|-----------|-----------|------|-----------|---------------------|
| On-Prem GraphQL | `connectors/on-prem-graphql/` | Customer token | 1-2 | Complete |
| On-Prem REST | `connectors/on-prem-rest/` | Customer token | 5-7+ | Gap strategy required |
| Cloud GraphQL | `connectors/cloud-graphql/` | Adobe IMS OAuth | 1-2 | Complete |
| Cloud REST | `connectors/cloud-rest/` | Adobe IMS OAuth | 5-7+ | Gap strategy required |

GraphQL connectors are recommended. They retrieve the complete company structure in 1-2 API calls with full user-role resolution. REST connectors are a fallback when GraphQL is unavailable.

## Repository Structure

```
magento/
│
├── connectors/                  Active connectors — ready for development/testing
│   ├── on-prem-graphql/         Self-hosted, GraphQL (recommended)
│   └── on-prem-rest/            Self-hosted, REST (fallback)
│
├── backlog/                     Connectors not yet ready (missing prerequisites)
│   ├── cloud-graphql/           Needs Commerce Cloud env + IMS credentials
│   └── cloud-rest/              Needs Commerce Cloud env + IMS credentials
│
├── shared/                      Common library (magento-oaa-shared)
│                                VezaClient, permissions, push helper, base builder
│
├── deployment/                  AWS EC2 test environment
│                                Terraform + scripts for Magento CE 2.4.7
│
└── reference/                   Non-deployable reference material
    ├── odie-oaa/                Generic CSV-to-Veza connector (reference impl)
    ├── commerce-webapi/         Adobe Commerce REST/GraphQL API docs
    └── legacy/                  Superseded standalone connectors (archived)
        ├── graphql-connector/
        └── rest-connector/
```

## Quick Start

```bash
# 1. Install the shared library
cd shared && pip install -e .

# 2. Choose your connector (example: on-prem-graphql)
cd ../connectors/on-prem-graphql
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your Magento and Veza credentials

# 3. Dry run — extract and save JSON without pushing
python run.py --dry-run

# 4. Push to Veza
python run.py --push
```

## Data Model

All connectors produce the same Veza OAA structure:

| Magento Entity | OAA Type | Unique ID Format |
|----------------|----------|------------------|
| Company | `LocalGroup` (type: company) | `company_{id}` |
| Team | `LocalGroup` (type: team) | `team_{id}` |
| Customer (user) | `LocalUser` | email address |
| Role | `LocalRole` | `role_{company_id}_{role_id}` |
| ACL Resource | `CustomPermission` | resource ID (e.g., `Magento_Sales::place_order`) |

### Relationships

1. User -> Company (membership)
2. User -> Team (membership)
3. User -> Role (assignment)
4. Role -> Permission (ACL allow grants)
5. Team -> Company (nesting)
6. User -> User (reports-to, from hierarchy)

## Prerequisites

- Python 3.9+
- Adobe Commerce with B2B module enabled (CE does not include B2B endpoints)
- A Magento customer account that is a B2B company admin
- Veza tenant URL and API key (for push mode; not required for dry-run)

## Test Environment

A disposable Magento CE 2.4.7 test environment runs on AWS EC2 for API validation. See `deployment/README.md` for deployment instructions, seeded sample data, and the full list of 322 CE REST routes and GraphQL queries.

B2B endpoints require Adobe Commerce keys. The CE deployment validates standard REST/GraphQL functionality and documents which B2B-specific endpoints are unavailable.
