# Config - Customer Customization Area

This directory contains all customer-configurable settings. **This is the primary area you will modify** to customize the connector for your organization.

## Files

| File | Purpose | Frequency of Changes |
|------|---------|---------------------|
| `settings.py` | Known permissions list and default settings | Occasional |
| `roles.py` | Role definitions and permission mappings | **Frequent** |
| `permissions.py` | Base permission definitions (C,R,U,D,M,N,?) | Rare |

## Quick Start - Adding a New Role

When you encounter an "unclassified permission" in the output, follow these steps:

### Example: Adding "DataAnalyst" role with Read + Metadata access

**Step 1: Edit `roles.py`**

```python
# Add to ROLE_DEFINITIONS
ROLE_DEFINITIONS = [
    # ... existing roles ...
    ("DataAnalyst", ["R", "M"], "role_dataanalyst"),  # Add this
]

# Add to PERMISSION_TO_ROLE
PERMISSION_TO_ROLE = {
    # ... existing mappings ...
    "dataanalyst": "role_dataanalyst",  # Add this
}

# Add to ROLE_TO_EFFECTIVE
ROLE_TO_EFFECTIVE = {
    # ... existing entries ...
    "dataanalyst": ["R", "M"],  # Add this
}
```

**Step 2: Edit `settings.py`**

```python
KNOWN_PERMISSIONS = {
    # ... existing permissions ...
    "dataanalyst",  # Add this
}
```

**Step 3: Validate your changes**

```bash
python validate_config.py --verbose
```

## File Details

### settings.py

Contains three main configurations:

1. **KNOWN_PERMISSIONS** - Set of permission names that are "classified"
   - Permissions in this set map to predefined roles
   - Permissions NOT in this set are flagged as "NEEDS REVIEW"

2. **DEFAULT_SETTINGS** - Default values when .env is not set
   - Provider name and prefix, CSV filename, output directory
   - Processing options (dry_run, save_json, debug)

3. **PROXY_ENV_VARS** - List of proxy-related environment variables
   - Used to detect and display proxy configuration at startup

### roles.py

The main configuration file with three data structures:

1. **ROLE_DEFINITIONS** - List of role tuples
   ```python
   ("DisplayName", ["C", "R", "U"], "role_id")
   ```

2. **PERMISSION_TO_ROLE** - Maps CSV permission names to role IDs
   ```python
   "csv_permission_name": "role_id"
   ```

3. **ROLE_TO_EFFECTIVE** - Maps role names to effective permissions (for display)
   ```python
   "rolename": ["C", "R", "U"]
   ```

### permissions.py

Defines the base atomic permissions:

| Symbol | Veza Permission | Meaning |
|--------|-----------------|---------|
| C | DataCreate | Create new data |
| R | DataRead | Read/view data |
| U | DataWrite | Update/modify data |
| D | DataDelete | Delete data |
| M | MetadataRead + MetadataWrite | Metadata access |
| N | NonData | Non-data operations |
| ? | Uncategorized | Unknown - needs review |

**Note:** You typically don't need to modify this file unless you need entirely new permission types.

## Validation

Always run the validator after making changes:

```bash
# Quick check
python validate_config.py

# Detailed output
python validate_config.py --verbose
```

The validator checks:
- Role definitions are properly formatted
- Permission mappings reference valid roles
- No duplicate role names or IDs
- Consistency between all configuration files

## Provider Prefix (Conflict Avoidance)

If you encounter provider name conflicts when pushing to Veza (providers with the same name already exist), you can add a prefix to all integration names.

**In `.env`:**
```bash
# Uncomment and set to add prefix to all provider names
PROVIDER_PREFIX=ODIE
```

**Effect:**
- Without prefix: `Fraud_Detection_AI`
- With prefix `ODIE`: `ODIE_Fraud_Detection_AI`

**When to use:**
- When the preflight check reports existing providers with the same name
- When deploying to a shared Veza tenant
- When testing alongside production integrations

The preflight check (runs during both `--dry-run` and `--push`) will suggest this option if conflicts are detected.

## Proxy Configuration

If your network requires a proxy to reach Veza cloud, add to `.env`:

```bash
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1
```

**How it works:**
1. `load_dotenv()` loads `.env` variables into `os.environ`
2. Python's `requests` library (used internally by oaaclient) automatically reads `HTTP_PROXY`/`HTTPS_PROXY` from `os.environ`
3. All Veza API calls are routed through the proxy

No code changes needed - proxy handling is automatic. Proxy status is displayed at startup for confirmation.
