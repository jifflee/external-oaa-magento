# REST API Gap Analysis — User-Role Assignment

This document describes the structural limitation in the Magento B2B REST API that prevents the REST connector from determining which role is assigned to each company user. It explains the impact on Veza access queries and documents the four workaround strategies available in this connector.

---

## The Problem

The Magento B2B REST API does not expose user-role assignment data. The gap exists at the following endpoints:

- `GET /rest/V1/customers/me` — Returns the authenticated user's profile, including `extension_attributes.company_attributes`. The `company_attributes` object includes `job_title`, `telephone`, and `status`, but **does not include `role_id` or `role_name`**.

- `GET /rest/V1/customers/{id}` — Returns a customer profile by ID. Same limitation: no `role_id` field in `company_attributes`.

- `GET /rest/V1/hierarchy/{companyId}` — Returns the organizational hierarchy as a nested tree of nodes. Each node identifies its entity type (`customer` or `team`) and entity ID, but contains **no role information for any user**.

- `GET /rest/V1/company/role` — Returns all roles for a company with their full ACL permission lists. This endpoint provides roles and permissions accurately, but **does not list which users hold each role**.

Roles exist in Magento. Users exist in Magento. ACL permissions exist on roles. The REST API simply does not provide the link between users and roles.

### Comparison with GraphQL

The GraphQL connector resolves this completely. The `company { structure { items } }` query returns each `Customer` entity in the company structure with a nested `role` object:

```graphql
entity {
  ... on Customer {
    email
    role {
      id
      name
    }
  }
}
```

This single query gives every user's role assignment in one round trip. The REST API has no equivalent.

---

## Impact on Veza

Without user-role links, Veza cannot answer the following types of access questions for users other than the authenticated connector account:

- "What can user X do in Magento B2B?" — Veza can show the user exists and belongs to the company, but cannot trace their effective permissions through a role.
- "Which users have the Purchaser role?" — Veza can show the role and its permissions, but cannot show which users hold it.
- "Who can approve purchase orders?" — Veza cannot identify the users unless role assignments are supplied through a workaround strategy.

Users appear in the Veza graph and are assigned to their company and team groups. However, without role assignments, the permission layer of the access model is incomplete.

This limitation does not affect the accuracy of role definitions (what permissions each role grants) or team and company structure. Only the user-to-role segment of the access graph is affected.

---

## Workaround Strategies

The connector implements four configurable strategies to handle this gap. Select a strategy based on the accuracy requirements and maintenance capacity of your deployment.

| Strategy | Config Value | Behavior | Accuracy | Maintenance |
|---|---|---|---|---|
| Default Role | `default_role` | Non-admin users are assigned the role named "Default User" (case-insensitive match). The company admin is assigned the first role whose name contains "admin". If no "Default User" role exists, the first role in the list is used as the fallback. | Low to medium. Correct when most users share the default role; incorrect for users with specialized roles such as Purchaser. | None required. |
| CSV Supplement | `csv_supplement` | Reads a CSV file mapping email addresses to role names. Users found in the CSV are assigned the corresponding role. Users not in the CSV fall back to `default_role` behavior. | High, if the CSV is maintained. Accuracy degrades when users change roles and the CSV is not updated. | Manual updates required whenever user role assignments change in Magento. |
| All Roles | `all_roles` | Roles are created in Veza with their full ACL permissions, but no user-role links are established. Users and roles are both present in the graph but are disconnected. | Not applicable. Makes no incorrect claims, but provides no effective permission data. | None required. |
| Skip | `skip` | User-role relationships are omitted entirely. Users appear in Veza with company and team group memberships but no role or permission associations. | Not applicable. The absence of role data is transparent. | None required. |

---

## Recommendations

1. **Use the GraphQL connector if at all possible.** The GraphQL connector resolves the user-role gap completely and requires only 1 to 2 API calls. If GraphQL is available on your Magento instance, it is the preferred integration path.

2. **If REST is required, use `csv_supplement` for the highest accuracy.** Maintain the CSV alongside your Magento user management process. When a user is assigned a new role in Magento, update the CSV and re-run the connector.

3. **Use `default_role` as a pragmatic starting point** for environments where most company users share the same role (a common configuration in simple B2B setups). Review the Veza access graph and validate that the role assignment reflects reality before acting on access query results.

4. **Use `all_roles` when structural visibility is the primary goal.** This strategy correctly represents what roles exist and what they can do, without making incorrect user-role claims. It is useful for auditing role definitions and permissions without asserting who holds each role.

5. **Use `skip` when you want to suppress all role-related data** rather than surface incomplete or potentially incorrect information. This produces the most conservative output.

---

## CSV Format

When using the `csv_supplement` strategy, provide a CSV file at the path configured by `USER_ROLE_MAPPING_PATH` (default: `./data/user_role_mapping.csv`).

Requirements:
- Must have a header row with columns named exactly `email` and `role_name`
- Email values are matched case-insensitively
- Role name values are matched case-insensitively against the roles returned by `GET /V1/company/role`
- Rows with blank email or blank role_name are ignored
- The file must be UTF-8 encoded (UTF-8 with BOM is also accepted)

```csv
email,role_name
user1@acme.com,Default User
user2@acme.com,Purchaser
buyer@acme.com,Senior Buyer
admin@acme.com,Company Administrator
```

If the file is missing or cannot be read when `csv_supplement` is selected, the connector logs a warning and falls back to `default_role` automatically. No extraction fails because of a missing CSV.

---

## REST API Endpoints Used

The following endpoints are called during a single extraction run. All endpoints require a valid customer bearer token obtained from the authentication step.

| Endpoint | Method | Auth Required | Data Returned | Called |
|---|---|---|---|---|
| `/rest/V1/integration/customer/token` | POST | None (credentials in body) | JWT bearer token string | Once per run |
| `/rest/V1/customers/me` | GET | Bearer token | Full profile of the authenticated customer, including `extension_attributes.company_attributes` with `company_id`, `job_title`, `telephone`, `status` | Once per run |
| `/rest/V1/company/{id}` | GET | Bearer token | Company record with `id`, `company_name`, `legal_name`, `company_email`, `super_user_id` | Once per run |
| `/rest/V1/company/role` | GET | Bearer token | List of company roles filtered by `company_id`, each with `id`, `role_name`, `permissions[]` (resource_id + allow/deny) | Once per run |
| `/rest/V1/hierarchy/{companyId}` | GET | Bearer token | Nested hierarchy tree with `structure_id`, `entity_id`, `entity_type` (customer or team), `structure_parent_id`, and `children[]` | Once per run |
| `/rest/V1/team/{id}` | GET | Bearer token | Team detail with `id`, `name`, `description` | Once per team in the hierarchy (N calls) |

### Request Volume

| Scenario | Approximate Request Count |
|---|---|
| Minimal company (no teams) | 5 requests |
| Company with 5 teams | 10 requests |
| Company with 20 teams | 25 requests |
| GraphQL connector (any size) | 1 to 2 requests |

The per-team GET call pattern is a direct consequence of the hierarchy endpoint returning only team IDs. Each team ID requires an individual lookup to retrieve the team name and description.

---

## Technical Background

The REST API limitation is not a bug in this connector — it reflects the design of the Magento B2B REST API. The customer resource schema at `GET /V1/customers/{id}` is a generic customer endpoint that predates the B2B module. The `company_attributes` extension added for B2B includes company membership data but was not extended to include role assignment.

Adobe Commerce's B2B GraphQL API was designed later and exposes the company structure query with full entity details including role assignment. This is why the GraphQL connector is preferred.

There is no publicly documented REST endpoint in Adobe Commerce B2B that lists all users with their role IDs. Admin REST API endpoints (those requiring admin integration tokens rather than customer tokens) may expose additional user management data, but this connector uses customer-scoped authentication by design to match the GraphQL connector's access model.

---

## Related Documentation

- [README.md](README.md) — Setup, configuration, and usage instructions
- [FIELD_MAPPING.md](FIELD_MAPPING.md) — Field-level mapping from REST responses to OAA properties
- `core/role_gap_handler.py` — Implementation of all four gap strategies
- `core/entity_extractor.py` — Notes on the REST hierarchy parsing and the `customer_{id}@unknown` fallback for non-authenticated users
