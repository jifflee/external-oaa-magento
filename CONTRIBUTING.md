# Contributing — SDLC & Branch Strategy

This document describes the development lifecycle, branch strategy, and release process for the Magento B2B OAA connector.

## Two-Repo Architecture

This project uses two GitHub repositories:

| Repository | Visibility | Purpose |
|------------|-----------|---------|
| [`source-oaa-magento`](https://github.com/jifflee/source-oaa-magento) | **Private** | Source of truth. All development, testing, deployment tools, backlog connectors, and reference material. |
| [`external-oaa-magento`](https://github.com/jifflee/external-oaa-magento) | **Public** | External distribution. Clean, release-ready code only. What an external user clones and runs. |

Code flows **one direction**: source → external. The external repo never receives direct commits.

```
source-oaa-magento (private)              external-oaa-magento (public)
┌────────────────────────────┐            ┌──────────────────────┐
│                            │            │                      │
│  dev ──→ qa ──→ main ──────────push────→│  main                │
│                            │            │                      │
│  3 branches, full tooling  │            │  1 branch, clean     │
└────────────────────────────┘            └──────────────────────┘
```

## Branch Strategy

### Three branches in `source-oaa-magento`

| Branch | Purpose | Remote | Contents |
|--------|---------|--------|----------|
| **`dev`** | Active development | `origin/dev` | Everything: production code + dev tools, deployment scripts, CE extraction, backlog connectors, reference material, promotion scripts |
| **`qa`** | Staging / validation | `origin/qa` | Production code + tests. Dev-only tools stripped. |
| **`main`** | Production releases | `origin/main` + `external/main` | Clean, documented, release-ready. Only what an external user needs. |

### What each branch contains

```
                        dev         qa          main        external/main
                        ───         ──          ────        ─────────────
Production code          ✓           ✓           ✓              ✓
Unit tests               ✓           ✓           ✓              ✓
GitHub Actions           ✓           ✓           ✓              ✓
LICENSE, VERSION         ✓           ✓           ✓              ✓
validation.sh            ✓           ✓           ✓              ✓
─────────────────────────────────────────────────────────────────────────
Promotion scripts        ✓           ✗           ✗              ✗
.branch-exclude-*        ✓           ✗           ✗              ✗
CONTRIBUTING.md          ✓           ✗           ✗              ✗
ARCHITECTURE.md          ✓           ✗           ✗              ✗
deployment/              ✓           ✗           ✗              ✗
backlog/                 ✓           ✗           ✗              ✗
reference/               ✓           ✗           ✗              ✗
on-prem-rest connector   ✓           ✗           ✗              ✗
CE extraction tools      ✓           ✗           ✗              ✗
Legacy shared modules    ✓           ✗           ✗              ✗
```

### Why three branches?

- **dev** is the working branch. It has everything: production code, dev tools, deployment automation, backlog experiments, and reference implementations. Developers work here daily.
- **qa** validates that the production code works independently from dev tools. Stripping dev-only files during promotion ensures nothing leaks through.
- **main** is what ships. It matches what appears on the external repo. Bumping `VERSION` on main triggers an auto-release via GitHub Actions.

## Promotion Workflow

All promotions are handled by `scripts/promote.sh`. You must be on the `dev` branch with a clean working tree.

### Step 1: dev → qa

```bash
./scripts/promote.sh dev-to-qa
```

What happens:
1. Checks out `qa`
2. Merges `dev` into `qa`
3. Reads `.branch-exclude-qa` and removes all listed dev-only files
4. Commits the removals as "Strip dev-only files from qa after merge from dev"
5. Returns to `dev`

### Step 2: qa → main

```bash
./scripts/promote.sh qa-to-main
```

What happens:
1. Checks out `main`
2. Merges `qa` into `main`
3. Reads `.branch-exclude-main` and removes any qa-only files (currently none)
4. Returns to `qa` (then you switch back to `dev`)

### Step 3: Publish to external

```bash
./scripts/promote.sh publish
```

What happens:
1. Pushes `main` to the `external` remote
2. Syncs repo description and topics from source → external
3. If the current `VERSION` tag doesn't exist as a release on external, creates it with the same release notes

### Full promotion (all three steps)

```bash
./scripts/promote.sh dev-to-qa
./scripts/promote.sh qa-to-main
./scripts/promote.sh publish
```

### Push branches to source remote

After any promotion, push the updated branches:

```bash
git push origin dev qa main
```

## File Stripping

The promotion script uses exclude files to know which paths to remove during promotion.

### `.branch-exclude-qa` — stripped when dev → qa

```
deployment/                                     # AWS EC2 setup, seed, debug scripts
backlog/                                        # Cloud connectors (not yet production)
reference/                                      # Legacy connectors, odie-oaa reference
ARCHITECTURE.md                                 # Internal architecture notes
connectors/on-prem-graphql/extract_ce.py        # CE data extraction tool
connectors/on-prem-graphql/CE_VS_B2B.md         # CE vs B2B comparison doc
connectors/on-prem-rest/                        # REST connector (not yet production)
connectors/README.md                            # Dev-only connectors overview
connectors/on-prem-graphql/tests/fixtures/.gitkeep
shared/magento_oaa_shared/preflight_checker.py  # Legacy Veza preflight module
shared/magento_oaa_shared/provider_registry.py  # Legacy Veza provider registry
shared/magento_oaa_shared/push_helper.py        # Legacy Veza push module
shared/magento_oaa_shared/veza_client.py        # Legacy Veza client module
shared/tests/test_preflight_checker.py          # Tests for legacy modules
shared/tests/test_push_helper.py                # Tests for legacy modules
scripts/                                        # Promotion scripts themselves
.branch-exclude-qa                              # This file
.branch-exclude-main                            # QA exclude file
```

### `.branch-exclude-main` — stripped when qa → main

Currently empty. Add paths here if qa gains test tooling that shouldn't reach production.

## Releases

### How releases are created

Releases are triggered by the `VERSION` file. The flow:

1. Developer bumps `VERSION` on `dev` (e.g., `0.1.1` → `0.2.0`)
2. Promote through qa → main → publish
3. On the **source** repo: GitHub Actions (`release.yml`) detects the VERSION change on main push and auto-creates a release with tag `v0.2.0`
4. On the **external** repo: `promote.sh publish` creates a matching release with the same notes. The external repo's own `release.yml` may also trigger independently.

### VERSION file

The `VERSION` file at the repo root contains a single version string (e.g., `0.2.0`). No `v` prefix.

### Creating a release manually

If you need to create a release without going through the full promotion:

```bash
# On source
gh release create v0.2.0 --title "v0.2.0" --generate-notes

# On external (or just run promote.sh publish)
gh release create v0.2.0 --repo jifflee/external-oaa-magento --title "v0.2.0" --notes "..."
```

## Git Remotes

The source repo has two remotes configured:

```
origin    → https://github.com/jifflee/source-oaa-magento.git   (private, all branches)
external  → https://github.com/jifflee/external-oaa-magento.git (public, main only)
```

### Setting up remotes (first-time clone)

If you clone the source repo fresh, add the external remote:

```bash
git clone https://github.com/jifflee/source-oaa-magento.git
cd source-oaa-magento
git remote add external https://github.com/jifflee/external-oaa-magento.git
```

## Daily Development Workflow

```bash
# 1. Work on dev
git checkout dev

# 2. Make changes, run tests
pytest shared/tests/ -v
cd connectors/on-prem-graphql && pytest tests/ -v

# 3. Commit to dev
git add <files>
git commit -m "description of change"
git push origin dev

# 4. When ready to promote
./scripts/promote.sh dev-to-qa       # dev → qa (strips dev tools)
./scripts/promote.sh qa-to-main      # qa → main
./scripts/promote.sh publish          # main → external repo
git push origin dev qa main           # push all branches to source remote
```

## Repository Structure (dev branch)

```
source-oaa-magento/
├── .github/workflows/release.yml       Auto-release on VERSION change
├── .branch-exclude-qa                  Files to strip: dev → qa
├── .branch-exclude-main                Files to strip: qa → main
├── .gitignore
├── ARCHITECTURE.md                     Internal architecture notes
├── CONTRIBUTING.md                     This file (SDLC & branch strategy)
├── LICENSE
├── README.md                           External-facing documentation
├── VERSION                             Current version (triggers releases)
├── validation.sh                       B2B readiness check script
│
├── scripts/
│   └── promote.sh                      Branch promotion & publish automation
│
├── connectors/
│   ├── README.md                       Connectors overview (dev only)
│   ├── on-prem-graphql/                GraphQL extractor (production)
│   │   ├── run.py                      Entry point
│   │   ├── config/                     Settings
│   │   ├── core/                       Extraction pipeline
│   │   ├── tests/                      Unit tests (37 tests)
│   │   ├── extract_ce.py              CE data extraction tool (dev only)
│   │   └── CE_VS_B2B.md              CE vs B2B comparison (dev only)
│   └── on-prem-rest/                   REST extractor (dev only, not production)
│
├── shared/                             magento-oaa-shared library
│   ├── magento_oaa_shared/             OAA builder, permissions, output
│   ├── tests/                          Unit tests (26 tests)
│   └── pyproject.toml
│
├── deployment/                         AWS EC2 test environment (dev only)
│   ├── setup/                          Instance setup scripts
│   ├── seed/                           Data seeding scripts
│   ├── test/                           Endpoint validation
│   └── debug/                          Troubleshooting utilities
│
├── backlog/                            Future connectors (dev only)
│   ├── cloud-graphql/                  Adobe Commerce Cloud (GraphQL)
│   └── cloud-rest/                     Adobe Commerce Cloud (REST)
│
└── reference/                          Legacy implementations (dev only)
    ├── legacy/                         Pre-refactor connectors
    └── odie-oaa/                       Original OAA reference
```

## What syncs between repos

| Artifact | source-oaa-magento | external-oaa-magento | Sync method |
|----------|-------------------|---------------------|-------------|
| Code (main branch) | All branches | main only | `promote.sh publish` → `git push` |
| Repo description | Set manually | Synced from source | `promote.sh publish` → `gh repo edit` |
| Topics/tags | Set manually | Synced from source | `promote.sh publish` → `gh repo edit` |
| Releases | Auto via GitHub Actions | Created by `promote.sh publish` | `gh release create` |
| Issues | Private issue tracking | Separate (if any) | Not synced |
| Branch protection | Configure independently | Configure independently | Not synced |

## Troubleshooting

### "Working tree is dirty"

The promotion script requires a clean working tree. Commit or stash changes first:

```bash
git stash
./scripts/promote.sh dev-to-qa
git stash pop
```

### Merge conflicts during promotion

If `promote.sh` reports merge conflicts:

```bash
# The script leaves you on the target branch (qa or main)
# Resolve conflicts manually
git mergetool        # or edit files directly
git add <resolved>
git commit
git checkout dev     # return to dev
```

### Remote 'external' not configured

```bash
git remote add external https://github.com/jifflee/external-oaa-magento.git
```

### Release already exists

The publish command skips release creation if the version tag already exists on external. To force-update release notes:

```bash
gh release edit v0.2.0 --repo jifflee/external-oaa-magento --notes "updated notes"
```
