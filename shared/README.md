# magento-oaa-shared

Shared library for the Magento B2B data extractor. Provides OAA application builder, ACL permission definitions, and output management.

## Installation

```bash
cd shared
pip install -e .
```

The extractor references this package via `requirements.txt`:
```
magento-oaa-shared @ file://../../shared
```

## Modules

| Module | Class/Function | Purpose |
|--------|----------------|---------|
| `permissions.py` | `MAGENTO_ACL_PERMISSIONS` | 34-entry ACL permission catalog with display names, categories, and OAA permission types |
| `permissions.py` | `define_oaa_permissions()` | Registers all ACL permissions on an OAA CustomApplication |
| `application_builder_base.py` | `BaseApplicationBuilder` | Base class for OAA CustomApplication construction with property definitions |
| `output_manager.py` | `OutputManager` | Creates timestamped output folders; enforces retention policy cleanup |

## Usage

```python
from magento_oaa_shared import (
    MAGENTO_ACL_PERMISSIONS,
    define_oaa_permissions,
    BaseApplicationBuilder,
    OutputManager,
)
```

## Dependencies

- `oaaclient>=1.0.0` - Veza OAA client library (used for data structuring)
- `requests>=2.28.0` - HTTP client
