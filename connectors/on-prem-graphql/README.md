# Magento B2B GraphQL Extractor

Extracts B2B authorization data from Adobe Commerce (Magento) via GraphQL and outputs structured JSON in Veza OAA format.

Retrieves the complete company structure (users, teams, roles, hierarchy) in 1-2 API calls with full user-role resolution.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your Magento credentials

python run.py               # Extract and save JSON
python run.py --debug        # Verbose output
python run.py --no-rest      # Skip REST role supplement
```

## Prerequisites

- Python 3.9+
- Adobe Commerce with B2B module enabled
- A B2B company admin account (email/password)
- Shared library installed: `pip install -e ../../shared`

Run `validation.sh` on the Magento server first to confirm B2B is available (see root README).

## Configuration

All settings are loaded from `.env` (default: `./.env`). Override with `--env /path/to/file.env`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAGENTO_STORE_URL` | Yes | -- | Base URL of the Magento store |
| `MAGENTO_USERNAME` | Yes | -- | Company admin email |
| `MAGENTO_PASSWORD` | Yes | -- | Company admin password |
| `SAVE_JSON` | No | `true` | Save extracted data as JSON |
| `DEBUG` | No | `false` | Verbose output |
| `USE_REST_ROLE_SUPPLEMENT` | No | `true` | Fetch per-role ACL permissions via REST |
| `OUTPUT_DIR` | No | `./output` | Output directory |
| `OUTPUT_RETENTION_DAYS` | No | `30` | Auto-cleanup old output folders |

## Pipeline

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate | `POST /rest/V1/integration/customer/token` |
| 2 | GraphQL extraction | `POST /graphql` (single `VezaExtraction` query) |
| 3 | REST role supplement (optional) | `GET /rest/V1/company/role?company_id=X` |
| 4 | Extract entities | Parse GraphQL response into users, teams, roles, hierarchy |
| 5 | Build OAA structure | Map entities to OAA CustomApplication format |
| 6 | Build relationships | Wire user-group, user-role, role-permission links |
| 7 | Save JSON | Write extracted data to output directory |

### REST Role Supplement

GraphQL returns role name and ID per user but not the per-role ACL permission tree. The REST supplement calls `GET /rest/V1/company/role` to fetch explicit allow/deny permissions for each role. Only `allow` entries are included in the output. Disable with `USE_REST_ROLE_SUPPLEMENT=false` or `--no-rest`.

## Output

Each run creates a timestamped folder under `OUTPUT_DIR`:

```
output/YYYYMMDD_HHMM_Magento_OnPrem_GraphQL/
  oaa_payload.json           Extracted authorization data (OAA format)
  extraction_results.json    Run metadata, entity counts, errors
```

## Project Structure

```
on-prem-graphql/
  run.py                          Entry point
  requirements.txt                Dependencies (includes shared library)
  .env.template                   Configuration template
  config/
    settings.py                   Defaults
  core/
    orchestrator.py               Pipeline coordination (7 steps)
    magento_client.py             REST auth + GraphQL execution
    graphql_queries.py            GraphQL query definition
    entity_extractor.py           Parse GraphQL response into entities
    application_builder.py        Build OAA structure
    relationship_builder.py       Wire entity relationships
  tests/
    test_entity_extractor.py
    test_application_builder.py
    test_relationship_builder.py
    test_orchestrator.py
```
