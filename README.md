# Magento B2B Authorization Data Extractor

Extracts B2B authorization data (companies, users, roles, permissions, teams, hierarchy) from Adobe Commerce / Magento stores via GraphQL and outputs structured JSON in Veza OAA format.

## Quick Start

```bash
# 1. Install the shared library
cd shared && pip install -e .

# 2. Install connector dependencies
cd ../connectors/on-prem-graphql
pip install -r requirements.txt

# 3. Configure credentials
cp .env.template .env
# Edit .env with your Magento store URL and company admin credentials

# 4. Run extraction
python run.py
```

## Validation

Before running the extractor, verify the target Magento instance has B2B support. Copy `validation.sh` to the Magento server and run it from the Magento root directory:

```bash
bash validation.sh                    # run from Magento root
bash validation.sh /var/www/magento   # specify Magento root path
```

This checks edition, hosting type, B2B module status, GraphQL availability, and outputs a readiness summary.

## Prerequisites

- Python 3.9+
- Adobe Commerce with B2B module enabled
- A Magento customer account that is a B2B company admin

Magento Open Source (CE) does not include B2B endpoints. This extractor requires **Adobe Commerce** with the B2B extension.

## How It Works

The extractor authenticates as a B2B company admin, runs a single GraphQL query to retrieve the complete company structure, then optionally supplements with a REST call for per-role ACL permissions. The extracted data is saved as JSON.

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate | `POST /rest/V1/integration/customer/token` |
| 2 | GraphQL extraction | `POST /graphql` (single query) |
| 3 | REST role supplement (optional) | `GET /rest/V1/company/role` |
| 4-6 | Parse entities, build OAA structure, save JSON | Local processing |

## What It Extracts

| Magento Entity | Description |
|----------------|-------------|
| Company | B2B organizational entity (name, legal name, admin) |
| Users | Company members (email, name, job title, status, active/inactive) |
| Teams | Groups within a company |
| Roles | Named permission sets (e.g., "Buyer", "Manager") |
| ACL Permissions | 34 granular B2B permissions across sales, quotes, purchase orders, company management |
| Hierarchy | Reporting structure (who reports to whom) |

### Relationships Captured

- User -> Company (membership)
- User -> Team (membership)
- User -> Role (assignment)
- Role -> Permission (ACL allow/deny)
- Team -> Company (nesting)
- User -> User (reports-to)

## Output

Each run creates a timestamped folder with the extracted data:

```
output/YYYYMMDD_HHMM_Magento_OnPrem_GraphQL/
  oaa_payload.json           Extracted authorization data (OAA format)
  extraction_results.json    Run metadata, entity counts, errors
```

## Configuration

All settings are loaded from `.env`. See `.env.template` for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `MAGENTO_STORE_URL` | Yes | Base URL of the Magento store |
| `MAGENTO_USERNAME` | Yes | Company admin email |
| `MAGENTO_PASSWORD` | Yes | Company admin password |

## Repository Structure

```
magento/
├── validation.sh                    B2B capability check (run on Magento server)
├── connectors/on-prem-graphql/      GraphQL extractor
│   ├── run.py                       Entry point
│   ├── .env.template                Configuration template
│   ├── config/                      Default settings
│   ├── core/                        Extraction pipeline modules
│   │   ├── orchestrator.py          Pipeline coordination (7 steps)
│   │   ├── magento_client.py        REST auth + GraphQL execution
│   │   ├── graphql_queries.py       GraphQL query definition
│   │   ├── entity_extractor.py      Parse response into entities
│   │   ├── application_builder.py   Build OAA structure
│   │   └── relationship_builder.py  Wire entity relationships
│   └── tests/                       Unit tests
├── shared/                          Common library (magento-oaa-shared)
│   ├── magento_oaa_shared/          OAA builder, permissions, output management
│   └── tests/                       Unit tests
└── README.md
```

## Running Tests

```bash
# Shared library tests
cd shared && pytest tests/

# Connector tests
cd connectors/on-prem-graphql && pytest tests/
```

## License

See [LICENSE](LICENSE).
