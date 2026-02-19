# Commerce Cloud REST Connector

Extracts B2B authorization data from Adobe Commerce Cloud via the REST API and pushes it to Veza as an OAA `CustomApplication`.

This connector authenticates via **Adobe IMS OAuth** (client_credentials grant) instead of Magento customer tokens. Use this for Commerce Cloud environments where GraphQL is disabled or unavailable. If GraphQL is available, prefer `connectors/cloud-graphql/`.

## Prerequisites

- Python 3.9+
- Adobe Commerce Cloud with B2B module enabled
- Adobe IMS OAuth credentials (client ID + client secret)
- Veza tenant URL and API key (push mode only)
- Shared library installed: `pip install -e ../../shared`

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your credentials

python run.py --dry-run                         # Extract and save JSON
python run.py --push                            # Extract and push to Veza
python run.py --push --strategy csv_supplement  # Use CSV for user-role mapping
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAGENTO_STORE_URL` | Yes | -- | Commerce Cloud store URL |
| `ADOBE_IMS_CLIENT_ID` | Yes | -- | Adobe IMS OAuth client ID |
| `ADOBE_IMS_CLIENT_SECRET` | Yes | -- | Adobe IMS OAuth client secret |
| `ADOBE_IMS_SCOPES` | No | `openid,AdobeID,additional_info.projectedProductContext` | IMS OAuth scopes |
| `VEZA_URL` | Push only | -- | Veza tenant URL |
| `VEZA_API_KEY` | Push only | -- | Veza API key |
| `PROVIDER_NAME` | No | `Commerce_Cloud_REST` | Provider name in Veza |
| `PROVIDER_PREFIX` | No | _(empty)_ | Prefix for provider name |
| `DRY_RUN` | No | `true` | Extract only, no push |
| `SAVE_JSON` | No | `true` | Save OAA payload JSON |
| `DEBUG` | No | `false` | Verbose output |
| `USER_ROLE_STRATEGY` | No | `default_role` | User-role gap strategy |
| `USER_ROLE_MAPPING_PATH` | No | `./data/user_role_mapping.csv` | CSV path for `csv_supplement` strategy |

## Pipeline

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate via Adobe IMS | `POST https://ims-na1.adobelogin.com/ims/token/v3` |
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

Same as the on-prem REST connector. The REST API does not expose user-role assignments. Four strategies available: `default_role`, `csv_supplement`, `all_roles`, `skip`. See `connectors/on-prem-rest/README.md` for details.

## Known Limitations

- Same REST limitations as the on-prem REST connector (incomplete user profiles, no user-role resolution)
- Adobe IMS token expires after ~24 hours; the client auto-refreshes

## Project Structure

```
cloud-rest/
  run.py                          Entry point
  requirements.txt                Dependencies (includes shared library)
  .env.template                   Configuration template
  config/
    settings.py                   Defaults and provider name
  core/
    orchestrator.py               Pipeline coordination (11 steps)
    ims_auth.py                   Adobe IMS OAuth token acquisition
    magento_client.py             Cloud REST API client
    entity_extractor.py           Parse REST responses into entities
    role_gap_handler.py           User-role gap workaround strategies
    application_builder.py        Build OAA CustomApplication
    relationship_builder.py       Wire OAA relationships
  tests/
    test_entity_extractor.py
    test_application_builder.py
    test_role_gap_handler.py
    test_orchestrator.py
    test_ims_auth.py
```
