# ODIE-OAA Connector

A standalone connector for pushing application permission data to Veza using the Open Authorization API (OAA).

## Overview

This connector processes CSV files containing user-application-permission mappings and creates individual Veza integrations for each application. It supports:

- Multiple applications in a single CSV file
- Automatic role classification with NEEDS_REVIEW flagging for unknown permissions
- **Preflight checks** to detect conflicts before pushing
- **Provider prefix** to avoid naming collisions
- Dry-run mode for testing without pushing to Veza
- JSON payload generation for debugging

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Access to a Veza tenant (for live push mode)

## Quick Start

### 1. Set Up Virtual Environment

```bash
cd odie-oaa
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.template .env
# Edit .env with your Veza credentials
```

### 3. Run in Dry-Run Mode (Recommended First Step)

```bash
python3 run.py --dry-run
```

This will:
- Load and validate your CSV data
- Check for existing provider conflicts in Veza
- Generate JSON payloads without pushing
- Report any issues that need resolution

### 4. Push to Veza

```bash
python3 run.py --push
```

## CSV Format

The input CSV must have the following columns:

| Column | Description | Required |
|--------|-------------|----------|
| `User Id` | Unique identifier for the user | Yes |
| `User Name` | Display name of the user | No |
| `User Email` | User's email address (used for identity linking) | No |
| `Application_FIN_ID` | Unique identifier for the application | Yes |
| `Application_FIN_Name` | Display name of the application | Yes |
| `Application_FIN_Criticality` | Criticality level (e.g., High, Medium, Low) | No |
| `Permission` | Role/permission name assigned to the user | Yes |

### Example CSV

```csv
User Id,User Name,User Email,Application_FIN_ID,Application_FIN_Name,Application_FIN_Criticality,Permission
U001,John Smith,john.smith@example.com,APP001,Trading Platform,High,Admin
U002,Jane Doe,jane.doe@example.com,APP001,Trading Platform,High,ReadOnly
U003,Bob Wilson,bob.wilson@example.com,APP002,Risk System,Medium,Editor
```

## Usage

### Basic Commands

```bash
# Dry run - validate and check for conflicts
python3 run.py --dry-run

# Dry run with custom CSV
python3 run.py --csv /path/to/your/data.csv --dry-run

# Push to Veza (requires configured .env)
python3 run.py --push

# Push, automatically skip existing providers
python3 run.py --push --skip-existing

# Push, delete and recreate existing providers
python3 run.py --push --delete-existing

# Enable debug output
python3 run.py --dry-run --debug
```

### Command-Line Arguments

| Argument | Short | Description |
|----------|-------|-------------|
| `--env` | `-e` | Path to .env file (default: `./.env`) |
| `--csv` | `-c` | Override CSV input path |
| `--dry-run` | | Generate JSON only, no push to Veza |
| `--push` | | Push to Veza (runs preflight check first) |
| `--skip-existing` | | Auto-skip applications with existing providers |
| `--delete-existing` | | Auto-delete and recreate existing providers |
| `--validate-only` | | Only run identity mapping validation (re-check) |
| `--skip-validation` | | Skip post-deployment identity mapping validation |
| `--idp-type` | | Identity provider type to validate (default: activedirectory) |
| `--debug` | | Enable debug output with stack traces |

## Preflight Check

Before pushing to Veza, the connector automatically checks for conflicts.

### Auto-Override (Same Provider)

If you run the connector multiple times, the preflight check recognizes providers from your previous run and **auto-overrides** them instead of treating them as conflicts:

```
============================================================
PREFLIGHT CHECK - Validating against Veza
============================================================
  Found 3 provider(s) from previous run
  Provider prefix: ODIE_
  Checking 3 applications against Veza...

  AUTO-OVERRIDE: 3 provider(s) match previous run (will update)
    - ODIE_Fraud_Detection_AI (ID: abc123...)
    - ODIE_Risk_System (ID: def456...)
    - ODIE_Trading_Platform (ID: ghi789...)

  OK: No external conflicts - 3 provider(s) will be updated
```

This is tracked via `output/oaa_provider_ids.json` which stores the provider **and data source** IDs from each run. On subsequent pushes, stored data source IDs are used directly to update in place, preventing duplicate data sources when names change.

### External Conflicts

If providers exist that were NOT created by this connector (different IDs), they are treated as conflicts:

```
============================================================
PREFLIGHT CHECK - Validating against Veza
============================================================
  Provider prefix: (none configured)
  Checking 3 applications against Veza...

  CONFLICTS FOUND: 2 provider(s) already exist in Veza
  --------------------------------------------------------

  Provider: Fraud_Detection_AI
    - Application: Fraud Detection AI (ID: FIN-040)
    - Veza Provider ID: abc123-def456...

  ==========================================================
  ACTION REQUIRED - Resolve conflicts before pushing:
  ==========================================================

  Option 1: Add a provider prefix (RECOMMENDED)
            Edit .env and uncomment PROVIDER_PREFIX:
            PROVIDER_PREFIX=ODIE
            This changes: Fraud_Detection_AI
                     to: ODIE_Fraud_Detection_AI

  Option 2: Delete existing providers in Veza UI
            Then run: python3 run.py --push

  Option 3: Skip existing providers
            Run: python3 run.py --push --skip-existing

  Option 4: Delete and recreate providers automatically
            Run: python3 run.py --push --delete-existing
```

### Using Provider Prefix

To avoid conflicts with existing providers, add a prefix in your `.env`:

```bash
# All integration names become: {PREFIX}_{App_Name}
# Example: ODIE_Fraud_Detection_AI instead of Fraud_Detection_AI
PROVIDER_PREFIX=ODIE
```

## Post-Deployment Validation

After pushing to Veza, the connector automatically validates that identity mapping is configured. **Without identity mapping, OAA application users will NOT link to IdP identities** in the Veza graph.

### What is Identity Mapping?

Identity mapping connects users in your OAA custom applications to their identities in the Identity Provider (e.g., Active Directory). This enables:
- Graph relationships between IdP users and application access
- Access reviews showing who has access to what
- Query capabilities across identity and application data

### Validation Output

```
============================================================
POST-DEPLOYMENT VALIDATION - Identity Mapping Check
============================================================
  IdP Type: Active Directory

  Active Directory Providers: 1 found
    - ad_corp: identity_mapping_configuration = NULL (NOT CONFIGURED)

  OAA Custom Providers: 3 found
    - ODIE_Fraud_Detection_AI (ID: abc123...)
    - ODIE_Risk_System (ID: def456...)
    - ODIE_Trading_Platform (ID: ghi789...)

  ========================================================
  RESULT: FAILED - NO IDENTITY MAPPING RELATIONSHIP
  --------------------------------------------------------

  ISSUES:
    - Active Directory provider(s) have identity_mapping_configuration = null

  RECOMMENDATIONS:
    - Configure identity mapping on your Active Directory provider in Veza UI
    - Go to: Integrations > Active Directory > Edit > Identity Mapping

  WHY THIS MATTERS:
    Without identity_mapping_configuration, OAA application users
    will NOT link to Active Directory identities in the Veza graph.
    Access reviews and queries will not show user relationships.
  ========================================================
```

### Re-Validating After Configuration

After configuring identity mapping in the Veza UI:

```bash
# Re-run validation only
python3 run.py --validate-only

# Or use the standalone validator
python3 -m config.validation.deployment_validator --revalidate
```

### Skipping Validation

If you want to skip validation (e.g., testing without IdP):

```bash
python3 run.py --push --skip-validation
```

### Output Files

After validation, these files are saved to the output folder:

| File | Description |
|------|-------------|
| `identity_mapping_validation.json` | Full validation results |
| `oaa_provider_ids.json` | Provider and data source IDs for update tracking |

## Environment Variables

Configure these in your `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `VEZA_URL` | Your Veza tenant URL | (required for push) |
| `VEZA_API_KEY` | Veza API key | (required for push) |
| `PROVIDER_NAME` | Base provider name (used in output folder naming) | `Odie_Application` |
| `PROVIDER_PREFIX` | Prefix for all integration names (optional) | (none) |
| `CSV_FILENAME` | CSV filename in `./data/` folder | `sample_permissions.csv` |
| `CSV_INPUT_PATH` | Full CSV path (overrides CSV_FILENAME) | - |
| `OUTPUT_DIR` | Base directory for output | `./output` |
| `OUTPUT_RETENTION_DAYS` | Auto-delete folders older than X days (0=disabled) | `30` |
| `DRY_RUN` | Run without pushing to Veza | `true` |
| `SAVE_JSON` | Save JSON payloads to disk | `true` |
| `DEBUG` | Enable debug mode | `false` |

### Proxy Configuration (Optional)

If your network requires a proxy to reach Veza:

```bash
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1
```

## Permission Mapping

The connector automatically maps known permission names to Veza-compatible roles:

| Input Permission | Mapped Role | Effective Permissions |
|-----------------|-------------|----------------------|
| `SuperAdmin` | SuperAdmin | C, R, U, D, M, N (full access) |
| `Admin` | Admin | C, R, U, D, M |
| `Editor`, `Write` | Editor | R, U |
| `ReadWrite` | ReadWrite | R, U |
| `Contributor` | Contributor | C, R, U |
| `Auditor` | Auditor | R, M |
| `ReadOnly`, `Read`, `Viewer` | ReadOnly | R |

**Unknown permissions** are flagged as `NEEDS_REVIEW` and assigned the `?` (Uncategorized) effective permission for easy identification in Veza.

### Effective Permission Key

- **C** - Create (DataCreate)
- **R** - Read (DataRead)
- **U** - Update (DataWrite)
- **D** - Delete (DataDelete)
- **M** - Metadata (MetadataRead, MetadataWrite)
- **N** - NonData
- **?** - Uncategorized (needs review)

## Output

### JSON Payloads

Each run creates a timestamped folder in the output directory:

```
output/
├── 20250203_1430_Odie/
│   ├── FIN001_oaa.json
│   ├── FIN002_oaa.json
│   ├── FIN003_oaa.json
│   └── multi_source_results.json
└── 20250204_0900_Odie/
    └── ...
```

Folder naming format: `YYYYMMDD_HHMM_<provider_name>`

### Results Summary

The `multi_source_results.json` file contains:
- Processing timestamps
- Configuration used
- Per-application results (success/failure/skipped)
- List of unclassified permissions requiring review
- Deleted and skipped provider information

## Project Structure

```
odie-oaa/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.template             # Environment config template
├── run.py                    # Main entry point
├── config/                   # Customer configuration (EDIT THESE)
│   ├── __init__.py
│   ├── settings.py           # Known permissions and defaults
│   ├── roles.py              # Role definitions and mappings
│   ├── permissions.py        # Base permission definitions
│   ├── README.md             # Config documentation
│   ├── validation/           # Validation utilities
│   │   ├── __init__.py
│   │   ├── config_validator.py
│   │   └── deployment_validator.py
│   └── terminate/            # Safe provider cleanup
│       ├── __init__.py
│       └── terminate.py      # python3 -m config.terminate.terminate
├── core/                     # Core modules (DO NOT EDIT)
│   ├── __init__.py
│   ├── orchestrator.py       # Main processing coordination
│   ├── veza_client.py        # Veza API operations (provider + data source)
│   ├── provider_registry.py  # Provider & data source ID tracking
│   ├── preflight_checker.py  # Conflict detection + SSL handling
│   ├── application_builder.py # OAA application construction
│   ├── csv_loader.py         # CSV utilities
│   ├── output_manager.py     # Output folder management
│   ├── deployment_validator.py # Identity mapping validation
│   └── README.md             # Core documentation
├── identity-mapping/         # AD ↔ OAA identity mapping automation
│   ├── run.py                # Entry point (steps 1-4)
│   ├── veza_api.py           # Shared API client
│   ├── debug_raw_response.py # Debug: dump raw provider responses
│   ├── steps/                # Step modules
│   │   ├── __init__.py
│   │   ├── fetch_ad_config.py    # Step 1: AD provider discovery
│   │   ├── fetch_custom_apps.py  # Step 2: custom app discovery
│   │   ├── build_mapping.py      # Step 3: mapping report
│   │   └── apply_mapping.py      # Step 4: apply mappings
│   └── output/               # Daily output folders (YYYY-MM-DD/)
├── certs/                    # Auto-generated SSL cert cache (gitignored)
├── data/                     # Input CSV files
│   └── sample_permissions.csv
└── output/                   # Generated payloads (created at runtime)
```

## Cleanup and Termination

The termination script safely removes OAA providers that were created by this connector.

### Preview Deletion (Safe - No Changes)

```bash
python3 -m config.terminate.terminate --dry-run
```

This reads `output/oaa_provider_ids.json` and shows what WOULD be deleted.

### Execute Deletion

```bash
# With per-provider confirmation
python3 -m config.terminate.terminate --execute

# With single batch confirmation
python3 -m config.terminate.terminate --execute --batch
```

### Safety Checkpoints

The termination script has 6 safety checkpoints:

1. **File Validation** - Verify oaa_provider_ids.json exists and is valid
2. **Provider Enumeration** - Show exactly what will be deleted
3. **Veza Connection** - Verify API connectivity
4. **Provider Verification** - Confirm each provider exists and matches records
5. **Final Confirmation** - Explicit user consent required (type "DELETE")
6. **Post-Deletion Verification** - Confirm providers were deleted

**IMPORTANT:** Providers with mismatched IDs (recreated by another process) will NOT be deleted for safety.

## SSL Certificate Handling

When running behind a corporate proxy that performs SSL inspection, Python's `requests` library may fail to verify Veza's TLS certificate (even though `curl` works, since it uses the macOS keychain).

The preflight check automatically detects and handles this:

```
============================================================
PREFLIGHT CHECK - Validating against Veza
============================================================
  Verifying SSL connectivity... FAILED
  Attempting to retrieve server certificate chain... OK
  Retrying SSL verification... OK
  Cached certificate bundle: ./certs/your-tenant.vezacloud.com.pem
```

### How It Works

1. **Initial SSL test** (10-second socket timeout) — runs before any Veza API call
2. **On failure** — checks for a previously cached cert in `./certs/`
3. **If no cache** — pulls the certificate chain via `openssl s_client` and appends it to a copy of the certifi CA bundle
4. **If auto-fix fails** — prompts for manual resolution:
   - **[P]** Provide path to your corporate CA certificate (.pem)
   - **[B]** Bypass SSL verification (insecure)
   - **[A]** Abort

Cached certificates persist in `./certs/<hostname>.pem` across runs. If SSL connectivity succeeds on the first test, the cert process is skipped entirely.

## Troubleshooting

### Common Issues

**"SSL ERROR" / "Verifying SSL connectivity... FAILED"**
- This is common behind corporate proxies with SSL inspection
- The connector will attempt to auto-fix by pulling the server certificate
- If auto-fix fails, provide your corporate CA cert via the `[P]` option
- You can also set `REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem` in your environment

**"CSV file not found"**
- Check the `--csv` path or `CSV_FILENAME` in `.env`
- Ensure the file exists and is readable

**"VEZA_URL is required when DRY_RUN=false"**
- Configure `VEZA_URL` and `VEZA_API_KEY` in `.env`
- Or use `--dry-run` flag for testing

**"Provider with the same external ID already exists"**
- Run `--dry-run` first to see conflicts
- Use `PROVIDER_PREFIX` in `.env` to add a unique prefix
- Or use `--skip-existing` or `--delete-existing` flags

**"ModuleNotFoundError: No module named 'oaaclient'"**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

### Validate Configuration

Run the validator to check your configuration:

```bash
python3 -m config.validation.config_validator --verbose
```

### Debug Mode

Enable debug mode for detailed error information:

```bash
python3 run.py --dry-run --debug
```

## Deployment

### Files to Deploy

Only these files need to be transported:

```
odie-oaa/
├── run.py                 # Main entry point
├── requirements.txt       # Python dependencies
├── .env.template          # Environment template (copy to .env)
├── README.md              # Documentation
├── core/                  # Core modules
│   └── *.py
├── config/                # Configuration
│   ├── *.py
│   ├── validation/*.py
│   └── terminate/*.py     # Cleanup script
└── data/                  # Sample data only
    └── sample_permissions.csv
```

### NOT Needed (Generated Locally)

- `venv/` - Create with `python -m venv venv`
- `__pycache__/` - Generated automatically at runtime
- `.env` - Contains secrets, create from template
- `output/*` - Generated at runtime

### Quick Start After Deployment

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.template .env
# Edit .env with your Veza credentials

# 4. Validate configuration
python3 -m config.validation.config_validator

# 5. Run dry-run test
python3 run.py --dry-run
```

## Identity Mapping Module

The `identity-mapping/` folder contains a separate module for automating AD-to-OAA identity mapping configuration.

```bash
cd identity-mapping
python run.py                              # Steps 1-3: discover current state (read-only)
python run.py --apply --limit 1            # Step 4: apply 1 mapping
python run.py --apply --limit 1 --dry-run  # Preview without changes
```

See `identity-mapping/` for details.

## TODO

### Provider Filtering for Identity Mapping

**Current state (implemented):**
- Identity mapping filters custom apps by: `state=ENABLED` + `custom_template=application` + `external_id` starts with `oaa_external:` + exclude list (Windows Server, Windows Files)
- This correctly identifies the 98 ODIE-managed providers without relying on provider name prefix
- Use `--no-filter` to override and see all providers

**Findings:**
- Provider names are **immutable** — the PATCH endpoint does not accept `name` as an updatable field
- OAA tags (`app.add_tag()`) and custom properties (`app.set_property()`) are in the **data source payload**, NOT on the provider object — they don't appear on `api/v1/providers/custom`
- Provider endpoint fields: `id`, `name`, `state`, `custom_template`, `external_id`

**Future state:**
- [ ] Set `PROVIDER_PREFIX` in `.env` (use `PROVIDER_NAME` value, e.g., `ODIE`) so new providers are created with `ODIE_` prefix
- [ ] Once all providers have the prefix, switch identity-mapping to use `--prefix ODIE` instead of `external_id`-based filtering
- [ ] Update the main pipeline's `run.py` to enforce `PROVIDER_PREFIX` is set before push

### Identity Mapping Automation
- [ ] Apply remaining 101 custom app mappings (use `--apply --limit N`)
- [ ] Verify all mappings after full rollout
- [ ] Document rollback procedure using backup files

## License

Internal use only.
