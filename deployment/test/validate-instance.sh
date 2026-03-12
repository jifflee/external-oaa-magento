#!/usr/bin/env bash
# =============================================================================
# validate-instance.sh — 5-stage validation of a target Adobe Commerce instance
#
# Confirms connectivity, authentication, B2B module availability, GraphQL
# extraction compatibility, and REST role permissions before running the
# connector.
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
#   ./validate-instance.sh
#
#   # Interactive (prompts for missing values):
#   ./validate-instance.sh
# =============================================================================
set -euo pipefail

# -- Colors / symbols --------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
PASS="${GREEN}✓ PASS${NC}"
FAIL="${RED}✗ FAIL${NC}"
WARN="${YELLOW}⚠ WARN${NC}"

# -- Dependency check ---------------------------------------------------------
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}ERROR: '$cmd' is required but not installed.${NC}" >&2
    exit 1
  fi
done

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

prompt_if_missing MAGENTO_URL          "Magento base URL (e.g. https://magento.example.com)"
prompt_if_missing COMPANY_ADMIN_EMAIL  "Company admin email"
prompt_if_missing COMPANY_ADMIN_PASSWORD "Company admin password" true
prompt_if_missing MAGENTO_ADMIN_USER   "Magento admin username"
prompt_if_missing MAGENTO_ADMIN_PASS   "Magento admin password" true

# Strip trailing slash from URL
MAGENTO_URL="${MAGENTO_URL%/}"

# -- Helper: build JSON auth payload safely with jq --------------------------
auth_payload() {
  jq -n --arg u "$1" --arg p "$2" '{username: $u, password: $p}'
}

# -- Helper: portable base64 decode ------------------------------------------
b64decode() {
  base64 --decode 2>/dev/null || base64 -d 2>/dev/null
}

# -- Result tracking ----------------------------------------------------------
declare -A STAGE_RESULT STAGE_DETAIL
STAGES=("Connectivity" "Authentication" "B2B Module" "GraphQL Extraction" "REST Permissions")

fail_stage() {
  local stage="$1" detail="$2"
  STAGE_RESULT["$stage"]="FAIL"
  STAGE_DETAIL["$stage"]="$detail"
  print_summary
  exit 1
}

warn_stage() {
  local stage="$1" detail="$2"
  STAGE_RESULT["$stage"]="WARN"
  STAGE_DETAIL["$stage"]="$detail"
}

pass_stage() {
  local stage="$1" detail="$2"
  STAGE_RESULT["$stage"]="PASS"
  STAGE_DETAIL["$stage"]="$detail"
}

print_summary() {
  echo ""
  echo "========================================"
  echo "VALIDATION SUMMARY"
  echo "========================================"
  for stage in "${STAGES[@]}"; do
    local result="${STAGE_RESULT[$stage]:-SKIP}"
    local detail="${STAGE_DETAIL[$stage]:-}"
    local symbol
    case "$result" in
      PASS) symbol="$PASS" ;;
      FAIL) symbol="$FAIL" ;;
      WARN) symbol="$WARN" ;;
      *)    symbol="  SKIP" ;;
    esac
    printf "  %-26s %b  (%s)\n" "Stage: $stage" "$symbol" "$detail"
  done
  echo "========================================"

  # Check if all required stages passed
  local all_pass=true
  for stage in "${STAGES[@]}"; do
    local result="${STAGE_RESULT[$stage]:-SKIP}"
    if [[ "$result" == "FAIL" ]]; then
      all_pass=false
      break
    fi
  done

  if $all_pass; then
    echo -e "${GREEN}Instance is ready for extraction.${NC}"
    echo "Run: ./run-extraction.sh"
  else
    echo -e "${RED}Validation failed. Fix the issues above and retry.${NC}"
  fi
  echo "========================================"
}

# -- Helper: curl with TLS error detection ------------------------------------
# Runs curl and captures both stdout and exit code. On failure, checks whether
# it's a TLS/cert issue and provides an actionable hint.
curl_or_fail() {
  local label="$1"; shift
  local http_output=""
  local curl_exit=0

  http_output=$(curl "$@" 2>&1) || curl_exit=$?

  if [[ $curl_exit -ne 0 ]]; then
    # curl exit 60 = SSL cert problem, 35 = SSL connect error
    if [[ $curl_exit -eq 60 || $curl_exit -eq 35 ]]; then
      fail_stage "$label" "TLS/certificate error (exit $curl_exit). Self-signed cert? Try: MAGENTO_URL with http:// or add --insecure"
    fi
    fail_stage "$label" "curl failed (exit $curl_exit). Is the URL correct?"
  fi

  echo "$http_output"
}

# =============================================================================
# STAGE 1: Connectivity
# =============================================================================
echo ""
echo "Stage 1/5: Connectivity"
echo "---"

STORE_RESPONSE=$(curl_or_fail "Connectivity" \
  -sf --max-time 10 \
  "${MAGENTO_URL}/rest/V1/store/storeConfigs" \
  -H "Content-Type: application/json")

# Validate JSON array response
if ! echo "$STORE_RESPONSE" | jq -e '.[0]' &>/dev/null; then
  fail_stage "Connectivity" "Response is not valid JSON"
fi

STORE_BASE_URL=$(echo "$STORE_RESPONSE" | jq -r '.[0].base_url // "unknown"')
BASE_CURRENCY=$(echo "$STORE_RESPONSE" | jq -r '.[0].default_display_currency_code // "unknown"')

echo "  Store URL:      ${STORE_BASE_URL}"
echo "  Base currency:  ${BASE_CURRENCY}"

pass_stage "Connectivity" "reachable"

# =============================================================================
# STAGE 2: Authentication (customer token)
# =============================================================================
echo ""
echo "Stage 2/5: Authentication"
echo "---"

CUSTOMER_TOKEN_RESPONSE=$(curl_or_fail "Authentication" \
  -sf -X POST \
  "${MAGENTO_URL}/rest/V1/integration/customer/token" \
  -H "Content-Type: application/json" \
  -d "$(auth_payload "$COMPANY_ADMIN_EMAIL" "$COMPANY_ADMIN_PASSWORD")")

# Check for error object instead of token
if echo "$CUSTOMER_TOKEN_RESPONSE" | jq -e '.message' &>/dev/null 2>&1; then
  ERROR_MSG=$(echo "$CUSTOMER_TOKEN_RESPONSE" | jq -r '.message')
  fail_stage "Authentication" "Auth error: ${ERROR_MSG}"
fi

# Strip quotes from token string
CUSTOMER_TOKEN=$(echo "$CUSTOMER_TOKEN_RESPONSE" | jq -r '.')

# Sanity check: token should be non-empty
if [[ -z "$CUSTOMER_TOKEN" || "$CUSTOMER_TOKEN" == "null" ]]; then
  fail_stage "Authentication" "Empty token returned"
fi

echo "  Customer token obtained"

pass_stage "Authentication" "customer token obtained"

# =============================================================================
# STAGE 3: B2B Module Check
# =============================================================================
echo ""
echo "Stage 3/5: B2B Module Check"
echo "---"

# 3a: Get admin token
ADMIN_TOKEN_RESPONSE=$(curl_or_fail "B2B Module" \
  -sf -X POST \
  "${MAGENTO_URL}/rest/V1/integration/admin/token" \
  -H "Content-Type: application/json" \
  -d "$(auth_payload "$MAGENTO_ADMIN_USER" "$MAGENTO_ADMIN_PASS")")

if echo "$ADMIN_TOKEN_RESPONSE" | jq -e '.message' &>/dev/null 2>&1; then
  ERROR_MSG=$(echo "$ADMIN_TOKEN_RESPONSE" | jq -r '.message')
  fail_stage "B2B Module" "Admin auth error: ${ERROR_MSG}"
fi

ADMIN_TOKEN=$(echo "$ADMIN_TOKEN_RESPONSE" | jq -r '.')

if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  fail_stage "B2B Module" "Empty admin token returned"
fi

echo "  Admin token obtained"

# 3b: REST B2B endpoint check
REST_B2B_RESPONSE=$(curl_or_fail "B2B Module" \
  -sf \
  "${MAGENTO_URL}/rest/V1/company/role?searchCriteria[pageSize]=1" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}")

if echo "$REST_B2B_RESPONSE" | jq -e '.message' &>/dev/null 2>&1; then
  ERROR_MSG=$(echo "$REST_B2B_RESPONSE" | jq -r '.message')
  fail_stage "B2B Module" "REST B2B error: ${ERROR_MSG}"
fi

echo "  REST B2B endpoint: OK"

# 3c: GraphQL B2B query check
GQL_B2B_RESPONSE=$(curl_or_fail "B2B Module" \
  -sf -X POST "${MAGENTO_URL}/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CUSTOMER_TOKEN}" \
  -d '{"query":"{ company { name } }"}')

if echo "$GQL_B2B_RESPONSE" | jq -e '.errors' &>/dev/null 2>&1; then
  GQL_ERROR=$(echo "$GQL_B2B_RESPONSE" | jq -r '.errors[0].message')
  fail_stage "B2B Module" "GraphQL B2B error: ${GQL_ERROR}"
fi

COMPANY_NAME=$(echo "$GQL_B2B_RESPONSE" | jq -r '.data.company.name // "unknown"')
echo "  GraphQL B2B query: OK (company: ${COMPANY_NAME})"

pass_stage "B2B Module" "company: ${COMPANY_NAME}"

# =============================================================================
# STAGE 4: Full GraphQL Extraction Query
# =============================================================================
echo ""
echo "Stage 4/5: Full GraphQL Extraction Query"
echo "---"

# The exact FULL_EXTRACTION_QUERY from connectors/on-prem-graphql/core/graphql_queries.py
# Built as a JSON payload via jq to avoid escaping issues.
EXTRACTION_QUERY='query VezaExtraction { customer { email firstname lastname } company { id name legal_name email company_admin { email firstname lastname } legal_address { street city region { region_code } postcode country_code telephone } structure { items { id parent_id entity { __typename ... on Customer { email firstname lastname job_title telephone status created_at role { id name } team { id name structure_id } } ... on CompanyTeam { id name description } } } } } }'

GQL_FULL_RESPONSE=$(curl_or_fail "GraphQL Extraction" \
  -sf -X POST "${MAGENTO_URL}/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CUSTOMER_TOKEN}" \
  -d "$(jq -n --arg q "$EXTRACTION_QUERY" '{query: $q}')")

# Check for GraphQL errors
if echo "$GQL_FULL_RESPONSE" | jq -e '.errors' &>/dev/null 2>&1; then
  GQL_ERROR=$(echo "$GQL_FULL_RESPONSE" | jq -r '.errors[0].message')
  fail_stage "GraphQL Extraction" "GraphQL error: ${GQL_ERROR}"
fi

# Check structure.items exists and has entries
ITEMS_COUNT=$(echo "$GQL_FULL_RESPONSE" | jq '.data.company.structure.items | length' 2>/dev/null)
if [[ -z "$ITEMS_COUNT" || "$ITEMS_COUNT" == "0" || "$ITEMS_COUNT" == "null" ]]; then
  fail_stage "GraphQL Extraction" "structure.items is empty or missing"
fi

# Extract summary data
FULL_COMPANY_NAME=$(echo "$GQL_FULL_RESPONSE" | jq -r '.data.company.name // "unknown"')
LEGAL_NAME=$(echo "$GQL_FULL_RESPONSE" | jq -r '.data.company.legal_name // "N/A"')
ADMIN_EMAIL=$(echo "$GQL_FULL_RESPONSE" | jq -r '.data.company.company_admin.email // "unknown"')
USER_COUNT=$(echo "$GQL_FULL_RESPONSE" | jq '[.data.company.structure.items[] | select(.entity.__typename == "Customer")] | length')
TEAM_COUNT=$(echo "$GQL_FULL_RESPONSE" | jq '[.data.company.structure.items[] | select(.entity.__typename == "CompanyTeam")] | length')
ROLE_NAMES=$(echo "$GQL_FULL_RESPONSE" | jq -r '[.data.company.structure.items[] | select(.entity.__typename == "Customer") | .entity.role.name // empty] | unique | join(", ")')
ROLE_COUNT=$(echo "$GQL_FULL_RESPONSE" | jq '[.data.company.structure.items[] | select(.entity.__typename == "Customer") | .entity.role.name // empty] | unique | length')

echo "  Company:     ${FULL_COMPANY_NAME}"
echo "  Legal Name:  ${LEGAL_NAME}"
echo "  Admin:       ${ADMIN_EMAIL}"
echo "  Users:       ${USER_COUNT}"
echo "  Teams:       ${TEAM_COUNT}"
echo "  Roles:       ${ROLE_COUNT} (${ROLE_NAMES})"

pass_stage "GraphQL Extraction" "${USER_COUNT} users, ${TEAM_COUNT} teams, ${ROLE_COUNT} roles"

# =============================================================================
# STAGE 5: REST Role Permissions
# =============================================================================
echo ""
echo "Stage 5/5: REST Role Permissions"
echo "---"

ROLE_EXIT=0
ROLE_RESPONSE=$(curl -sf \
  "${MAGENTO_URL}/rest/V1/company/role?searchCriteria[pageSize]=100" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" 2>&1) || ROLE_EXIT=$?

if [[ $ROLE_EXIT -ne 0 ]]; then
  warn_stage "REST Permissions" "REST role endpoint unreachable (non-blocking)"
  echo "  Warning: Could not fetch role permissions (non-blocking)"
  print_summary
  exit 0
fi

# Check for error response
if echo "$ROLE_RESPONSE" | jq -e '.message' &>/dev/null 2>&1; then
  warn_stage "REST Permissions" "REST role endpoint returned error (non-blocking)"
  echo "  Warning: Role endpoint error (non-blocking)"
  print_summary
  exit 0
fi

REST_ROLE_COUNT=$(echo "$ROLE_RESPONSE" | jq '.items | length' 2>/dev/null)
if [[ -z "$REST_ROLE_COUNT" || "$REST_ROLE_COUNT" == "null" ]]; then
  warn_stage "REST Permissions" "Unexpected response format"
  print_summary
  exit 0
fi

# Print per-role permission counts (no subshell — use process substitution)
while IFS=$'\t' read -r role_name allow_count; do
  echo "  Role: ${role_name} — ${allow_count} permissions (allow)"
done < <(echo "$ROLE_RESPONSE" | jq -r '.items[] | [.role_name, ([.permissions[] | select(.permission == "allow")] | length | tostring)] | @tsv')

MAX_ACL=$(echo "$ROLE_RESPONSE" | jq '[.items[].permissions | [.[] | select(.permission == "allow")] | length] | max')

echo ""
echo "  ${REST_ROLE_COUNT} roles found, max ${MAX_ACL} ACL resources"

pass_stage "REST Permissions" "${REST_ROLE_COUNT} roles, ${MAX_ACL} ACL resources"

# =============================================================================
# Summary
# =============================================================================
print_summary
