# Example Output

This directory contains a sample OAA payload showing the connector's output format.

## `oaa_payload_sample.json`

A realistic example produced by the connector pipeline. Shows 1 company (Acme Corp)
with 2 teams, 4 roles, 5 users, and 34 ACL permissions wired with all 6 relationship
types.

### Top-level structure

| Key | Description |
|-----|-------------|
| `custom_property_definition` | Property schemas for application, user, group, and role entities |
| `applications[]` | The OAA CustomApplication with all entities and properties |
| `permissions[]` | The 34 Magento B2B ACL permission definitions |
| `identity_to_permissions[]` | User-to-role assignments linking identities to permissions |

### Entity types inside `applications[0]`

| Key | Description |
|-----|-------------|
| `local_users[]` | Company users with email, identity, group memberships, and custom properties |
| `local_groups[]` | Company group (type=company) and team groups (type=team) with nesting |
| `local_roles[]` | B2B roles with their allowed ACL permissions |

### Custom properties

**User properties:**
- `job_title` - Magento B2B job title
- `telephone` - Contact phone number
- `is_company_admin` - Whether this user is the company administrator
- `company_id` - Magento company ID
- `reports_to` - Email of the user's manager (from hierarchy)

**Group properties (company):**
- `legal_name` - Company legal name
- `company_email` - Company contact email
- `admin_email` - Company admin's email
- `magento_company_id` - Magento company ID

**Group properties (team):**
- `description` - Team description
- `magento_team_id` - Magento team ID
- `parent_company_id` - Parent company ID

**Role properties:**
- `magento_role_id` - Magento role ID
- `company_id` - Company this role belongs to

### Relationships demonstrated

1. **User -> Company** - Every user belongs to `company_1` group
2. **User -> Team** - Team members belong to `team_1` or `team_2`
3. **User -> Role** - Each user has a role assignment (via `identity_to_permissions`)
4. **Role -> Permission** - Each role lists its allowed ACL permissions
5. **Team -> Company** - Teams are nested under the company group
6. **User -> User** - `reports_to` property shows reporting hierarchy
