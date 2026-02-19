#!/bin/bash
# Validate what data Magento CE 2.4.7 exposes via REST and GraphQL

BASE="http://127.0.0.1"

echo "=========================================="
echo "Magento CE 2.4.7 — Data Availability Test"
echo "=========================================="

# Get admin token
RAW=$(curl -s -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"
echo "Admin token acquired: ${TOKEN:0:15}..."
echo ""

# ---------- REST API ----------
echo "=========================================="
echo "REST API — CE Endpoints"
echo "=========================================="

echo ""
echo "--- Store Configuration ---"
curl -s "$BASE/rest/V1/store/storeConfigs" | python3 -m json.tool 2>/dev/null | head -25
echo ""

echo "--- Store Websites ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/store/websites" | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Store Groups ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/store/storeGroups" | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Store Views ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/store/storeViews" | python3 -m json.tool 2>/dev/null | head -30
echo ""

echo "--- Installed Modules (count) ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/modules" | python3 -c "
import sys, json
mods = json.load(sys.stdin)
print(f'Total: {len(mods)} modules')
print('Sample:', mods[:5])
" 2>&1
echo ""

echo "--- Customers (search) ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/customers/search?searchCriteria[pageSize]=5" | python3 -m json.tool 2>/dev/null | head -20
echo ""

echo "--- Customer Groups ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/customerGroups/search?searchCriteria[pageSize]=10" | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Products (search) ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/products?searchCriteria[pageSize]=3" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total products: {data.get(\"total_count\", 0)}')
for p in data.get('items', [])[:3]:
    print(f'  - {p.get(\"sku\")}: {p.get(\"name\")} (status={p.get(\"status\")})')
" 2>&1
echo ""

echo "--- Categories ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/categories" | python3 -c "
import sys, json
def show(node, depth=0):
    print('  ' * depth + f'[{node.get(\"id\")}] {node.get(\"name\")} (active={node.get(\"is_active\")}, products={node.get(\"product_count\",0)})')
    for child in node.get('children_data', []):
        show(child, depth+1)
data = json.load(sys.stdin)
show(data)
" 2>&1
echo ""

echo "--- Orders (search) ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/orders?searchCriteria[pageSize]=3" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total orders: {data.get(\"total_count\", 0)}')
for o in data.get('items', [])[:3]:
    print(f'  - Order #{o.get(\"increment_id\")}: {o.get(\"status\")} total={o.get(\"grand_total\")}')
" 2>&1
echo ""

echo "--- CMS Pages ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/cmsPage/search?searchCriteria[pageSize]=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total CMS pages: {data.get(\"total_count\", 0)}')
for p in data.get('items', [])[:5]:
    print(f'  - [{p.get(\"id\")}] {p.get(\"title\")} (active={p.get(\"active\")})')
" 2>&1
echo ""

echo "--- CMS Blocks ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/cmsBlock/search?searchCriteria[pageSize]=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total CMS blocks: {data.get(\"total_count\", 0)}')
" 2>&1
echo ""

echo "--- Tax Rules ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/taxRules/search?searchCriteria[pageSize]=5" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total tax rules: {data.get(\"total_count\", 0)}')
" 2>&1
echo ""

echo "--- Inventory Sources ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/inventory/sources?searchCriteria[pageSize]=5" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total inventory sources: {data.get(\"total_count\", 0)}')
for s in data.get('items', []):
    print(f'  - {s.get(\"source_code\")}: {s.get(\"name\")} (enabled={s.get(\"enabled\")})')
" 2>&1
echo ""

echo "--- Cart Price Rules ---"
curl -s -g -H "$AUTH" "$BASE/rest/V1/salesRules/search?searchCriteria[pageSize]=5" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Total cart rules: {data.get(\"total_count\", 0)}')
" 2>&1
echo ""

echo ""
echo "=========================================="
echo "REST API — B2B Endpoints (expect 404)"
echo "=========================================="
echo ""
for ep in "company/" "company/role/" "hierarchy/1" "team/1" "sharedCatalog/" "negotiableQuote/list"; do
  CODE=$(curl -s -g -o /dev/null -w "%{http_code}" -H "$AUTH" "$BASE/rest/V1/$ep")
  printf "%-30s %s\n" "/rest/V1/$ep" "$CODE"
done

echo ""
echo "=========================================="
echo "GraphQL — Data Extraction"
echo "=========================================="

echo ""
echo "--- Store Config ---"
curl -s -X POST "$BASE/graphql" \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ storeConfig { store_name store_code base_url base_currency_code default_display_currency_code locale timezone weight_unit } }"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Products via GraphQL ---"
curl -s -X POST "$BASE/graphql" \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ products(search: \"\", pageSize: 3) { total_count items { sku name type_id price_range { minimum_price { regular_price { value currency } } } } } }"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Categories via GraphQL ---"
curl -s -X POST "$BASE/graphql" \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ categories(filters: {}) { total_count items { id name url_path product_count children { id name product_count } } } }"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "--- CMS Pages via GraphQL ---"
curl -s -X POST "$BASE/graphql" \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ cmsPage(identifier: \"home\") { identifier title url_key content_heading meta_title } }"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "--- Customer (auth required) via GraphQL ---"
CUST_TOKEN=$(curl -s -X POST "$BASE/rest/V1/integration/customer/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin@example.com","password":"Admin123!@#"}' 2>&1 | tr -d '"')
echo "Customer token attempt: ${CUST_TOKEN:0:30}"
echo ""

echo "--- B2B GraphQL (company query - expect error) ---"
curl -s -X POST "$BASE/graphql" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"{ company { id name legal_name } }"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "=========================================="
echo "Available REST API Endpoints (Swagger) ---"
echo "=========================================="
echo -n "Swagger JSON available: "
curl -s -o /dev/null -w "%{http_code}" -g -H "$AUTH" "$BASE/rest/all/schema?services=all"
echo ""
echo ""

echo "--- Counting available REST routes ---"
curl -s -g -H "$AUTH" "$BASE/rest/all/schema?services=all" 2>/dev/null | python3 -c "
import sys, json
try:
    schema = json.load(sys.stdin)
    paths = schema.get('paths', {})
    print(f'Total REST API routes: {len(paths)}')
    # Group by first path segment
    groups = {}
    for path in paths:
        parts = path.strip('/').split('/')
        key = parts[1] if len(parts) > 1 else parts[0]
        groups[key] = groups.get(key, 0) + 1
    print()
    print('Routes by resource:')
    for k, v in sorted(groups.items(), key=lambda x: -x[1])[:25]:
        print(f'  {k:30s} {v} routes')
except Exception as e:
    print(f'Error: {e}')
" 2>&1

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
php /var/www/magento/bin/magento --version 2>/dev/null
echo "Instance: $(curl -s -H "X-aws-ec2-metadata-token: $(curl -s -X PUT http://169.254.169.254/latest/api/token -H X-aws-ec2-metadata-token-ttl-seconds:60)" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null)"
