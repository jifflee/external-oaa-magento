# Field Mapping Reference — Magento B2B REST Connector

This document describes how fields from the Magento REST API responses map to Veza OAA `CustomApplication` properties. Use this reference when debugging output data, extending the connector, or verifying that Veza displays the expected values.

---

## LocalUser — Customer

Source: `GET /rest/V1/customers/me` (authenticated user) and hierarchy nodes (`GET /rest/V1/hierarchy/{companyId}`)

> Note: Full profile fields (email, name, job title, telephone, active status) are only available for the authenticated user. All other users discovered via the hierarchy tree are populated with minimal data. See the `entity_extractor.py` note on this REST limitation.

| OAA Property | REST Source Field | Notes |
|---|---|---|
| `name` (unique_id) | `customer.email` | Used as both the display name and unique identifier in OAA. For non-authenticated users, set to `customer_{entity_id}@unknown`. |
| `email` | `customer.email` | Standard email identity. Empty for non-authenticated users. |
| `first_name` | `customer.firstname` | Empty for non-authenticated users. |
| `last_name` | `customer.lastname` | Empty for non-authenticated users. |
| `is_active` | `customer.extension_attributes.company_attributes.status` | `true` when status equals `1`; `false` when `0`. Assumed `true` for non-authenticated users (unknown). |
| `job_title` (custom) | `customer.extension_attributes.company_attributes.job_title` | Empty for non-authenticated users. |
| `telephone` (custom) | `customer.extension_attributes.company_attributes.telephone` | Empty for non-authenticated users. |
| `is_company_admin` (custom) | Derived: `customer.id == company.super_user_id` | `true` if the customer ID matches the company's super user ID. |
| `company_id` (custom) | `customer.extension_attributes.company_attributes.company_id` | String representation of the Magento company ID. |
| `magento_customer_id` (custom) | `customer.id` | Magento's internal integer customer ID, stored as a string. |

### Identity

Each `LocalUser` has a single identity added:

```
identity = customer.email
```

This allows Veza to correlate the Magento user with identity providers that share the same email address.

---

## LocalGroup — Company

Source: `GET /rest/V1/company/{id}`

| OAA Property | REST Source Field | Notes |
|---|---|---|
| `name` | `company.company_name` | Display name of the company in OAA. |
| `unique_id` | Derived: `company_{company.id}` | Prefixed to avoid collisions with team group IDs. |
| `group_type` | Hardcoded: `"company"` | Distinguishes company groups from team groups. |
| `legal_name` (custom) | `company.legal_name` | The registered legal name of the company. |
| `company_email` (custom) | `company.company_email` | The company's primary contact email. |
| `admin_email` (custom) | Derived: email of user whose `magento_customer_id == company.super_user_id` | Resolved after user extraction. Empty if super user is not in the hierarchy or is not the authenticated user. |
| `magento_company_id` (custom) | `company.id` | Magento's internal company ID, stored as a string. |

---

## LocalGroup — Team

Source: `GET /rest/V1/hierarchy/{companyId}` (structure node) combined with `GET /rest/V1/team/{id}` (detail)

| OAA Property | REST Source Field | Notes |
|---|---|---|
| `name` | `team.name` from `GET /V1/team/{id}` | Falls back to `"Team {entity_id}"` if the detail call fails. |
| `unique_id` | Derived: `team_{entity_id}` | Uses the hierarchy node's `entity_id`. |
| `group_type` | Hardcoded: `"team"` | Distinguishes team groups from company groups. |
| `description` (custom) | `team.description` from `GET /V1/team/{id}` | Empty string if not set or if the detail call fails. |
| `magento_team_id` (custom) | `hierarchy_node.entity_id` | Magento's internal team ID. |
| `parent_company_id` (custom) | Derived from company context | The Magento company ID string that owns this team. |

---

## LocalRole — Company Role

Source: `GET /rest/V1/company/role?searchCriteria[...][field]=company_id&[...][value]={company_id}&[...][condition_type]=eq`

| OAA Property | REST Source Field | Notes |
|---|---|---|
| `name` | `role.role_name` | Display name of the role. |
| `unique_id` | Derived: `role_{company_id}_{role.id}` | Includes company ID to ensure uniqueness across companies. |
| `magento_role_id` (custom) | `role.id` | Magento's internal role ID, stored as a string. |
| `company_id` (custom) | `role.company_id` | The Magento company ID this role belongs to. |

---

## CustomPermission — ACL Resource

Source: `role.permissions[]` array from `GET /rest/V1/company/role`

Each role in the REST response includes an explicit list of ACL resource permissions with `allow` or `deny` status:

```json
{
  "resource_id": "Magento_Sales::place_order",
  "permission": "allow"
}
```

Only entries with `"permission": "allow"` are registered as OAA permissions. Entries with `"permission": "deny"` are silently ignored (deny is the default in Veza's model).

| OAA Property | REST Source Field | Notes |
|---|---|---|
| `permission_name` | `perm.resource_id` | The full ACL resource ID string, e.g. `Magento_Sales::place_order`. |
| OAA permission type | Derived from category in `permissions.py` | `OAAPermission.DataRead` for base, company, and credit categories; `OAAPermission.DataWrite` for sales, quotes, purchase_orders, and user management categories. |

---

## Application-Level Properties

The `CustomApplication` object itself carries metadata properties set during construction.

| OAA Property | Source | Notes |
|---|---|---|
| `name` | Derived: `magento_b2b_{company_id}` | Unique application name. |
| `application_type` | Hardcoded: `"Magento B2B"` | Application type label in Veza. |
| `description` | Derived: `"Adobe Commerce B2B - {company_name} (REST)"` | Identifies the source as REST to distinguish from a GraphQL push. |
| `store_url` (custom) | `MAGENTO_STORE_URL` from config | The Magento store base URL. |
| `sync_timestamp` (custom) | Runtime UTC ISO timestamp | When the extraction was performed. |
| `company_name` (custom) | `company.company_name` | Human-readable company name on the application object. |

---

## ACL Permission Catalog

The following 33 ACL resource IDs are recognized by this connector. They are sourced from the Adobe Commerce B2B documentation (`b2b-roles.md`). Permissions not in this catalog that appear in a role's `permissions[]` array are ignored.

| Resource ID | Display Name | Category | OAA Permission Type |
|---|---|---|---|
| `Magento_Company::index` | All Access | base | DataRead |
| `Magento_Sales::all` | Sales | sales | DataWrite |
| `Magento_Sales::place_order` | Allow Checkout | sales | DataWrite |
| `Magento_Sales::payment_account` | Pay On Account | sales | DataWrite |
| `Magento_Sales::view_orders` | View Orders | sales | DataWrite |
| `Magento_Sales::view_orders_sub` | View Subordinate Orders | sales | DataWrite |
| `Magento_NegotiableQuote::all` | Quotes | quotes | DataWrite |
| `Magento_NegotiableQuote::view_quotes` | View Quotes | quotes | DataWrite |
| `Magento_NegotiableQuote::manage` | Manage Quotes | quotes | DataWrite |
| `Magento_NegotiableQuote::checkout` | Checkout Quote | quotes | DataWrite |
| `Magento_NegotiableQuote::view_quotes_sub` | View Subordinate Quotes | quotes | DataWrite |
| `Magento_PurchaseOrder::all` | Order Approvals | purchase_orders | DataWrite |
| `Magento_PurchaseOrder::view_purchase_orders` | View My POs | purchase_orders | DataWrite |
| `Magento_PurchaseOrder::view_purchase_orders_for_subordinates` | View Subordinate POs | purchase_orders | DataWrite |
| `Magento_PurchaseOrder::view_purchase_orders_for_company` | View Company POs | purchase_orders | DataWrite |
| `Magento_PurchaseOrder::autoapprove_purchase_order` | Auto-approve POs | purchase_orders | DataWrite |
| `Magento_PurchaseOrderRule::super_approve_purchase_order` | Super Approve | purchase_orders | DataWrite |
| `Magento_PurchaseOrderRule::view_approval_rules` | View Approval Rules | purchase_orders | DataWrite |
| `Magento_PurchaseOrderRule::manage_approval_rules` | Manage Approval Rules | purchase_orders | DataWrite |
| `Magento_Company::view` | Company Profile | company | DataRead |
| `Magento_Company::view_account` | View Account | company | DataRead |
| `Magento_Company::edit_account` | Edit Account | company | DataRead |
| `Magento_Company::view_address` | View Address | company | DataRead |
| `Magento_Company::edit_address` | Edit Address | company | DataRead |
| `Magento_Company::contacts` | View Contacts | company | DataRead |
| `Magento_Company::payment_information` | View Payment Info | company | DataRead |
| `Magento_Company::shipping_information` | View Shipping Info | company | DataRead |
| `Magento_Company::user_management` | User Management | users | DataWrite |
| `Magento_Company::roles_view` | View Roles | users | DataWrite |
| `Magento_Company::roles_edit` | Manage Roles | users | DataWrite |
| `Magento_Company::users_view` | View Users | users | DataWrite |
| `Magento_Company::users_edit` | Manage Users | users | DataWrite |
| `Magento_Company::credit` | Company Credit | credit | DataRead |
| `Magento_Company::credit_history` | Credit History | credit | DataRead |

> Note: The catalog contains 33 entries. The `permissions.py` source comment references 33 resources; the `Magento_Company::index` base resource brings the count to 33 when `Magento_Company::credit` and `Magento_Company::credit_history` are both included. If a Magento instance returns additional custom ACL resources not in this catalog, they are silently skipped. To add support for additional resources, update `config/permissions.py`.

---

## Hierarchy Node Fields

The hierarchy response is a nested tree structure. Each node is flattened by `entity_extractor.py` into the following fields for internal use:

| Internal Field | REST Source Field | Description |
|---|---|---|
| `structure_id` | `node.structure_id` | Unique position ID in the hierarchy tree. Used as a relationship key. |
| `entity_id` | `node.entity_id` | The ID of the referenced entity (customer ID or team ID). |
| `entity_type` | `node.entity_type` | Either `"customer"` or `"team"` (normalized to lowercase). |
| `structure_parent_id` | `node.structure_parent_id` | The `structure_id` of this node's parent. Used to derive team membership and reports-to relationships. |

---

## Notes for Developers

- The `entity_extractor.py` module normalizes all numeric IDs to strings for consistent comparison throughout the pipeline.
- The `role_gap_handler.py` module populates `role_id` and `role_name` on user entities. These fields are `None` by default because the REST API does not supply them.
- The `relationship_builder.py` module skips user-to-role relationship creation silently when `role_id` is `None`, so all gap strategies are safe to use without changing any other pipeline code.
- The application description includes `(REST)` to make it easy to distinguish REST-sourced applications from GraphQL-sourced ones in the Veza UI, particularly when both connectors are used in testing scenarios.
