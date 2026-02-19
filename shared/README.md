# magento-oaa-shared

Shared library for the Magento B2B Veza OAA connectors. Provides common utilities used by all four Magento connector variants.

## Installation

```bash
cd shared
pip install -e .
```

The connectors reference this package via `requirements.txt`:
```
magento-oaa-shared @ file://../../shared
```

## Modules

| Module | Class/Function | Purpose |
|--------|----------------|---------|
| `veza_client.py` | `VezaClient` | Wraps `oaaclient` library; manages provider creation and OAA payload push |
| `provider_registry.py` | `ProviderRegistry` | Persists provider and data source IDs in `oaa_provider_ids.json` across runs |
| `output_manager.py` | `OutputManager` | Creates timestamped output folders; enforces retention policy cleanup |
| `preflight_checker.py` | `PreflightChecker` | Detects provider name conflicts in Veza before pushing; auto-overrides own providers |
| `permissions.py` | `MAGENTO_ACL_PERMISSIONS` | 33-entry ACL permission catalog with display names, categories, and OAA permission types |
| `permissions.py` | `define_oaa_permissions()` | Registers all ACL permissions on an OAA CustomApplication |
| `application_builder_base.py` | `BaseApplicationBuilder` | Base class for OAA CustomApplication construction with shared property definitions |
| `push_helper.py` | `execute_veza_push()` | End-to-end push workflow: preflight check, create/update provider, push payload, update registry |

## Usage

```python
from magento_oaa_shared import (
    VezaClient,
    ProviderRegistry,
    OutputManager,
    PreflightChecker,
    MAGENTO_ACL_PERMISSIONS,
    define_oaa_permissions,
    BaseApplicationBuilder,
    execute_veza_push,
)
```

## Dependencies

- `oaaclient>=1.0.0` — Veza OAA client library
- `requests>=2.28.0` — HTTP client

## ACL Permission Catalog

The `MAGENTO_ACL_PERMISSIONS` dictionary defines all 33 B2B ACL resources that the connectors map to Veza `CustomPermission` objects. Each entry includes:
- `display_name` — Human-readable label
- `category` — Grouping (Sales, Company, Catalog, etc.)
- `oaa_permissions` — List of OAA permission types (DataRead, DataWrite, DataCreate, DataDelete, MetadataRead, NonData)
