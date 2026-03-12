# Magento B2B Authorization Data Extractor

Extracts B2B authorization data (companies, users, roles, permissions, teams, hierarchy) from Adobe Commerce / Magento stores via GraphQL and outputs structured JSON in Veza OAA format.

## Quick Start

```bash
# 1. Install the shared library
cd shared && pip install -e .

# 2. Install connector dependencies
cd ../connectors/on-prem-graphql
pip install -r requirements.txt

# 3. Configure credentials
cp .env.template .env
# Edit .env with your Magento store URL and company admin credentials

# 4. Run extraction
python run.py
```

## Validation

Verify the target Magento instance has B2B support before running the extractor. Copy `validation.sh` to the Magento server and run it from the Magento root directory:

```bash
bash validation.sh                    # run from Magento root
bash validation.sh /var/www/magento   # specify Magento root path
```

This checks edition, hosting type, B2B module status, GraphQL availability, and outputs a readiness summary.

> **Remote validation and sample extraction scripts** (validate-instance, run-extraction) are available on the `dev` branch under `deployment/test/`. These support cross-platform use (bash + Python) and do not require server access. See the dev branch README for details.

## Prerequisites

- Python 3.9+
- Adobe Commerce with B2B module enabled
- A Magento customer account that is a B2B company admin

Magento Open Source (CE) does not include B2B endpoints. This extractor requires **Adobe Commerce** with the B2B extension.

## How It Works

The extractor authenticates as a B2B company admin, runs a single GraphQL query to retrieve the complete company structure, then optionally supplements with a REST call for per-role ACL permissions. The extracted data is saved as JSON.

| Step | Action | API Call |
|------|--------|----------|
| 1 | Authenticate | `POST /rest/V1/integration/customer/token` |
| 2 | GraphQL extraction | `POST /graphql` (single query) |
| 3 | REST role supplement (optional) | `GET /rest/V1/company/role` |
| 4-6 | Parse entities, build OAA structure, save JSON | Local processing |

## What It Extracts

| Magento Entity | Description |
|----------------|-------------|
| Company | B2B organizational entity (name, legal name, admin) |
| Users | Company members (email, name, job title, status, active/inactive) |
| Teams | Groups within a company |
| Roles | Named permission sets (e.g., "Buyer", "Manager") |
| ACL Permissions | 34 granular B2B permissions across sales, quotes, purchase orders, company management |
| Hierarchy | Reporting structure (who reports to whom) |

### Relationships Captured

- User -> Company (membership)
- User -> Team (membership)
- User -> Role (assignment)
- Role -> Permission (ACL allow/deny)
- Team -> Company (nesting)
- User -> User (reports-to)

## Output

Each run creates a timestamped folder with the extracted data:

```
output/YYYYMMDD_HHMM_Magento_OnPrem_GraphQL/
  oaa_payload.json           Extracted authorization data (OAA format)
  extraction_results.json    Run metadata, entity counts, errors
```

## Configuration

All settings are loaded from `.env`. See `.env.template` for the full list.

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

## Repository Structure

```
magento/
├── validation.sh                    B2B capability check (run on Magento server)
├── connectors/on-prem-graphql/      GraphQL extractor (full OAA pipeline)
│   ├── run.py                       Entry point
│   ├── .env.template                Configuration template
│   ├── config/                      Default settings
│   ├── core/                        Extraction pipeline modules
│   │   ├── orchestrator.py          Pipeline coordination (7 steps)
│   │   ├── magento_client.py        REST auth + GraphQL execution
│   │   ├── graphql_queries.py       GraphQL query definition
│   │   ├── entity_extractor.py      Parse response into entities
│   │   ├── application_builder.py   Build OAA structure
│   │   ├── relationship_builder.py  Wire entity relationships
│   │   └── ce_data_builder.py       CE fallback: synthetic B2B from CE customers
│   ├── examples/                    Sample OAA payload output
│   └── tests/                       Unit tests
├── shared/                          Common library (magento-oaa-shared)
│   ├── magento_oaa_shared/          OAA builder, permissions, output management
│   └── tests/                       Unit tests
└── README.md
```

> Additional dev tooling (deployment scripts, remote validation, sample extraction, REST connector, architecture docs) is available on the `dev` branch.

## Running Tests

```bash
# Shared library tests
cd shared && pytest tests/

# Connector tests
cd connectors/on-prem-graphql && pytest tests/
```

## QA Branch Requirements

This branch is the staging gate between active development (`dev`) and production release (`main`). Nothing reaches `main` without passing through `qa` first.

### What belongs on qa/main

Only production-ready code ships on qa and main:

- **GraphQL connector** — the full 7-step extraction pipeline (`connectors/on-prem-graphql/`)
- **Shared library** — OAA builder, permissions, output manager (`shared/magento_oaa_shared/`)
- **Unit tests** — all tests that validate the above modules
- **Configuration templates** — `.env.template` with placeholder values only
- **Example output** — `oaa_payload_sample.json` with fictional data (`@acmecorp.example.com`)
- **User-facing docs** — `README.md`, `LICENSE`, `validation.sh`
- **CI/CD** — `.github/workflows/release.yml`

### What is stripped during dev-to-qa promotion

The following are removed automatically by `scripts/promote.sh dev-to-qa` (defined in `.branch-exclude-qa` on dev):

| Path | Reason |
|------|--------|
| `deployment/` | AWS test environment, validation/extraction scripts |
| `backlog/` | Cloud connectors (not yet production) |
| `reference/` | Legacy connectors, API docs |
| `scripts/` | Dev tooling (promote.sh) |
| `ARCHITECTURE.md`, `CONTRIBUTING.md` | Internal dev documentation |
| `connectors/on-prem-rest/` | REST connector (fallback, not production) |
| `connectors/README.md` | Multi-connector overview (only GraphQL ships) |
| `connectors/on-prem-graphql/extract_ce.py` | CE fallback extraction script |
| `connectors/on-prem-graphql/CE_VS_B2B.md` | CE vs B2B comparison doc |
| `connectors/on-prem-graphql/tests/fixtures/` | Test fixture JSON files |
| `shared/magento_oaa_shared/preflight_checker.py` | Not yet production-ready |
| `shared/magento_oaa_shared/provider_registry.py` | Not yet production-ready |
| `shared/magento_oaa_shared/push_helper.py` | Not yet production-ready |
| `shared/magento_oaa_shared/veza_client.py` | Not yet production-ready |
| `shared/tests/test_preflight_checker.py` | Tests for stripped module |
| `shared/tests/test_push_helper.py` | Tests for stripped module |
| `.branch-exclude-qa`, `.branch-exclude-main` | Exclude rules themselves |

### QA checklist (before promoting qa to main)

**1. No secrets or real credentials**
- [ ] No hardcoded passwords, API keys, tokens, or JWT strings
- [ ] `.env.template` uses only placeholder values (`your-password`, `example.com`)
- [ ] Test files use only mock/fictional credentials (`"secret"`, `@example.com`)

**2. No internal infrastructure references**
- [ ] No AWS account IDs, instance IDs, S3 bucket names
- [ ] No SSO URLs, IAM roles, or deployment-specific configuration
- [ ] No real IP addresses or internal hostnames

**3. No real customer data**
- [ ] Sample data uses fictional names and `@example.com` domains only
- [ ] No real email addresses, phone numbers, or company names
- [ ] `oaa_payload_sample.json` contains only synthetic data

**4. No dev-only files leaked**
- [ ] None of the paths listed in the stripping table above exist
- [ ] Verify: `git ls-files | grep -E '^(deployment/|backlog/|reference/|scripts/|ARCHITECTURE|CONTRIBUTING|\.branch-exclude)'`

**5. README accuracy**
- [ ] README does not reference files/directories that don't exist on this branch
- [ ] Repository structure section matches actual tracked files

**6. Tests pass**
- [ ] `cd shared && pytest tests/` — all pass
- [ ] `cd connectors/on-prem-graphql && pytest tests/` — all pass

**7. Version**
- [ ] `VERSION` file reflects the intended release version
- [ ] Version bump is intentional (triggers auto-release on main via CI)

### Promoting to main

```bash
# From dev branch:
./scripts/promote.sh qa-to-main     # merge qa into main
./scripts/promote.sh publish         # push main to external repo (triggers release)
```

### Merge conflict handling

When promoting dev-to-qa, conflicts commonly occur on files that were deleted on qa (by stripping) but modified on dev. Resolution:

1. Accept the dev version (`git add <file>`)
2. Complete the merge (`git commit --no-edit`)
3. Re-run the strip for all excluded paths
4. Commit the strip (`git commit -m "Strip dev-only files from qa"`)

## License

See [LICENSE](LICENSE).
