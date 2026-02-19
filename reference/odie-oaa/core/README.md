# Core - Standard Functionality

This directory contains the core connector logic. **Do not modify these files** unless you understand the implications.

## Purpose

The core modules provide the standard OAA processing pipeline that:
- Loads and parses CSV data
- Builds Veza OAA CustomApplication objects
- Manages output folders with retention
- Coordinates the processing workflow
- **Preflight checks** for existing provider conflicts
- **SSL certificate handling** for corporate proxy environments
- **Provider prefix** support for naming collision avoidance
- **Provider and data source ID tracking** for idempotent updates
- **Post-deployment validation** for identity mapping
- Handles Veza API interaction

## Files

| File | Purpose |
|------|---------|
| `csv_loader.py` | CSV loading and data manipulation utilities |
| `application_builder.py` | Builds OAA CustomApplication from CSV rows |
| `orchestrator.py` | Main processing coordination, Veza API, ID-based updates |
| `veza_client.py` | Veza API operations (provider + data source management) |
| `provider_registry.py` | Provider and data source ID persistence and tracking |
| `preflight_checker.py` | Provider conflict detection and SSL certificate handling |
| `output_manager.py` | Timestamped output folders and retention cleanup |
| `deployment_validator.py` | Post-deployment identity mapping validation |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        run.py                                    │
│                    (Entry Point)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     orchestrator.py                              │
│                                                                  │
│  - Loads configuration                                           │
│  - Validates settings                                            │
│  - Preflight check (conflicts + SSL)                             │
│  - Provider prefix support (PROVIDER_PREFIX)                     │
│  - ID-based updates (provider + data source IDs)                 │
│  - Coordinates processing                                        │
│  - Post-deployment validation                                    │
└─────────────────────────────────────────────────────────────────┘
    │              │              │              │
    ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
│ csv_     │ │ app_     │ │ output_      │ │ veza_        │
│ loader   │ │ builder  │ │ manager      │ │ client       │
│          │ │          │ │              │ │              │
│ Load CSV │ │ Build    │ │ Timestamped  │ │ API ops      │
│ Group by │ │ OAA      │ │ folders      │ │ push by name │
│ app      │ │ payloads │ │ Retention    │ │ push by ID   │
└──────────┘ └──────────┘ └──────────────┘ └──────────────┘
                                                  │
              ┌───────────────────┐   ┌───────────┴──────────┐
              │ preflight_        │   │ provider_            │
              │ checker           │   │ registry             │
              │                   │   │                      │
              │ SSL cert handling │   │ Provider IDs         │
              │ Conflict detect   │   │ Data source IDs      │
              │ Auto-override     │   │ Cross-run tracking   │
              └───────────────────┘   └──────────────────────┘
                      │
              ┌───────┴───────────────┐
              │ deployment_validator  │
              │                       │
              │ IdP provider query    │
              │ Identity mapping      │
              │ OAA app validation    │
              └───────────────────────┘
```

## Module Details

### csv_loader.py

Provides CSV data utilities:

```python
from core import load_csv, group_by_application, get_unique_permissions

rows = load_csv("./data/file.csv")
apps = group_by_application(rows)  # Dict of app_id -> rows
perms = get_unique_permissions(rows)  # Set of permission names
```

### application_builder.py

Builds OAA CustomApplication objects:

```python
from core import build_application

app, unclassified = build_application(app_id, app_rows)
# app = CustomApplication ready for JSON or Veza push
# unclassified = set of permission names needing review
```

Uses configuration from `config/` for:
- Permission definitions
- Role definitions and mappings

### orchestrator.py

Main processing coordinator with preflight checks and conflict resolution:

```python
from core import MultiSourceOrchestrator

orchestrator = MultiSourceOrchestrator(env_file="./.env")
orchestrator.validate_config()

# Preflight check - detects existing provider conflicts
preflight = orchestrator.preflight_check(dry_run_check=True)
if preflight["has_conflicts"]:
    # Handle conflicts (skip, delete, or abort)
    pass

# Process applications with preflight results
results = orchestrator.process_all_applications(preflight_result=preflight)
orchestrator.print_summary(results)
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `validate_config()` | Validate configuration before running |
| `preflight_check()` | Check for existing provider conflicts (includes SSL check) |
| `generate_provider_name()` | Generate provider name with optional prefix |
| `process_all_applications()` | Main processing loop (uses stored IDs for updates) |
| `delete_provider()` | Delete an existing provider by name |
| `print_summary()` | Print processing summary |
| `validate_identity_mapping()` | Post-deployment identity mapping check |
| `revalidate_identity_mapping()` | Re-check if previous validation failed |

**Data Source ID Tracking:**

The orchestrator loads the full provider registry (including data source IDs) before processing. When updating a known provider, it uses `push_application_by_ids()` to push directly by provider and data source ID, preventing duplicate data sources when names change.

**Provider Prefix:**

The orchestrator respects `PROVIDER_PREFIX` from environment:
```python
# If PROVIDER_PREFIX=ODIE in .env:
orchestrator.generate_provider_name("Fraud Detection AI")
# Returns: "ODIE_Fraud_Detection_AI"
```

### output_manager.py

Manages timestamped output folders:

```python
from core import OutputManager

manager = OutputManager("./output", "MyProvider", retention_days=30)
manager.cleanup_old_folders()
manager.create_timestamped_dir()  # Creates ./output/YYYYMMDD_HHMM_MyProvider/
path = manager.get_output_path("file.json")
```

### deployment_validator.py

Validates identity mapping configuration between IdP and OAA applications:

```python
from core import DeploymentValidator

validator = DeploymentValidator(
    veza_url="https://your-tenant.vezacloud.com",
    veza_api_key="your_api_key",
    output_dir="./output"
)

# Check identity mapping configuration
result = validator.validate(idp_type="activedirectory")
if not result["has_identity_mapping"]:
    print("WARNING: No identity mapping configured!")
    print("OAA users will NOT link to IdP identities in the graph.")

# Re-validate if previous check failed
result = validator.revalidate_if_failed(idp_type="activedirectory")
```

**Key Features:**
- Queries Active Directory providers via Veza API
- Checks `identity_mapping_configuration` field (null = not configured)
- Only checks ENABLED providers (skips disabled)
- Lists all OAA custom providers created
- Saves provider IDs to output for reference
- Supports re-validation after user configures identity mapping

### veza_client.py

Wraps all Veza API interactions through the `oaaclient` library:

```python
from core.veza_client import VezaClient

client = VezaClient(veza_url, veza_api_key)

# Provider operations
client.get_provider_list()
client.ensure_provider("MyProvider")

# Name-based push (for new providers)
client.push_application(app, provider_name, data_source_name)

# ID-based push (for updates — avoids creating duplicate data sources)
client.push_application_by_ids(app, provider_id, data_source_id)

# Data source queries
client.get_data_sources(provider_id)
```

### provider_registry.py

Persists provider and data source IDs to `oaa_provider_ids.json` for cross-run tracking:

```python
from core.provider_registry import ProviderRegistry

registry = ProviderRegistry(output_dir)

# Basic load (provider_name -> provider_id)
ids = registry.load()

# Full load (includes data source IDs)
records = registry.load_full()
# Returns: {provider_name: {id, app_id, app_name, data_sources: [{name, id}]}}
```

### preflight_checker.py

Detects provider conflicts and handles SSL certificate issues:

- **SSL handling**: Quick TLS handshake test (10s timeout) before any API call. On failure: tries cached cert, then `openssl` auto-pull, then prompts user.
- **Conflict detection**: Compares providers in Veza against the registry to distinguish our own (auto-override) from external (conflict).

**Supported IdP Types:**
| Type | API Path | Status |
|------|----------|--------|
| `activedirectory` | `/api/v1/providers/activedirectory` | Implemented |
| `okta` | `/api/v1/providers/okta` | Planned |
| `onelogin` | `/api/v1/providers/onelogin` | Planned |

## Customization

If you need to modify behavior:

1. **First check `config/`** - Most customizations can be done there
2. **For CSV column names** - Modify `csv_loader.py` and `application_builder.py`
3. **For processing logic** - Modify `orchestrator.py`

**Warning:** Changes to core modules may break the connector. Always test thoroughly after any modifications.
