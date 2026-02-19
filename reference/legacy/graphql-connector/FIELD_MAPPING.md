# GraphQL Connector - Field Mapping Reference

This document describes how Magento B2B data fields are mapped from the GraphQL and REST API responses to Veza OAA entity fields. It also provides the complete ACL permission catalog used for role-permission assignments.

---

## LocalUser

Each `Customer` entity in `company.structure.items` is mapped to a Veza `LocalUser`.

The user's email address is used as both the `name` and `unique_id`. This ensures stable identity matching across connector runs and enables Veza to correlate users with identities from other connected systems.

| OAA Field | GraphQL Source Path | Type | Example Value |
|---|---|---|---|
| `name` | `entity.email` | String | `buyer@example.com` |
| `unique_id` | `entity.email` | String | `buyer@example.com` |
| `email` | `entity.email` | String | `buyer@example.com` |
| `first_name` | `entity.firstname` | String | `Jane` |
| `last_name` | `entity.lastname` | String | `Smith` |
| `is_active` | `entity.status == "ACTIVE"` | Boolean | `true` |
| `identity` | `entity.email` (via `add_identity`) | String | `buyer@example.com` |
| `job_title` _(custom)_ | `entity.job_title` | String | `Procurement Manager` |
| `telephone` _(custom)_ | `entity.telephone` | String | `+1-555-0100` |
| `is_company_admin` _(custom)_ | `entity.email == company.company_admin.email` | Boolean | `false` |
| `company_id` _(custom)_ | Decoded `company.id` | String | `6` |

**Notes:**
- `is_active` is derived by comparing `entity.status` to the string `"ACTIVE"`. Any other status value (including a missing field) is treated as inactive.
- `is_company_admin` is determined at extraction time by comparing the user's email to `company.company_admin.email` (case-insensitive).
- `job_title` and `telephone` are only set when non-empty to avoid storing empty string properties.
- The `identity` claim links this user to identity providers in Veza. The email is registered as the identity value.

---

## LocalGroup (Company)

The top-level `company` object in the GraphQL response is mapped to a single `LocalGroup` with `group_type="company"`.

| OAA Field | GraphQL Source Path | Type | Example Value |
|---|---|---|---|
| `name` | `company.name` | String | `Acme Corp` |
| `unique_id` | `"company_" + decoded(company.id)` | String | `company_6` |
| `legal_name` _(custom)_ | `company.legal_name` | String | `Acme Corporation LLC` |
| `company_email` _(custom)_ | `company.email` | String | `billing@acme.example.com` |
| `admin_email` _(custom)_ | `company.company_admin.email` | String | `admin@acme.example.com` |
| `magento_company_id` _(custom)_ | Decoded `company.id` | String | `6` |

**Notes:**
- The `unique_id` uses the `company_` prefix to prevent collisions with team IDs in the same application.
- `company.id` in the GraphQL response is a base64-encoded string (e.g., `"Ng=="` decodes to `"6"`). The connector decodes all such IDs before use.
- There is exactly one company group per extraction run. The connector authenticates as a single company admin, so only one company is accessible per run.

---

## LocalGroup (Team)

Each `CompanyTeam` entity in `company.structure.items` is mapped to a `LocalGroup` with `group_type="team"`.

| OAA Field | GraphQL Source Path | Type | Example Value |
|---|---|---|---|
| `name` | `entity.name` | String | `West Coast Sales` |
| `unique_id` | `"team_" + decoded(entity.id)` | String | `team_3` |
| `description` _(custom)_ | `entity.description` | String | `Handles Pacific region accounts` |
| `magento_team_id` _(custom)_ | Decoded `entity.id` | String | `3` |
| `parent_company_id` _(custom)_ | Decoded `company.id` | String | `6` |

**Notes:**
- The `unique_id` uses the `team_` prefix to prevent collisions with the company group ID.
- The parent-child relationship between a team and the company is established separately via `RelationshipBuilder` (Relationship 5: Team -> Company), not through these properties.
- Teams may be nested within other teams in Magento's structure tree, but the OAA model associates each team directly with the company group.

---

## LocalRole

Roles are discovered by scanning `entity.role` on each `Customer` entity. Because multiple users may share the same role, roles are deduplicated by `role_id` during extraction.

| OAA Field | GraphQL Source Path | Type | Example Value |
|---|---|---|---|
| `name` | `entity.role.name` | String | `Buyer` |
| `unique_id` | `"role_" + company_id + "_" + decoded(entity.role.id)` | String | `role_6_2` |
| `magento_role_id` _(custom)_ | Decoded `entity.role.id` | String | `2` |
| `company_id` _(custom)_ | Decoded `company.id` | String | `6` |

**Notes:**
- The `unique_id` includes both the company ID and the role ID to ensure global uniqueness across multi-company deployments within a single Veza tenant.
- Role IDs in GraphQL are base64-encoded (e.g., `"Mg=="` decodes to `"2"`).
- Permissions are not available from GraphQL alone. The REST role supplement (`GET /rest/V1/company/role`) provides explicit allow/deny per ACL resource. See the [Permissions](#permission) section and the REST Role Supplement description in the README.
- If the REST supplement is disabled, roles will appear in Veza without permission assignments.

---

## Permission

The connector predefines 34 ACL resources as `CustomPermission` objects on the application. These resource IDs match the values returned by both the Magento GraphQL and REST APIs.

Permission names in OAA are set to the `resource_id` string (e.g., `Magento_Sales::place_order`). Display names and categories are defined in `config/permissions.py` and are used for grouping and OAA permission type assignment.

**OAA Permission Type mapping by category:**

| Category | OAA Permission Type |
|---|---|
| base | `DataRead` |
| sales | `DataWrite` |
| quotes | `DataWrite` |
| purchase_orders | `DataWrite` |
| company | `DataRead` |
| users | `DataWrite` |
| credit | `DataRead` |

---

### Full ACL Permission Catalog (34 resources)

> **Important:** Three resources in the Purchase Orders category use the `Magento_PurchaseOrderRule::` namespace prefix (not `Magento_PurchaseOrder::`). This matches the official Adobe Commerce B2B documentation and the values returned by the Magento API. Using the wrong namespace prefix will cause permission lookups to fail silently.

| Resource ID | Display Name | Category |
|---|---|---|
| `Magento_Company::index` | All Access | Base |
| `Magento_Sales::all` | Sales | Sales |
| `Magento_Sales::place_order` | Allow Checkout | Sales |
| `Magento_Sales::payment_account` | Pay On Account | Sales |
| `Magento_Sales::view_orders` | View Orders | Sales |
| `Magento_Sales::view_orders_sub` | View Subordinate Orders | Sales |
| `Magento_NegotiableQuote::all` | Quotes | Quotes |
| `Magento_NegotiableQuote::view_quotes` | View Quotes | Quotes |
| `Magento_NegotiableQuote::manage` | Manage Quotes | Quotes |
| `Magento_NegotiableQuote::checkout` | Checkout Quote | Quotes |
| `Magento_NegotiableQuote::view_quotes_sub` | View Subordinate Quotes | Quotes |
| `Magento_PurchaseOrder::all` | Order Approvals | Purchase Orders |
| `Magento_PurchaseOrder::view_purchase_orders` | View My POs | Purchase Orders |
| `Magento_PurchaseOrder::view_purchase_orders_for_subordinates` | View Subordinate POs | Purchase Orders |
| `Magento_PurchaseOrder::view_purchase_orders_for_company` | View Company POs | Purchase Orders |
| `Magento_PurchaseOrder::autoapprove_purchase_order` | Auto-approve POs | Purchase Orders |
| `Magento_PurchaseOrderRule::super_approve_purchase_order` | Super Approve | Purchase Orders |
| `Magento_PurchaseOrderRule::view_approval_rules` | View Approval Rules | Purchase Orders |
| `Magento_PurchaseOrderRule::manage_approval_rules` | Manage Approval Rules | Purchase Orders |
| `Magento_Company::view` | Company Profile | Company |
| `Magento_Company::view_account` | View Account | Company |
| `Magento_Company::edit_account` | Edit Account | Company |
| `Magento_Company::view_address` | View Address | Company |
| `Magento_Company::edit_address` | Edit Address | Company |
| `Magento_Company::contacts` | View Contacts | Company |
| `Magento_Company::payment_information` | View Payment Info | Company |
| `Magento_Company::shipping_information` | View Shipping Info | Company |
| `Magento_Company::user_management` | User Management | Users |
| `Magento_Company::roles_view` | View Roles | Users |
| `Magento_Company::roles_edit` | Manage Roles | Users |
| `Magento_Company::users_view` | View Users | Users |
| `Magento_Company::users_edit` | Manage Users | Users |
| `Magento_Company::credit` | Company Credit | Credit |
| `Magento_Company::credit_history` | Credit History | Credit |

---

## Namespace Reference

| Namespace | Entity Domain | Count |
|---|---|---|
| `Magento_Company::` | Company profile, user management, and credit | 14 |
| `Magento_Sales::` | Order placement and viewing | 5 |
| `Magento_NegotiableQuote::` | Quote management | 5 |
| `Magento_PurchaseOrder::` | Purchase order workflow | 6 |
| `Magento_PurchaseOrderRule::` | Purchase order approval rules | 3 |
| **Total** | | **33** |

> **Note:** The source code comment in `config/permissions.py` states "33 resources" but the file defines 34 entries. The discrepancy exists because the comment was not updated when a resource was added. The authoritative count is 34 as defined in `MAGENTO_ACL_PERMISSIONS`.

---

## GraphQL ID Decoding

Magento GraphQL returns entity IDs as base64-encoded strings. The `decode_graphql_id` function in `core/entity_extractor.py` decodes these before use.

| Raw GraphQL ID | Decoded Value | Usage |
|---|---|---|
| `"MQ=="` | `"1"` | Company, team, or role with numeric ID 1 |
| `"Mg=="` | `"2"` | Numeric ID 2 |
| `"Ng=="` | `"6"` | Numeric ID 6 |

Decoded IDs are stored as strings (not integers) throughout the connector to ensure consistent key formatting and to avoid type mismatch errors when constructing unique IDs.

---

## REST Role Supplement Field Mapping

When `USE_REST_ROLE_SUPPLEMENT=true`, the connector calls `GET /rest/V1/company/role` and maps the response as follows.

**REST response structure (per role):**

```json
{
  "id": 2,
  "role_name": "Buyer",
  "company_id": 6,
  "permissions": [
    {"resource_id": "Magento_Sales::place_order", "permission": "allow"},
    {"resource_id": "Magento_Sales::view_orders", "permission": "allow"},
    {"resource_id": "Magento_Sales::view_orders_sub", "permission": "deny"}
  ]
}
```

**Field mapping from REST to OAA:**

| REST Field | Used For | Notes |
|---|---|---|
| `id` | Matches to `LocalRole.unique_id` via `role_{company_id}_{id}` | Integer, converted to string |
| `role_name` | Display verification only | Not written back to OAA; role name comes from GraphQL |
| `company_id` | Part of `LocalRole.unique_id` construction | Integer, converted to string |
| `permissions[].resource_id` | Identifies the `CustomPermission` to link | Must exactly match an entry in the ACL catalog |
| `permissions[].permission` | Determines whether to create an OAA grant | Only `"allow"` creates a link; `"deny"` is ignored |
