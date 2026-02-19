# Architecture

## Overview

This repository contains Veza OAA connectors that extract B2B authorization data from Adobe Commerce (Magento) stores. The connectors model companies, users, teams, roles, and ACL permissions as a Veza `CustomApplication` for authorization visibility.

## Folder Structure

```
magento/
├── connectors/                  Active connectors (ready for dev/testing)
│   ├── on-prem-graphql/         Self-hosted Magento, GraphQL API (recommended)
│   └── on-prem-rest/            Self-hosted Magento, REST API (fallback)
├── backlog/                     Connectors not yet ready (missing prerequisites)
│   ├── cloud-graphql/           Needs Commerce Cloud env + IMS credentials
│   └── cloud-rest/              Needs Commerce Cloud env + IMS credentials
├── shared/                      Common library: magento-oaa-shared
├── deployment/                  AWS EC2 test environment (Terraform + scripts)
├── reference/                   Non-deployable reference material
│   ├── odie-oaa/                Generic CSV-to-Veza connector (reference)
│   ├── commerce-webapi/         Adobe Commerce API docs (Gatsby)
│   └── legacy/                  Superseded standalone connectors
│       ├── graphql-connector/
│       └── rest-connector/
├── README.md                    Entry point + connector selection guide
└── ARCHITECTURE.md              This file
```

## Connector Selection

The end user's Magento platform type and API availability determines which connector to use:

```
What type of Magento?
│
├─ Self-Hosted / On-Prem
│  ├─ GraphQL available  →  connectors/on-prem-graphql/   (RECOMMENDED)
│  └─ GraphQL blocked    →  connectors/on-prem-rest/
│
└─ Commerce Cloud (*.magentosite.cloud)
   ├─ GraphQL available  →  connectors/cloud-graphql/     (RECOMMENDED)
   └─ GraphQL blocked    →  connectors/cloud-rest/
```

### Why Two Axes?

**Platform (on-prem vs cloud)** determines authentication:
- On-prem uses Magento customer tokens (`POST /rest/V1/integration/customer/token` with email/password)
- Cloud uses Adobe IMS OAuth (`POST https://ims-na1.adobelogin.com/ims/token/v3` with client_id/client_secret)

**API (GraphQL vs REST)** determines extraction capability:
- GraphQL retrieves the full company structure in 1-2 calls with complete user-role resolution
- REST requires 5-7+ calls and cannot resolve user-role assignments (requires a gap strategy)

## Component Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Connector                          │
│  run.py → orchestrator.py → magento_client.py        │
│                              entity_extractor.py      │
│                              application_builder.py   │
│                              relationship_builder.py  │
│                              [ims_auth.py] (cloud)    │
│                              [role_gap_handler.py]    │
│                                  (REST only)          │
└───────────────────┬──────────────────────────────────┘
                    │ imports
┌───────────────────▼──────────────────────────────────┐
│              shared (magento-oaa-shared)              │
│  VezaClient          — OAA provider lifecycle        │
│  ProviderRegistry    — Persist provider IDs          │
│  OutputManager       — Timestamped output + cleanup  │
│  PreflightChecker    — Conflict detection pre-push   │
│  permissions.py      — 34 ACL resource catalog       │
│  BaseApplicationBuilder — OAA property definitions   │
│  push_helper.py      — End-to-end push orchestration │
└───────────────────┬──────────────────────────────────┘
                    │ depends on
              ┌─────▼─────┐
              │ oaaclient │  (Veza SDK, PyPI)
              └───────────┘
```

### What's Shared vs Connector-Specific

| Concern | Location | Rationale |
|---------|----------|-----------|
| Veza push lifecycle | `shared/` | Identical across all connectors |
| ACL permissions (34 resources) | `shared/` | Same B2B permission set |
| Output management | `shared/` | Same timestamped folder + retention logic |
| Preflight conflict checks | `shared/` | Same Veza provider validation |
| OAA base property definitions | `shared/` | Same custom properties on all OAA objects |
| API client | Each connector | Different auth (token vs IMS), different API (GraphQL vs REST) |
| Entity extraction | Each connector | GraphQL response shape differs from REST |
| Pipeline orchestration | Each connector | 7 steps (GraphQL) vs 11 steps (REST) |
| Role gap handling | REST connectors only | GraphQL has native user-role resolution |
| IMS authentication | Cloud connectors only | On-prem uses customer tokens |

## Data Flow

### GraphQL Pipeline (7 steps)

```
Authenticate → GraphQL Query → [REST Role Supplement] → Extract Entities
    → Build OAA Application → Build Relationships → Save/Push
```

### REST Pipeline (11 steps)

```
Authenticate → Get User → Get Company → Get Roles → Get Hierarchy → Get Teams
    → Extract Entities → Handle User-Role Gap → Build OAA Application
    → Build Relationships → Save/Push
```

## OAA Data Model

All connectors produce the same Veza output:

```
CustomApplication
├── LocalGroup (company)
│   ├── LocalGroup (team)
│   │   └── LocalUser (customer)
│   └── LocalUser (customer)
├── LocalRole (company role)
│   └── CustomPermission (ACL resource, e.g. Magento_Sales::place_order)
└── Relationships
    ├── User → Company (membership)
    ├── User → Team (membership)
    ├── User → Role (assignment)
    ├── Role → Permission (ACL allow)
    ├── Team → Company (nesting)
    └── User → User (reports-to)
```

## AWS Test Environment

### Current State

| Component | Details |
|-----------|---------|
| Instance | `i-028422b8abdd9f6a4` (t3.medium, us-east-2) |
| OS | Amazon Linux 2023 |
| Magento | CE 2.4.7 (Community Edition) |
| Stack | Nginx 1.28, PHP 8.2, MariaDB 10.5, Redis 6, OpenSearch 2.x |
| Data | 10 customers, 12 products, 10 orders, 322 REST routes |
| Access | SSM Session Manager (no SSH, corporate proxy blocks SSH) |
| Auto-stop | CloudWatch alarm after 10 min CPU < 5% |

### CE vs Adobe Commerce Gap

The deployed Magento CE does **not** include B2B endpoints. The following return 404 on CE:

| B2B Endpoint | Purpose |
|--------------|---------|
| `GET /rest/V1/company/{id}` | Company details |
| `GET /rest/V1/company/role` | Role definitions + ACL permissions |
| `GET /rest/V1/hierarchy/{id}` | Organizational hierarchy tree |
| `GET /rest/V1/team/{id}` | Team details |
| `POST /graphql` `{ company { ... } }` | GraphQL company query |

To run the connectors end-to-end, we need either:
1. Adobe Commerce (EE) keys to install the B2B extension
2. A mock/stub layer that simulates B2B API responses on CE

### Build Priority

| Priority | Action | Why |
|----------|--------|-----|
| 1 | `on-prem-graphql` | Recommended connector, maps to EC2 deployment, fewest API calls |
| 2 | `on-prem-rest` | Same auth, validates REST fallback path |
| 3 | Resolve B2B gap | Get Adobe Commerce keys or build mock endpoints |
| 4 | `cloud-graphql` | Requires separate Commerce Cloud environment |
| 5 | `cloud-rest` | Same as cloud-graphql but REST fallback |

## Test Coverage

| Component | Test Files | Tests |
|-----------|-----------|-------|
| `connectors/on-prem-graphql/` | 4 | orchestrator, entity_extractor, application_builder, relationship_builder |
| `connectors/on-prem-rest/` | 5 | + role_gap_handler |
| `connectors/cloud-graphql/` | 4 | + ims_auth |
| `connectors/cloud-rest/` | 5 | + ims_auth, role_gap_handler |
| `shared/` | 4 | application_builder_base, permissions, preflight_checker, push_helper |

All connector tests run from within the connector directory (`cd connectors/<name> && pytest tests/`).
Shared tests run from repo root (`pytest shared/tests/`).

## Dependencies

```
connectors/on-prem-graphql/  ─┐
connectors/on-prem-rest/     ─┤
connectors/cloud-graphql/    ─┤── shared (magento-oaa-shared) ── oaaclient (PyPI)
connectors/cloud-rest/       ─┘                                  requests (PyPI)

reference/odie-oaa/          ── oaaclient (PyPI, standalone, no shared dependency)
```

All four connectors reference the shared library via `requirements.txt`:
```
magento-oaa-shared @ file://../../shared
```
