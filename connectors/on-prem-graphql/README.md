# Magento B2B GraphQL Extractor

Extracts B2B authorization data from Adobe Commerce (Magento) via GraphQL and outputs structured JSON in Veza OAA format.

Retrieves the complete company structure (users, teams, roles, hierarchy) in 1-2 API calls with full user-role resolution.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your Magento credentials

python run.py               # Extract and save JSON
python run.py --debug       # Verbose output
python run.py --no-rest     # Skip REST role supplement
python run.py --ce-mode     # CE fallback (synthetic B2B from real CE customers)
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
| `CE_MODE` | No | `false` | CE fallback mode (synthetic B2B from real CE customers) |
| `MAGENTO_ADMIN_USERNAME` | CE mode | -- | Admin username for REST API access |
| `MAGENTO_ADMIN_PASSWORD` | CE mode | -- | Admin password for REST API access |

## Pipeline

| Step | Module | Action |
|------|--------|--------|
| 1 | `magento_client.py` | Authenticate via `POST /rest/V1/integration/customer/token` |
| 2 | `magento_client.py` | Execute GraphQL `VezaExtraction` query via `POST /graphql` |
| 3 | `magento_client.py` | (Optional) Fetch per-role ACL permissions via `GET /rest/V1/company/role` |
| 4 | `entity_extractor.py` | Parse GraphQL response into normalized users, teams, roles, hierarchy |
| 5 | `application_builder.py` | Map entities to OAA CustomApplication format |
| 6 | `relationship_builder.py` | Wire user-group, user-role, role-permission, reports-to links |
| 7 | `orchestrator.py` | Save OAA payload and run metadata as JSON |

### REST Role Supplement

GraphQL returns role name and ID per user but not the per-role ACL permission tree. The REST supplement calls `GET /rest/V1/company/role` to fetch explicit allow/deny permissions for each of the 34 B2B ACL resources. Only `allow` entries are included in the output. Disable with `USE_REST_ROLE_SUPPLEMENT=false` or `--no-rest`.

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
    settings.py                   Default settings
  core/
    orchestrator.py               Pipeline coordination (7 steps)
    magento_client.py             REST auth + GraphQL execution
    graphql_queries.py            GraphQL query definition
    entity_extractor.py           Parse GraphQL response into entities
    application_builder.py        Build OAA structure
    relationship_builder.py       Wire entity relationships
    ce_data_builder.py            CE fallback: synthetic B2B from real CE customers
  tests/
    test_entity_extractor.py      Entity parsing tests
    test_application_builder.py   OAA builder tests
    test_relationship_builder.py  Relationship wiring tests
    test_orchestrator.py          Config validation tests
```
