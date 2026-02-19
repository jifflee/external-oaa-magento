# Magento On-Prem GraphQL Connector

Extracts B2B authorization data from a self-hosted Adobe Commerce (Magento) instance via the GraphQL API and pushes it to Veza as an OAA `CustomApplication`.

This is the **recommended connector** for on-prem deployments. It retrieves the complete company structure (users, teams, roles, hierarchy) in 1-2 API calls with full user-role resolution.

## Prerequisites

- Python 3.9+
- Adobe Commerce with B2B module enabled
- A B2B company admin account (email/password)
- Veza tenant URL and API key (push mode only)
- Shared library installed: `pip install -e ../../shared`

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your credentials

python run.py --dry-run    # Extract and save JSON
python run.py --push       # Extract and push to Veza
python run.py --debug      # Verbose output
python run.py --no-rest    # Skip REST role supplement
```

## Configuration

All settings are loaded from `.env` (default: `./.env`). Override with `--env /path/to/file.env`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAGENTO_STORE_URL` | Yes | -- | Base URL of the Magento store |
| `MAGENTO_USERNAME` | Yes | -- | Company admin email |
| `MAGENTO_PASSWORD` | Yes | -- | Company admin password |
| `VEZA_URL` | Push only | -- | Veza tenant URL |
| `VEZA_API_KEY` | Push only | -- | Veza API key |
| `PROVIDER_NAME` | No | `Magento_OnPrem_GraphQL` | Provider name in Veza |
| `PROVIDER_PREFIX` | No | _(empty)_ | Prefix for provider name |
| `DRY_RUN` | No | `true` | Extract only, no push |
| `SAVE_JSON` | No | `true` | Save OAA payload JSON |
| `DEBUG` | No | `false` | Verbose output |
| `USE_REST_ROLE_SUPPLEMENT` | No | `true` | Fetch per-role ACL permissions via REST |

## Pipeline

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate | `POST /rest/V1/integration/customer/token` |
| 2 | GraphQL extraction | `POST /graphql` (single `VezaExtraction` query) |
| 3 | REST role supplement (optional) | `GET /rest/V1/company/role?company_id=X` |
| 4 | Extract entities | Parse GraphQL response into users, teams, roles, hierarchy |
| 5 | Build OAA application | Map entities to CustomApplication |
| 6 | Build relationships | Wire user-group, user-role, role-permission links |
| 7 | Save JSON / Push to Veza | Output or push via shared `execute_veza_push()` |

### REST Role Supplement

GraphQL returns role name and ID per user but not the per-role ACL permission tree. The REST supplement calls `GET /rest/V1/company/role` to fetch explicit allow/deny permissions. Only `allow` entries become OAA permission grants. Disable with `USE_REST_ROLE_SUPPLEMENT=false` or `--no-rest`.

## Output

Each run creates a timestamped folder under `OUTPUT_DIR`:

```
output/YYYYMMDD_HHMM_Magento_OnPrem_GraphQL/
  oaa_payload.json           OAA CustomApplication payload
  extraction_results.json    Run metadata, entity counts, errors
```

## Differences from REST Connector

| Feature | GraphQL | REST |
|---------|---------|------|
| API calls per extraction | 1-2 | 5-7+ |
| User-role resolution | Complete (embedded in response) | Not available (gap strategy required) |
| User profiles | Full (email, name, status, job title) | Only authenticated user; others are `customer_{id}@unknown` |
| Reports-to relationships | Complete | Incomplete (email unavailable for non-auth users) |

## Project Structure

```
on-prem-graphql/
  run.py                          Entry point
  requirements.txt                Dependencies (includes shared library)
  .env.template                   Configuration template
  config/
    settings.py                   Defaults and provider name
  core/
    orchestrator.py               Pipeline coordination (7 steps)
    magento_client.py             REST auth + GraphQL execution
    graphql_queries.py            VezaExtraction query definition
    entity_extractor.py           Parse GraphQL response into entities
    application_builder.py        Build OAA CustomApplication
    relationship_builder.py       Wire OAA relationships
  tests/
    test_entity_extractor.py
    test_application_builder.py
    test_relationship_builder.py
    test_orchestrator.py
```
