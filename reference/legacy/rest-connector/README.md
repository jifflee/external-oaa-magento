# Magento B2B REST Connector for Veza OAA

> **ARCHIVED:** This is the original standalone connector. It has been superseded by `connectors/on-prem-rest/` (on-prem) and `connectors/cloud-rest/` (cloud), which use the shared library (`shared/magento_oaa_shared`) and support both on-prem and Commerce Cloud authentication. New deployments should use the connectors in the `connectors/` directory.

## Overview

This connector extracts B2B authorization data from Adobe Commerce (Magento) via the REST API and pushes it to Veza as an OAA `CustomApplication`. It models company users, teams, roles, and ACL permissions so that Veza can answer access questions about who can do what within a Magento B2B organization.

**Use this connector when GraphQL is disabled, unavailable, or blocked in your environment.** If GraphQL is available, prefer the `graphql-connector` instead — it provides a complete user-role mapping that the REST API cannot supply. See [REST_GAP_ANALYSIS.md](REST_GAP_ANALYSIS.md) for a full description of the limitation and available workarounds.

---

## Prerequisites

- Python 3.9 or later
- A Magento Adobe Commerce instance with the B2B module enabled
- A Magento customer account that belongs to a B2B company (used for authentication)
- A Veza tenant URL and API key (not required for dry-run mode)
- Network access from the machine running this connector to both the Magento store URL and the Veza URL

---

## Installation

```bash
cd rest-connector
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your configuration values
```

---

## Configuration

All configuration is loaded from a `.env` file (default: `./.env`). The path to the `.env` file can be overridden at runtime with the `--env` flag.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MAGENTO_STORE_URL` | Yes | — | Base URL of the Magento store, e.g. `https://store.example.com` |
| `MAGENTO_USERNAME` | Yes | — | Email address of the Magento customer account used for authentication |
| `MAGENTO_PASSWORD` | Yes | — | Password for the Magento customer account |
| `VEZA_URL` | Push only | — | Base URL of your Veza tenant, e.g. `https://myorg.vezacloud.com` |
| `VEZA_API_KEY` | Push only | — | Veza API key with OAA write permissions |
| `PROVIDER_NAME` | No | `Magento_B2B` | Name of the OAA provider registered in Veza |
| `PROVIDER_PREFIX` | No | _(empty)_ | Optional prefix prepended to the provider name to disambiguate multiple instances |
| `DRY_RUN` | No | `true` | When `true`, extracts data and saves JSON but does not push to Veza |
| `SAVE_JSON` | No | `true` | When `true`, saves the OAA payload JSON to the output directory |
| `DEBUG` | No | `false` | When `true`, prints verbose diagnostic output |
| `OUTPUT_DIR` | No | `./output` | Directory where timestamped output folders are written |
| `OUTPUT_RETENTION_DAYS` | No | `30` | Number of days to retain output folders; set to `0` to disable cleanup |
| `USER_ROLE_STRATEGY` | No | `default_role` | Strategy for handling the REST user-role assignment gap. One of: `default_role`, `csv_supplement`, `all_roles`, `skip`. See [User-Role Gap Strategies](#user-role-gap-strategies) below. |
| `USER_ROLE_MAPPING_PATH` | No | `./data/user_role_mapping.csv` | Path to the CSV mapping file used when `USER_ROLE_STRATEGY=csv_supplement` |

`VEZA_URL` and `VEZA_API_KEY` are only required when `DRY_RUN=false` (i.e., when actually pushing data to Veza). They are not needed for dry-run extraction.

---

## Usage

```bash
# Extract data, save JSON to output/, but do not push to Veza
python run.py --dry-run

# Extract and push to Veza using the strategy set in .env
python run.py --push

# Extract and push using the CSV supplement strategy for user-role mapping
python run.py --push --strategy csv_supplement

# Extract and push with verbose debug output
python run.py --push --debug

# Load configuration from a non-default .env file
python run.py --push --env /path/to/production.env
```

### Command-Line Arguments

| Argument | Description |
|---|---|
| `--dry-run` | Forces dry-run mode regardless of `DRY_RUN` in `.env` |
| `--push` | Forces live push mode (overrides `DRY_RUN=true` in `.env`) |
| `--debug` | Enables debug output (overrides `DEBUG` in `.env`) |
| `--strategy` | Overrides `USER_ROLE_STRATEGY` from `.env`. Accepted values: `default_role`, `csv_supplement`, `all_roles`, `skip` |
| `--env` / `-e` | Path to `.env` file (default: `./.env`) |

---

## How It Works

The connector runs as an 11-step pipeline. Each step is logged to the console during execution.

### Step 1 — Authenticate

Makes a `POST /rest/V1/integration/customer/token` request with the configured username and password. The response is a JWT bearer token that is attached to all subsequent requests as an `Authorization: Bearer <token>` header.

### Step 2 — Get Current User

Makes a `GET /rest/V1/customers/me` request to retrieve the profile of the authenticated customer. The response contains `extension_attributes.company_attributes.company_id`, which is required for all subsequent company-scoped requests.

The connector aborts here if the authenticated user is not associated with a company.

### Step 3 — Get Company Details

Makes a `GET /rest/V1/company/{company_id}` request to retrieve the company record, including `company_name`, `legal_name`, `company_email`, and `super_user_id` (the company administrator's customer ID).

### Step 4 — Get Company Roles and Permissions

Makes a `GET /rest/V1/company/role` request filtered by `company_id`. Returns all roles defined for the company, each with an explicit list of ACL resource permissions tagged as `allow` or `deny`.

Only permissions with `"permission": "allow"` are applied in Veza.

### Step 5 — Get Hierarchy Tree

Makes a `GET /rest/V1/hierarchy/{company_id}` request to retrieve the company's organizational hierarchy as a nested tree of nodes. Each node contains:

- `entity_type`: `"customer"` or `"team"`
- `entity_id`: the customer ID or team ID
- `structure_id`: the node's position ID in the tree
- `structure_parent_id`: the parent node's position ID

This endpoint provides structural relationships but does not include user email addresses, names, or role assignments for users other than the authenticated caller.

### Step 6 — Get Team Details

For each node in the hierarchy with `entity_type = "team"`, makes a separate `GET /rest/V1/team/{team_id}` request to retrieve the team's `name` and `description`. This results in N additional API calls where N is the number of teams in the hierarchy.

### Step 7 — Extract Entities

Parses all API responses into normalized internal entity dictionaries:

- **Users** — built from hierarchy nodes with `entity_type = "customer"`. Full profile details (name, email, job title, telephone, active status) are only available for the authenticated user. All other users are represented as minimal entries using a synthetic email address in the format `customer_{id}@unknown`.
- **Teams** — built from hierarchy nodes with `entity_type = "team"` combined with the per-team detail responses.
- **Roles** — built directly from the roles API response.
- **Company** — built from the company detail response.
- **Hierarchy links** — parent-child relationships derived from `structure_parent_id` references between nodes.

### Step 8 — Handle User-Role Gap

The REST API does not expose which role is assigned to each user. This step applies one of four configurable strategies to handle this gap. See [User-Role Gap Strategies](#user-role-gap-strategies) for a full description of each option.

### Step 9 — Build OAA CustomApplication

Constructs a Veza OAA `CustomApplication` object from the extracted entities:

- Each user becomes a `LocalUser`
- The company becomes a `LocalGroup` with `group_type = "company"`
- Each team becomes a `LocalGroup` with `group_type = "team"`
- Each role becomes a `LocalRole`
- Each ACL resource ID becomes a `CustomPermission`

### Step 10 — Build Relationships

Wires up all relationships in the OAA graph:

1. `LocalUser` -> `LocalGroup` (company membership — all users)
2. `LocalUser` -> `LocalGroup` (team membership — derived from hierarchy)
3. `LocalUser` -> `LocalRole` (role assignment — present only if gap strategy produced assignments)
4. `LocalRole` -> `CustomPermission` (ACL permissions with `allow` status)
5. `LocalGroup` (team) -> `LocalGroup` (company) (team belongs to company)
6. `LocalUser` -> `LocalUser` reports-to relationships (limited by REST; only resolves when both parent and child are the authenticated user or resolvable by customer ID)

### Step 11 — Push to Veza or Save JSON

If `SAVE_JSON=true`, the OAA payload is written to a timestamped folder under `OUTPUT_DIR` as `oaa_payload.json`.

If `DRY_RUN=false`, the connector performs a preflight check against Veza to detect existing providers, then pushes the application payload using the OAA client. Results and timing metadata are written to `extraction_results.json` in the same output folder.

---

## Known Limitations

The REST API has several structural limitations compared to the GraphQL connector. Review [REST_GAP_ANALYSIS.md](REST_GAP_ANALYSIS.md) for complete details.

- **User-role assignment is not available via REST.** The `GET /V1/customers/{id}` and `GET /V1/customers/me` responses do not include a `role_id` field. The connector uses a configurable gap strategy to approximate this relationship.
- **Only the authenticated user has a full profile.** Users discovered via the hierarchy tree are represented with a customer ID only. Their email addresses, names, and status are unknown unless they are the authenticated caller.
- **Reports-to relationships are incomplete.** Hierarchy parent-child links between users cannot be fully resolved because email addresses are unavailable for non-authenticated users.
- **Multiple API calls are required.** A single extraction requires 5 to 7 or more HTTP requests, compared to 1 to 2 for the GraphQL connector. This increases latency and potential for partial failures.

---

## User-Role Gap Strategies

Because the REST API does not expose user-role assignments, the connector provides four strategies to handle this gap. The strategy is set via the `USER_ROLE_STRATEGY` environment variable or the `--strategy` CLI flag.

| Strategy | Config Value | Behavior | Accuracy | Maintenance |
|---|---|---|---|---|
| Default Role | `default_role` | Non-admin users are assigned the role named "Default User" (case-insensitive). If no such role exists, the first role in the list is used. The company admin is assigned the first role whose name contains "admin". | Low to medium — correct when most users have the default role, incorrect otherwise | None required |
| CSV Supplement | `csv_supplement` | Reads a CSV file mapping email addresses to role names. Any user found in the CSV is assigned the corresponding role. Users not in the CSV fall back to the `default_role` behavior. | High — as accurate as the CSV data | Manual updates required when user roles change |
| All Roles | `all_roles` | Roles are created in Veza with their full ACL permissions, but no user-role links are created. Users and roles exist in the graph independently. | Not applicable — makes no incorrect claims, but provides no effective permission data | None required |
| Skip | `skip` | User-role relationships are omitted entirely. Users appear in Veza but have no role or permission associations. | Not applicable — transparent gap | None required |

**Recommendation:** Use `csv_supplement` if user-role accuracy matters for your Veza access queries. Use `default_role` as a starting point when most users share the same role. Use `all_roles` or `skip` when you want to populate Veza with structural data only, without making inaccurate permission claims.

---

## CSV Format for csv_supplement Strategy

The CSV file must have a header row with exactly the columns `email` and `role_name`. The role name must match a role defined in Magento for the company (case-insensitive matching is applied).

```csv
email,role_name
user1@acme.com,Default User
user2@acme.com,Purchaser
admin@acme.com,Company Administrator
```

The default CSV path is `./data/user_role_mapping.csv`. A sample file is provided at that path. Override the path with `USER_ROLE_MAPPING_PATH` in `.env`.

If the CSV file is missing or unreadable when `csv_supplement` is selected, the connector logs a warning and falls back to the `default_role` strategy.

---

## Data Model Mapping

The connector maps Magento B2B REST API data to the Veza OAA `CustomApplication` model as follows.

| Veza OAA Type | Magento Entity | Primary Identifier | REST Source |
|---|---|---|---|
| `LocalUser` | Customer (company user) | `email` (or `customer_{id}@unknown` for non-auth users) | `GET /V1/customers/me` and hierarchy nodes |
| `LocalGroup` (company) | Company | `company_{id}` | `GET /V1/company/{id}` |
| `LocalGroup` (team) | CompanyTeam | `team_{id}` | `GET /V1/team/{id}` |
| `LocalRole` | Company Role | `role_{company_id}_{role_id}` | `GET /V1/company/role` |
| `CustomPermission` | ACL Resource | ACL resource ID string | `permissions[]` array on each role |

See [FIELD_MAPPING.md](FIELD_MAPPING.md) for the full field-level mapping from REST response fields to OAA properties.

---

## Output Files

Each run creates a timestamped subdirectory under `OUTPUT_DIR` with the format `YYYYMMDD_HHMM_{provider_name}/`.

| File | Description |
|---|---|
| `oaa_payload.json` | The full OAA payload that was or would be pushed to Veza. Present when `SAVE_JSON=true`. |
| `extraction_results.json` | Run metadata including start/end times, entity counts, strategy used, and any errors. Always written. |

Output folders older than `OUTPUT_RETENTION_DAYS` days are automatically deleted at the start of each run. Set `OUTPUT_RETENTION_DAYS=0` to disable automatic cleanup.

---

## Troubleshooting

### Authentication fails with 401

Verify that `MAGENTO_USERNAME` and `MAGENTO_PASSWORD` are correct and that the account is active. The account must be a company user, not a guest.

### "User is not associated with a company" error

The authenticated Magento account must belong to a B2B company. Verify the account in the Magento admin and confirm `extension_attributes.company_attributes.company_id` is present.

### Users appear as `customer_{id}@unknown` in Veza

This is expected behavior. The REST hierarchy endpoint returns only customer IDs for users other than the authenticated caller. Their full profiles are not accessible without individual `GET /V1/customers/{id}` calls, which require admin-level authentication not provided by this connector.

### CSV file not found warning with csv_supplement strategy

Ensure the file exists at the path specified by `USER_ROLE_MAPPING_PATH`. The default path is `./data/user_role_mapping.csv` relative to the connector's working directory. The connector falls back to `default_role` automatically when the file is missing.

### No roles assigned to users

If `USER_ROLE_STRATEGY=all_roles` or `USER_ROLE_STRATEGY=skip` is configured, this is expected. Switch to `default_role` or `csv_supplement` to populate role assignments.

### Push fails with provider conflict warning

The connector detected a Veza provider with the same name that was not created by this connector. Adjust `PROVIDER_NAME` or `PROVIDER_PREFIX` to use a unique name, or resolve the conflict in the Veza UI before running again.

### Enabling debug output

Set `DEBUG=true` in `.env` or pass `--debug` on the command line. Debug output includes request details, entity counts at each pipeline step, and hierarchy traversal information.

---

## Project Structure

```
rest-connector/
  run.py                        Entry point and CLI argument handling
  requirements.txt              Python dependencies
  config/
    __init__.py
    settings.py                 Default configuration values
    permissions.py              Magento B2B ACL permission catalog (33 resources)
  core/
    __init__.py
    orchestrator.py             Pipeline coordination (11 steps)
    magento_client.py           REST API client for all Magento endpoints
    entity_extractor.py         Parses REST responses into domain entities
    role_gap_handler.py         User-role gap workaround strategies
    application_builder.py      Builds OAA CustomApplication from entities
    relationship_builder.py     Wires up OAA relationships
    output_manager.py           Timestamped output folder management
    preflight_checker.py        Pre-push validation against Veza
    provider_registry.py        Tracks provider IDs across runs
    veza_client.py              OAA push client for Veza
  data/
    user_role_mapping.csv       Sample CSV for csv_supplement strategy
    sample_rest_responses/      Sample API responses for reference and testing
  tests/
    fixtures/                   Test fixture data
  output/                       Runtime output (gitignored)
```

---

## Related Documentation

- [FIELD_MAPPING.md](FIELD_MAPPING.md) — Field-level mapping from REST responses to OAA properties
- [REST_GAP_ANALYSIS.md](REST_GAP_ANALYSIS.md) — Detailed analysis of the user-role assignment gap and workaround strategies
