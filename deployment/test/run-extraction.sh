#!/usr/bin/env bash
# =============================================================================
# run-extraction.sh — Lightweight B2B data extraction (50 records per entity)
#
# Pulls company structure, users, teams, roles, and permissions directly via
# curl and saves each entity type as a separate JSON in a timestamped output
# folder matching the project convention: YYYYMMDD_HHMM_{label}
#
# Note on the 50-record limit:
#   The GraphQL company.structure query has NO server-side pagination — Magento
#   returns ALL structure items in one response. The 50-record cap is applied
#   client-side by jq after download. For companies with hundreds of users the
#   full response is still fetched over the network; the limit only controls
#   how many records are saved to disk. The REST /company/role endpoint does
#   support server-side pageSize, so that limit is real.
#
# Prerequisites: curl, jq
#
# Usage:
#   # With env vars:
#   MAGENTO_URL=https://magento.example.com \
#   COMPANY_ADMIN_EMAIL=admin@company.com \
#   COMPANY_ADMIN_PASSWORD=secret \
#   MAGENTO_ADMIN_USER=admin \
#   MAGENTO_ADMIN_PASS=secret \
#   ./run-extraction.sh
#
#   # Interactive (prompts for missing values):
#   ./run-extraction.sh
# =============================================================================
set -euo pipefail

PAGE_SIZE=50

# -- Paths --------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# -- Colors -------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'

# -- Dependency check ---------------------------------------------------------
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}ERROR: '$cmd' is required but not installed.${NC}" >&2
    exit 1
  fi
done

# -- Helper: build JSON auth payload safely with jq --------------------------
auth_payload() {
  jq -n --arg u "$1" --arg p "$2" '{username: $u, password: $p}'
}

# -- Collect credentials ------------------------------------------------------
prompt_if_missing() {
  local var_name="$1" prompt_text="$2" is_secret="${3:-false}"
  if [[ -z "${!var_name:-}" ]]; then
    if [[ "$is_secret" == "true" ]]; then
      read -rsp "$prompt_text: " "$var_name"
      echo
    else
      read -rp "$prompt_text: " "$var_name"
    fi
  fi
}

prompt_if_missing MAGENTO_URL            "Magento base URL (e.g. https://magento.example.com)"
prompt_if_missing COMPANY_ADMIN_EMAIL    "Company admin email"
prompt_if_missing COMPANY_ADMIN_PASSWORD "Company admin password" true
prompt_if_missing MAGENTO_ADMIN_USER     "Magento admin username"
prompt_if_missing MAGENTO_ADMIN_PASS     "Magento admin password" true

# Strip trailing slash from URL
MAGENTO_URL="${MAGENTO_URL%/}"

# -- Create output directory (YYYYMMDD_HHMMSS to avoid same-minute collisions)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_BASE="${REPO_ROOT}/deployment/test/output"
OUTPUT_DIR="${OUTPUT_BASE}/${TIMESTAMP}_B2B_Extraction"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "========================================"
echo "B2B DATA EXTRACTION (limit: ${PAGE_SIZE} per entity)"
echo "========================================"
echo "  Target:  ${MAGENTO_URL}"
echo "  Output:  ${OUTPUT_DIR}"
echo ""

# =============================================================================
# Step 1: Authenticate
# =============================================================================
echo "Step 1/5: Authenticating"
echo "---"

# Customer token (company admin — for GraphQL)
# Capture curl exit code separately to avoid pipe masking failures.
CUSTOMER_TOKEN_RAW=""
CURL_EXIT=0
CUSTOMER_TOKEN_RAW=$(curl -sf -X POST \
  "${MAGENTO_URL}/rest/V1/integration/customer/token" \
  -H "Content-Type: application/json" \
  -d "$(auth_payload "$COMPANY_ADMIN_EMAIL" "$COMPANY_ADMIN_PASSWORD")" 2>&1) || CURL_EXIT=$?

if [[ $CURL_EXIT -ne 0 ]]; then
  if [[ $CURL_EXIT -eq 60 || $CURL_EXIT -eq 35 ]]; then
    echo -e "${RED}ERROR: TLS/certificate error (exit $CURL_EXIT). Self-signed cert? Try http:// or verify CA.${NC}"
  else
    echo -e "${RED}ERROR: Customer auth failed (curl exit $CURL_EXIT)${NC}"
  fi
  exit 1
fi

# Check for Magento error object
if echo "$CUSTOMER_TOKEN_RAW" | jq -e '.message' &>/dev/null 2>&1; then
  echo -e "${RED}ERROR: $(echo "$CUSTOMER_TOKEN_RAW" | jq -r '.message')${NC}"
  exit 1
fi

CUSTOMER_TOKEN=$(echo "$CUSTOMER_TOKEN_RAW" | jq -r '.')
if [[ -z "$CUSTOMER_TOKEN" || "$CUSTOMER_TOKEN" == "null" ]]; then
  echo -e "${RED}ERROR: Empty customer token returned${NC}"; exit 1
fi
echo "  Customer token: OK"

# Admin token (for REST endpoints)
ADMIN_TOKEN_RAW=""
CURL_EXIT=0
ADMIN_TOKEN_RAW=$(curl -sf -X POST \
  "${MAGENTO_URL}/rest/V1/integration/admin/token" \
  -H "Content-Type: application/json" \
  -d "$(auth_payload "$MAGENTO_ADMIN_USER" "$MAGENTO_ADMIN_PASS")" 2>&1) || CURL_EXIT=$?

if [[ $CURL_EXIT -ne 0 ]]; then
  echo -e "${RED}ERROR: Admin auth failed (curl exit $CURL_EXIT)${NC}"; exit 1
fi

if echo "$ADMIN_TOKEN_RAW" | jq -e '.message' &>/dev/null 2>&1; then
  echo -e "${RED}ERROR: $(echo "$ADMIN_TOKEN_RAW" | jq -r '.message')${NC}"
  exit 1
fi

ADMIN_TOKEN=$(echo "$ADMIN_TOKEN_RAW" | jq -r '.')
if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  echo -e "${RED}ERROR: Empty admin token returned${NC}"; exit 1
fi
echo "  Admin token:    OK"

# =============================================================================
# Step 2: Extract company + structure via GraphQL
# =============================================================================
echo ""
echo "Step 2/5: Extracting company structure (GraphQL)"
echo "---"

EXTRACTION_QUERY='query VezaExtraction { customer { email firstname lastname } company { id name legal_name email company_admin { email firstname lastname } legal_address { street city region { region_code } postcode country_code telephone } structure { items { id parent_id entity { __typename ... on Customer { email firstname lastname job_title telephone status created_at role { id name } team { id name structure_id } } ... on CompanyTeam { id name description } } } } } }'

# Use jq to safely build the JSON payload (avoids query string escaping issues)
GQL_PAYLOAD=$(jq -n --arg q "$EXTRACTION_QUERY" '{query: $q}')

CURL_EXIT=0
GQL_RESPONSE=$(curl -sf -X POST "${MAGENTO_URL}/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CUSTOMER_TOKEN}" \
  -d "$GQL_PAYLOAD" 2>&1) || CURL_EXIT=$?

if [[ $CURL_EXIT -ne 0 ]]; then
  echo -e "${RED}ERROR: GraphQL extraction failed (curl exit $CURL_EXIT)${NC}"; exit 1
fi

# Check for errors
if echo "$GQL_RESPONSE" | jq -e '.errors' &>/dev/null; then
  echo -e "${RED}ERROR: $(echo "$GQL_RESPONSE" | jq -r '.errors[0].message')${NC}"
  exit 1
fi

# -- Save company.json --------------------------------------------------------
echo "$GQL_RESPONSE" | jq '{
  id:            .data.company.id,
  name:          .data.company.name,
  legal_name:    .data.company.legal_name,
  email:         .data.company.email,
  company_admin: .data.company.company_admin,
  legal_address: .data.company.legal_address
}' > "${OUTPUT_DIR}/company.json"

COMPANY_NAME=$(jq -r '.name' "${OUTPUT_DIR}/company.json")
COMPANY_ID=$(jq -r '.id' "${OUTPUT_DIR}/company.json")
echo "  company.json — ${COMPANY_NAME}"

# Count totals before truncation so the user knows what was left behind
TOTAL_USERS=$(echo "$GQL_RESPONSE" | jq '[.data.company.structure.items[] | select(.entity.__typename == "Customer")] | length')
TOTAL_TEAMS=$(echo "$GQL_RESPONSE" | jq '[.data.company.structure.items[] | select(.entity.__typename == "CompanyTeam")] | length')
TOTAL_ITEMS=$(echo "$GQL_RESPONSE" | jq '.data.company.structure.items | length')

# -- Save users.json (first PAGE_SIZE) ----------------------------------------
echo "$GQL_RESPONSE" | jq --argjson limit "$PAGE_SIZE" '[
  .data.company.structure.items[]
  | select(.entity.__typename == "Customer")
  | {
      structure_id: .id,
      parent_id:    .parent_id,
      email:        .entity.email,
      firstname:    .entity.firstname,
      lastname:     .entity.lastname,
      job_title:    .entity.job_title,
      telephone:    .entity.telephone,
      status:       .entity.status,
      created_at:   .entity.created_at,
      role_id:      .entity.role.id,
      role_name:    .entity.role.name,
      team_id:      .entity.team.id,
      team_name:    .entity.team.name
    }
] | .[:$limit]' > "${OUTPUT_DIR}/users.json"

USER_COUNT=$(jq 'length' "${OUTPUT_DIR}/users.json")
TRUNCATED_USERS=""
if [[ "$TOTAL_USERS" -gt "$PAGE_SIZE" ]]; then
  TRUNCATED_USERS=" (truncated from ${TOTAL_USERS})"
fi
echo "  users.json — ${USER_COUNT} users${TRUNCATED_USERS}"

# -- Save teams.json (first PAGE_SIZE) ----------------------------------------
echo "$GQL_RESPONSE" | jq --argjson limit "$PAGE_SIZE" '[
  .data.company.structure.items[]
  | select(.entity.__typename == "CompanyTeam")
  | {
      structure_id: .id,
      parent_id:    .parent_id,
      id:           .entity.id,
      name:         .entity.name,
      description:  .entity.description
    }
] | .[:$limit]' > "${OUTPUT_DIR}/teams.json"

TEAM_COUNT=$(jq 'length' "${OUTPUT_DIR}/teams.json")
TRUNCATED_TEAMS=""
if [[ "$TOTAL_TEAMS" -gt "$PAGE_SIZE" ]]; then
  TRUNCATED_TEAMS=" (truncated from ${TOTAL_TEAMS})"
fi
echo "  teams.json — ${TEAM_COUNT} teams${TRUNCATED_TEAMS}"

# -- Save structure.json (ALL nodes — not truncated) ---------------------------
# The hierarchy must be complete for parent_id references in users/teams to
# resolve. Truncating structure would orphan nodes. Users and teams are capped
# independently above.
echo "$GQL_RESPONSE" | jq '[
  .data.company.structure.items[]
  | {
      id:        .id,
      parent_id: .parent_id,
      type:      .entity.__typename
    }
]' > "${OUTPUT_DIR}/structure.json"

STRUCTURE_COUNT=$(jq 'length' "${OUTPUT_DIR}/structure.json")
echo "  structure.json — ${STRUCTURE_COUNT} nodes (full hierarchy, not truncated)"

# =============================================================================
# Step 3: Extract roles via REST (with permissions)
# =============================================================================
echo ""
echo "Step 3/5: Extracting roles via REST"
echo "---"

# Decode the GraphQL base64 company ID to numeric for the REST filter.
# Magento GraphQL returns IDs like "MQ==" (base64 of "1").
COMPANY_ID_NUMERIC=""
if [[ -n "$COMPANY_ID" && "$COMPANY_ID" != "null" ]]; then
  COMPANY_ID_NUMERIC=$(echo "$COMPANY_ID" | base64 --decode 2>/dev/null || echo "$COMPANY_ID" | base64 -d 2>/dev/null || echo "")
fi

CURL_EXIT=0
if [[ -n "$COMPANY_ID_NUMERIC" && "$COMPANY_ID_NUMERIC" =~ ^[0-9]+$ ]]; then
  # Filter by company_id so we only get roles for THIS company (not all companies)
  ROLES_RESPONSE=$(curl -sf \
    "${MAGENTO_URL}/rest/V1/company/role?searchCriteria[pageSize]=${PAGE_SIZE}&searchCriteria[filter_groups][0][filters][0][field]=company_id&searchCriteria[filter_groups][0][filters][0][value]=${COMPANY_ID_NUMERIC}&searchCriteria[filter_groups][0][filters][0][condition_type]=eq" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" 2>&1) || CURL_EXIT=$?
else
  # Fallback: no company_id filter (may return roles from all companies)
  echo "  Note: Could not decode company_id — fetching all roles"
  ROLES_RESPONSE=$(curl -sf \
    "${MAGENTO_URL}/rest/V1/company/role?searchCriteria[pageSize]=${PAGE_SIZE}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" 2>&1) || CURL_EXIT=$?
fi

if [[ $CURL_EXIT -ne 0 ]]; then
  echo -e "${YELLOW}WARNING: REST /company/role failed (curl exit $CURL_EXIT) — skipping${NC}"
  echo '[]' > "${OUTPUT_DIR}/roles.json"
  ROLE_COUNT=0
elif echo "$ROLES_RESPONSE" | jq -e '.message' &>/dev/null 2>&1; then
  echo -e "${YELLOW}WARNING: $(echo "$ROLES_RESPONSE" | jq -r '.message') — skipping${NC}"
  echo '[]' > "${OUTPUT_DIR}/roles.json"
  ROLE_COUNT=0
else
  echo "$ROLES_RESPONSE" | jq '.items // []' > "${OUTPUT_DIR}/roles.json"
  ROLE_COUNT=$(jq 'length' "${OUTPUT_DIR}/roles.json")
  echo "  roles.json — ${ROLE_COUNT} roles"
fi

# =============================================================================
# Step 4: Extract permissions per role
# =============================================================================
echo ""
echo "Step 4/5: Extracting role permissions"
echo "---"

if [[ "$ROLE_COUNT" -gt 0 ]]; then
  # Build a permissions file: role_name → [allowed resources]
  jq '[
    .[] | {
      role_id:    .id,
      role_name:  .role_name,
      company_id: .company_id,
      permissions_allow: [.permissions[] | select(.permission == "allow") | .resource_id],
      permissions_deny:  [.permissions[] | select(.permission == "deny")  | .resource_id]
    }
  ]' "${OUTPUT_DIR}/roles.json" > "${OUTPUT_DIR}/permissions.json"

  PERM_COUNT=$(jq '[.[].permissions_allow | length] | add // 0' "${OUTPUT_DIR}/permissions.json")
  echo "  permissions.json — ${ROLE_COUNT} roles, ${PERM_COUNT} total allow entries"
else
  echo '[]' > "${OUTPUT_DIR}/permissions.json"
  echo "  permissions.json — skipped (no roles)"
fi

# =============================================================================
# Step 5: Save extraction metadata
# =============================================================================
echo ""
echo "Step 5/5: Saving metadata"
echo "---"

jq -n \
  --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg url "$MAGENTO_URL" \
  --arg company "$COMPANY_NAME" \
  --argjson users "$USER_COUNT" \
  --argjson teams "$TEAM_COUNT" \
  --argjson roles "$ROLE_COUNT" \
  --argjson nodes "$STRUCTURE_COUNT" \
  --argjson total_users "$TOTAL_USERS" \
  --argjson total_teams "$TOTAL_TEAMS" \
  --argjson total_items "$TOTAL_ITEMS" \
  --argjson limit "$PAGE_SIZE" \
  '{
    extracted_at: $ts,
    store_url:    $url,
    company:      $company,
    record_limit: $limit,
    counts: {
      users:       $users,
      teams:       $teams,
      roles:       $roles,
      structure:   $nodes
    },
    totals_before_truncation: {
      users:       $total_users,
      teams:       $total_teams,
      all_items:   $total_items
    },
    notes: "GraphQL company.structure has no server-side pagination. All items are fetched; users/teams are truncated client-side to record_limit. Structure is kept complete for hierarchy integrity.",
    files: [
      "company.json",
      "users.json",
      "teams.json",
      "structure.json",
      "roles.json",
      "permissions.json",
      "extraction_metadata.json"
    ]
  }' > "${OUTPUT_DIR}/extraction_metadata.json"

echo "  extraction_metadata.json — OK"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "========================================"
echo -e "${GREEN}Extraction complete.${NC}"
echo "========================================"
echo "  Output:  ${OUTPUT_DIR}/"
echo ""
echo "  Files:"
for f in "${OUTPUT_DIR}"/*.json; do
  SIZE=$(du -h "$f" | cut -f1 | xargs)
  echo "    $(basename "$f")  (${SIZE})"
done
echo ""
echo "  Counts:"
echo "    Company:      ${COMPANY_NAME}"
echo "    Users:        ${USER_COUNT}/${TOTAL_USERS} (limit ${PAGE_SIZE})"
echo "    Teams:        ${TEAM_COUNT}/${TOTAL_TEAMS} (limit ${PAGE_SIZE})"
echo "    Roles:        ${ROLE_COUNT} (limit ${PAGE_SIZE})"
echo "    Structure:    ${STRUCTURE_COUNT} (full — not truncated)"
echo "========================================"
