# Magento On-Prem REST Connector

Extracts B2B authorization data from a self-hosted Adobe Commerce (Magento) instance via the REST API and pushes it to Veza as an OAA `CustomApplication`.

Use this connector when GraphQL is disabled or unavailable. If GraphQL is available, prefer `connectors/on-prem-graphql/` for complete user-role resolution.

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

python run.py --dry-run                     # Extract and save JSON
python run.py --push                        # Extract and push to Veza
python run.py --push --strategy csv_supplement  # Use CSV for user-role mapping
python run.py --debug                       # Verbose output
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAGENTO_STORE_URL` | Yes | -- | Base URL of the Magento store |
| `MAGENTO_USERNAME` | Yes | -- | Company admin email |
| `MAGENTO_PASSWORD` | Yes | -- | Company admin password |
| `VEZA_URL` | Push only | -- | Veza tenant URL |
| `VEZA_API_KEY` | Push only | -- | Veza API key |
| `PROVIDER_NAME` | No | `Magento_OnPrem_REST` | Provider name in Veza |
| `PROVIDER_PREFIX` | No | _(empty)_ | Prefix for provider name |
| `DRY_RUN` | No | `true` | Extract only, no push |
| `SAVE_JSON` | No | `true` | Save OAA payload JSON |
| `DEBUG` | No | `false` | Verbose output |
| `USER_ROLE_STRATEGY` | No | `default_role` | How to handle the user-role gap |
| `USER_ROLE_MAPPING_PATH` | No | `./data/user_role_mapping.csv` | CSV path for `csv_supplement` strategy |

## Pipeline

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate | `POST /rest/V1/integration/customer/token` |
| 2 | Get current user | `GET /rest/V1/customers/me` |
| 3 | Get company details | `GET /rest/V1/company/{id}` |
| 4 | Get roles + permissions | `GET /rest/V1/company/role?company_id=X` |
| 5 | Get hierarchy | `GET /rest/V1/hierarchy/{companyId}` |
| 6 | Get team details | `GET /rest/V1/team/{id}` x N |
| 7 | Extract entities | Parse responses into normalized objects |
| 8 | User-role gap handling | Apply configured strategy |
| 9 | Build OAA application | Map entities to CustomApplication |
| 10 | Build relationships | Wire OAA relationships |
| 11 | Save JSON / Push | Output or push via shared `execute_veza_push()` |

## User-Role Gap

The REST API does not expose which role is assigned to each user. Four strategies are available:

| Strategy | Config Value | Behavior |
|----------|-------------|----------|
| Default Role | `default_role` | Assigns "Default User" role to non-admin users |
| CSV Supplement | `csv_supplement` | Reads user-role mapping from CSV file |
| All Roles | `all_roles` | Creates roles without user-role links |
| Skip | `skip` | Omits all user-role relationships |

**Recommendation:** Use `csv_supplement` when accuracy matters. Use `default_role` as a starting point.

### CSV Format

```csv
email,role_name
user1@acme.com,Default User
admin@acme.com,Company Administrator
```

## Known Limitations

- Only the authenticated user has a full profile; others appear as `customer_{id}@unknown`
- Reports-to relationships are incomplete (email unavailable for non-auth users)
- 5-7+ API calls per extraction vs 1-2 for GraphQL

## Project Structure

```
on-prem-rest/
  run.py                          Entry point
  requirements.txt                Dependencies (includes shared library)
  .env.template                   Configuration template
  config/
    settings.py                   Defaults, provider name, role strategy
  core/
    orchestrator.py               Pipeline coordination (11 steps)
    magento_client.py             REST API client
    entity_extractor.py           Parse REST responses into entities
    role_gap_handler.py           User-role gap workaround strategies
    application_builder.py        Build OAA CustomApplication
    relationship_builder.py       Wire OAA relationships
  tests/
    test_entity_extractor.py
    test_application_builder.py
    test_relationship_builder.py
    test_role_gap_handler.py
    test_orchestrator.py
```
