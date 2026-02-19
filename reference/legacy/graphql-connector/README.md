# Magento B2B GraphQL Connector for Veza OAA

> **ARCHIVED:** This is the original standalone connector. It has been superseded by `connectors/on-prem-graphql/` (on-prem) and `connectors/cloud-graphql/` (cloud), which use the shared library (`shared/magento_oaa_shared`) and support both on-prem and Commerce Cloud authentication. New deployments should use the connectors in the `connectors/` directory.

## Overview

This connector extracts B2B authorization data from Adobe Commerce (Magento) via the GraphQL API and pushes it to Veza as an OAA `CustomApplication`. It is the recommended connector for Magento B2B integrations because it retrieves the full company structure — users, teams, roles, and hierarchy — in 1–2 API calls with complete entity resolution.

**What is extracted:**
- Company identity and admin metadata
- All company users (customers) with status, title, and contact info
- All company teams and their nesting within the company structure
- All roles assigned to users (name and ID)
- Organizational hierarchy (reports-to relationships derived from company structure)
- Explicit allow/deny permissions per role (via optional REST supplement)

**How data flows:**
```
Magento B2B Store
  └─ GraphQL API  ──────────────────────────────────────────┐
  └─ REST API (role supplement, optional)                    │
                                                             v
                                                   Veza OAA CustomApplication
                                                   (LocalUsers, LocalGroups,
                                                    LocalRoles, Permissions)
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.8 or later |
| Adobe Commerce | B2B module must be enabled |
| Magento credentials | Company admin user email and password |
| Veza tenant URL | Required for push mode only |
| Veza API key | Required for push mode only |

The authenticating user must be a **company admin** (the designated administrator of a B2B company account). Regular company members do not have access to the full company structure via the GraphQL API.

---

## Installation

```bash
cd graphql-connector
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your configuration
```

**Python dependencies** (`requirements.txt`):

| Package | Purpose |
|---|---|
| `oaaclient>=2.0.0` | Veza OAA client library for building and pushing CustomApplication payloads |
| `requests>=2.28.0` | HTTP client for Magento REST and GraphQL API calls |
| `python-dotenv>=0.21.0` | Loads configuration from `.env` file |

---

## Configuration

All configuration is read from a `.env` file (default: `./.env`). A template is provided at `.env.template`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MAGENTO_STORE_URL` | Yes | — | Base URL of the Magento store (e.g., `https://store.example.com`). Do not include a trailing slash. |
| `MAGENTO_USERNAME` | Yes | — | Email address of the B2B company admin user. |
| `MAGENTO_PASSWORD` | Yes | — | Password for the company admin user. |
| `VEZA_URL` | Push mode only | — | Base URL of the Veza tenant (e.g., `https://org.vezacloud.com`). |
| `VEZA_API_KEY` | Push mode only | — | Veza API key with OAA write permissions. |
| `PROVIDER_NAME` | No | `Magento_B2B` | Display name for the OAA provider in Veza. |
| `PROVIDER_PREFIX` | No | _(empty)_ | Optional prefix prepended to the provider name. Useful when running multiple connectors against the same Veza tenant to avoid naming conflicts. |
| `DRY_RUN` | No | `true` | When `true`, extracts and saves JSON but does not push to Veza. |
| `SAVE_JSON` | No | `true` | When `true`, writes `oaa_payload.json` and `extraction_results.json` to the output folder. |
| `DEBUG` | No | `false` | When `true`, prints detailed request/response information to stdout. |
| `OUTPUT_DIR` | No | `./output` | Base directory for timestamped output folders. |
| `OUTPUT_RETENTION_DAYS` | No | `30` | Number of days to retain output folders before automatic cleanup. Set to `0` to disable cleanup. |
| `USE_REST_ROLE_SUPPLEMENT` | No | `true` | When `true`, fetches explicit allow/deny permission data per role via the REST API after the GraphQL extraction. See [REST Role Supplement](#rest-role-supplement). |

---

## Usage

All commands are run from the `graphql-connector/` directory.

```bash
# Extract data, save JSON output, do not push to Veza
python run.py --dry-run

# Extract data and push to Veza
python run.py --push

# Extract, push, and print debug output
python run.py --push --debug

# Extract and push without the REST role supplement
python run.py --push --no-rest

# Use a custom .env file path
python run.py --push --env /path/to/custom.env
```

**CLI flags:**

| Flag | Description |
|---|---|
| `--dry-run` | Overrides `DRY_RUN=false` in `.env`; saves JSON without pushing |
| `--push` | Overrides `DRY_RUN=true` in `.env`; pushes to Veza |
| `--debug` | Overrides `DEBUG=false` in `.env`; enables verbose output |
| `--no-rest` | Disables REST role supplement for this run, overriding `USE_REST_ROLE_SUPPLEMENT=true` |
| `--env PATH` | Specifies path to `.env` file (default: `./.env`) |

If neither `--dry-run` nor `--push` is specified, the value of `DRY_RUN` in `.env` applies. The default in `.env.template` is `DRY_RUN=true`, so new installations default to dry-run mode.

---

## How It Works

The connector runs a sequential pipeline managed by `GraphQLOrchestrator`. Each step is printed to stdout as it executes.

### Step 1 — Authentication

Authenticates against the Magento REST token endpoint using company admin credentials. Returns a JWT bearer token used for all subsequent API calls.

```
POST /rest/V1/integration/customer/token
Body: {"username": "admin@example.com", "password": "..."}
Response: "eyJhbGciOi..."  (token string)
```

The token is stored in the session and automatically included in the `Authorization` header for all subsequent requests.

### Step 2 — GraphQL Extraction

Executes a single GraphQL query (`VezaExtraction`) that retrieves the complete company structure in one round trip.

```
POST /graphql
Headers: Authorization: Bearer {token}
Body: {"query": "query VezaExtraction { customer { ... } company { ... } }"}
```

The query returns:
- The current user's profile (`customer`)
- The company identity, admin details, and full organizational structure (`company.structure.items`)

Each structure item is either a `Customer` (user) or a `CompanyTeam` (team), and includes its parent in the hierarchy tree. Roles are embedded on each customer entity.

### Step 3 — REST Role Supplement (optional)

GraphQL returns only the role name and ID for each user; it does not return the explicit permission tree for a role. The REST supplement fills this gap by calling:

```
GET /rest/V1/company/role?searchCriteria[filter_groups][0][filters][0][field]=company_id
                          &searchCriteria[filter_groups][0][filters][0][value]={company_id}
                          &searchCriteria[filter_groups][0][filters][0][condition_type]=eq
```

This returns all roles for the company, each with a `permissions` array of `{resource_id, permission}` objects where `permission` is `"allow"` or `"deny"`. Only `"allow"` entries are translated into OAA permission grants.

If the REST supplement fails (for example, due to insufficient API permissions), the connector logs a warning and continues without explicit permission data. Roles will still appear in Veza but without permission assignments.

### Step 4 — Entity Extraction

`EntityExtractor` parses the raw GraphQL response into normalized domain objects: company, users, teams, roles, and organizational hierarchy.

GraphQL IDs are base64-encoded (e.g., `"MQ=="` decodes to `"1"`). The extractor decodes all IDs to their numeric string values before use.

The admin user is identified by comparing email addresses with `company.company_admin.email`.

### Step 5 — Build OAA Application

`ApplicationBuilder` constructs a Veza `CustomApplication` object, mapping each Magento entity to an OAA type:

| Magento Entity | OAA Type | Notes |
|---|---|---|
| Company | `LocalGroup` (type: `company`) | One per extraction run |
| Team | `LocalGroup` (type: `team`) | Zero or more |
| Customer | `LocalUser` | Identified by email address |
| Role | `LocalRole` | Deduplicated across all users |
| ACL Resource | `CustomPermission` | 33 resources defined in `config/permissions.py` |

Custom properties are defined for users (job title, telephone, admin flag), groups (legal name, email, admin email), and roles (Magento role ID, company ID). Application-level properties record the store URL and sync timestamp.

### Step 6 — Build Relationships

`RelationshipBuilder` establishes the six OAA relationship types:

1. **User -> Company** — Every extracted user is added as a member of the company group.
2. **User -> Team** — Users with a `team_id` are added as members of their team group.
3. **User -> Role** — Users with a `role_id` are assigned their role.
4. **Role -> Permission** — Each role's allowed ACL resources are linked as permission grants (only when REST supplement data is available).
5. **Team -> Company** — Each team is nested inside the company group (parent group relationship).
6. **User -> User (reports_to)** — Users whose parent node in the company structure is another user are linked via a `reports_to` property.

### Step 7 — Output and Push

- If `SAVE_JSON=true`, the OAA payload and run results are written to a timestamped output folder.
- If not in dry-run mode, the application is pushed to Veza via the OAA client. A preflight check runs first to detect whether a provider with the same name already exists in Veza. If the provider was created by a previous run of this connector (tracked in `output/oaa_provider_ids.json`), it is automatically overridden. If it was created externally, a conflict warning is printed.

---

## Data Model Mapping

### Entity Unique ID Formats

| Magento Entity | OAA Entity Type | Unique ID Format | Example |
|---|---|---|---|
| Company | `LocalGroup` (company) | `company_{numeric_id}` | `company_6` |
| Team | `LocalGroup` (team) | `team_{numeric_id}` | `team_3` |
| Customer | `LocalUser` | email address | `buyer@example.com` |
| Role | `LocalRole` | `role_{company_id}_{role_id}` | `role_6_2` |
| ACL Resource | `CustomPermission` | resource ID string | `Magento_Sales::place_order` |

### OAA Application Properties

| Property | Type | Description |
|---|---|---|
| `store_url` | String | Magento store base URL |
| `sync_timestamp` | String | ISO 8601 timestamp of the extraction run |
| `company_name` | String | Company display name |

### OAA LocalUser Properties

| Property | Type | Source |
|---|---|---|
| `name` / `unique_id` | String | Customer email address |
| `first_name` | String | `entity.firstname` |
| `last_name` | String | `entity.lastname` |
| `email` | String | `entity.email` |
| `is_active` | Boolean | `entity.status == "ACTIVE"` |
| `job_title` | String (custom) | `entity.job_title` |
| `telephone` | String (custom) | `entity.telephone` |
| `is_company_admin` | Boolean (custom) | Email matches `company_admin.email` |
| `company_id` | String (custom) | Decoded company numeric ID |

### OAA LocalGroup Properties (Company)

| Property | Type | Source |
|---|---|---|
| `name` | String | `company.name` |
| `unique_id` | String | `company_{id}` |
| `legal_name` | String (custom) | `company.legal_name` |
| `company_email` | String (custom) | `company.email` |
| `admin_email` | String (custom) | `company.company_admin.email` |
| `magento_company_id` | String (custom) | Decoded company numeric ID |

### OAA LocalGroup Properties (Team)

| Property | Type | Source |
|---|---|---|
| `name` | String | `entity.name` |
| `unique_id` | String | `team_{id}` |
| `description` | String (custom) | `entity.description` |
| `magento_team_id` | String (custom) | Decoded team numeric ID |
| `parent_company_id` | String (custom) | Company numeric ID |

### OAA LocalRole Properties

| Property | Type | Source |
|---|---|---|
| `name` | String | `role.name` |
| `unique_id` | String | `role_{company_id}_{role_id}` |
| `magento_role_id` | String (custom) | Decoded role numeric ID |
| `company_id` | String (custom) | Company numeric ID |

---

## Output Files

Each run creates a timestamped folder under `OUTPUT_DIR` with the format `YYYYMMDD_HHMM_{provider_name}`.

Example: `./output/20260217_1430_Magento_B2B/`

| File | Description |
|---|---|
| `oaa_payload.json` | The full OAA CustomApplication JSON payload, suitable for inspection or manual push |
| `extraction_results.json` | Run metadata including start/end timestamps, entity counts, success status, and any error details |

A registry file is maintained at `{OUTPUT_DIR}/oaa_provider_ids.json` after a successful push. This file tracks the Veza provider and data source IDs created by this connector so that subsequent runs can update (rather than duplicate) the same provider.

Output folders older than `OUTPUT_RETENTION_DAYS` days are automatically deleted at the start of each run.

---

## REST Role Supplement

The Magento GraphQL API returns the role name and ID for each user but does not expose the per-role permission tree (which ACL resources are allowed or denied). Without this data, roles appear in Veza without any permission assignments.

The REST role supplement addresses this by calling `GET /rest/V1/company/role` after the GraphQL extraction. This endpoint returns each role's full permissions list with explicit `"allow"` or `"deny"` values per ACL resource.

**Behavior:**
- Enabled by default (`USE_REST_ROLE_SUPPLEMENT=true`)
- Only `"allow"` permission entries are translated into OAA permission grants
- `"deny"` entries are silently ignored (Veza models absence of a grant, not explicit denials)
- If the REST call fails, the connector logs a warning and continues — roles will exist in Veza without permission links
- Can be disabled via `USE_REST_ROLE_SUPPLEMENT=false` or the `--no-rest` CLI flag

**When to disable:**
- The company admin account does not have REST API access to `/rest/V1/company/role`
- You only need user/team/role structure without permission details
- Debugging GraphQL extraction in isolation

---

## Troubleshooting

### Authentication failure (401)

- Verify `MAGENTO_STORE_URL` does not have a trailing slash
- Confirm the user is a B2B company admin (not a regular customer or Magento admin panel user)
- Check that the password does not contain special characters that may need URL encoding

### GraphQL endpoint not found (404)

- Confirm the store has the B2B module installed and enabled
- Try accessing `{MAGENTO_STORE_URL}/graphql` manually in a browser — a 200 response with GraphQL schema information indicates the endpoint is available

### No company data returned

- The authenticated user must be assigned as the company admin in Magento Admin > Customers > Companies
- Regular company members do not have access to `company.structure` in the GraphQL API

### REST role supplement returns 403

- The company admin account may lack REST API permissions
- Disable the supplement with `USE_REST_ROLE_SUPPLEMENT=false` and re-run
- Roles will still be extracted but will not have permission assignments in Veza

### Proxy configuration

If your network requires an HTTP proxy, set standard proxy environment variables before running:

```bash
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1
python run.py --push
```

The `requests` library honors `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy`, `NO_PROXY`, and `no_proxy` environment variables automatically.

### Provider name conflicts in Veza

If the connector reports a provider conflict, it means a provider with the same name exists in Veza but was not created by this connector. Use `PROVIDER_PREFIX` to create a uniquely named provider:

```bash
PROVIDER_PREFIX=prod
```

This produces a provider named `prod_Magento_B2B` (or `prod_{PROVIDER_NAME}`).

---

## Architecture

The connector is structured as a pipeline of single-responsibility modules.

| Module | File | Responsibility |
|---|---|---|
| Orchestrator | `core/orchestrator.py` | Coordinates the full extraction pipeline; reads `.env`; prints progress |
| Magento Client | `core/magento_client.py` | Handles REST authentication, GraphQL execution, and REST role supplement calls |
| Entity Extractor | `core/entity_extractor.py` | Parses raw GraphQL JSON into normalized Python objects; decodes base64 IDs |
| Application Builder | `core/application_builder.py` | Constructs the OAA `CustomApplication` from entities; defines custom properties |
| Relationship Builder | `core/relationship_builder.py` | Wires all six OAA relationship types between users, groups, roles, and permissions |
| Veza Client | `core/veza_client.py` | Wraps the `oaaclient` library; manages provider lifecycle and payload push |
| Provider Registry | `core/provider_registry.py` | Persists Veza provider and data source IDs across runs in `oaa_provider_ids.json` |
| Output Manager | `core/output_manager.py` | Creates timestamped output folders; enforces retention policy cleanup |
| Preflight Checker | `core/preflight_checker.py` | Checks for provider name conflicts in Veza before pushing |
| Permissions Config | `config/permissions.py` | Defines the 33-entry ACL permission catalog with display names, categories, and OAA permission types |
| Settings | `config/settings.py` | Defines default values for all configuration variables |

### Entry Point

`run.py` parses CLI arguments, instantiates `GraphQLOrchestrator`, applies any CLI overrides to the loaded configuration, then calls `orchestrator.run()`.

### GraphQL Query

The extraction query is defined in `core/graphql_queries.py` as `FULL_EXTRACTION_QUERY`. The query is named `VezaExtraction` and retrieves both `customer` (the authenticated user's profile) and `company` (the full organizational structure) in a single request. A second query, `ROLE_PERMISSIONS_QUERY`, is defined but not used by the default pipeline — it is available for scenarios where GraphQL-only permission extraction is needed.
