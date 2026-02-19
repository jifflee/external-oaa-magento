# Commerce Cloud GraphQL Connector

Extracts B2B authorization data from Adobe Commerce Cloud via the GraphQL API and pushes it to Veza as an OAA `CustomApplication`.

This connector authenticates via **Adobe IMS OAuth** (client_credentials grant) instead of Magento customer tokens. Use this for Commerce Cloud environments (`.magentosite.cloud`).

## Prerequisites

- Python 3.9+
- Adobe Commerce Cloud with B2B module enabled
- Adobe IMS OAuth credentials (client ID + client secret)
- Veza tenant URL and API key (push mode only)
- Shared library installed: `pip install -e ../../shared`

### Adobe IMS Setup

Commerce Cloud uses Adobe Identity Management System (IMS) for API authentication. You need OAuth client credentials configured in the Adobe Developer Console with scopes that include access to the Commerce Cloud project.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your credentials

python run.py --dry-run    # Extract and save JSON
python run.py --push       # Extract and push to Veza
python run.py --no-rest    # Skip REST role supplement
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAGENTO_STORE_URL` | Yes | -- | Commerce Cloud store URL (e.g., `https://project-env.us-4.magentosite.cloud`) |
| `ADOBE_IMS_CLIENT_ID` | Yes | -- | Adobe IMS OAuth client ID |
| `ADOBE_IMS_CLIENT_SECRET` | Yes | -- | Adobe IMS OAuth client secret |
| `ADOBE_IMS_SCOPES` | No | `openid,AdobeID,additional_info.projectedProductContext` | IMS OAuth scopes |
| `VEZA_URL` | Push only | -- | Veza tenant URL |
| `VEZA_API_KEY` | Push only | -- | Veza API key |
| `PROVIDER_NAME` | No | `Commerce_Cloud_GraphQL` | Provider name in Veza |
| `PROVIDER_PREFIX` | No | _(empty)_ | Prefix for provider name |
| `DRY_RUN` | No | `true` | Extract only, no push |
| `SAVE_JSON` | No | `true` | Save OAA payload JSON |
| `DEBUG` | No | `false` | Verbose output |
| `USE_REST_ROLE_SUPPLEMENT` | No | `true` | Fetch per-role ACL permissions via REST |

## Pipeline

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate via Adobe IMS | `POST https://ims-na1.adobelogin.com/ims/token/v3` (client_credentials) |
| 2 | GraphQL extraction | `POST /graphql` (single `VezaExtraction` query) |
| 3 | REST role supplement (optional) | `GET /rest/V1/company/role?company_id=X` |
| 4 | Extract entities | Parse GraphQL response |
| 5 | Build OAA application | Map entities to CustomApplication |
| 6 | Build relationships | Wire OAA relationships |
| 7 | Save JSON / Push to Veza | Output or push via shared `execute_veza_push()` |

### Differences from On-Prem GraphQL Connector

| Feature | Commerce Cloud | On-Prem |
|---------|---------------|---------|
| Authentication | Adobe IMS OAuth (client_credentials) | Magento customer token (email/password) |
| Store URL format | `*.magentosite.cloud` | Custom domain or IP |
| Credentials | IMS client ID + secret | Email + password |
| Pipeline | Identical after auth step | Identical after auth step |

## Project Structure

```
cloud-graphql/
  run.py                          Entry point
  requirements.txt                Dependencies (includes shared library)
  .env.template                   Configuration template
  config/
    settings.py                   Defaults and provider name
  core/
    orchestrator.py               Pipeline coordination (7 steps)
    ims_auth.py                   Adobe IMS OAuth token acquisition
    magento_client.py             Cloud GraphQL + REST client
    graphql_queries.py            VezaExtraction query definition
    entity_extractor.py           Parse GraphQL response into entities
    application_builder.py        Build OAA CustomApplication
    relationship_builder.py       Wire OAA relationships
  tests/
    test_entity_extractor.py
    test_application_builder.py
    test_orchestrator.py
    test_ims_auth.py
```
