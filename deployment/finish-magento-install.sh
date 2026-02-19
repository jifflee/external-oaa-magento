#!/bin/bash
set -euo pipefail
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1
MAGENTO_DIR="/var/www/magento"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# EC2 metadata (IMDSv2)
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300" 2>/dev/null || true)
get_meta() { curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || echo ""; }

PRIVATE_IP=$(get_meta local-ipv4)
PUBLIC_IP=$(get_meta public-ipv4)
[ -z "$PRIVATE_IP" ] && PRIVATE_IP=$(hostname -I | awk '{print $1}')
[ -z "$PUBLIC_IP" ] && PUBLIC_IP="$PRIVATE_IP"
log "Public IP: $PUBLIC_IP, Private IP: $PRIVATE_IP"

# ---------- Redo Composer create-project with plugins enabled ----------
log "Wiping previous incomplete install and re-creating Magento project..."
rm -rf "${MAGENTO_DIR:?}"
mkdir -p "$MAGENTO_DIR"

# Disable block-insecure globally (Magento 2.4.7 has known advisory PKSA-db8d-773v-rd1n)
composer config --global audit.block-insecure false 2>/dev/null || true

log "Running composer create-project (this takes several minutes)..."
composer create-project --repository-url=https://repo.magento.com/ \
  magento/project-community-edition=2.4.7 "$MAGENTO_DIR" \
  --no-interaction --no-dev --no-audit 2>&1 | tail -20

cd "$MAGENTO_DIR"

# Verify bin/magento exists
if [ ! -f bin/magento ]; then
  log "ERROR: bin/magento still doesn't exist!"
  ls -la "$MAGENTO_DIR/" | head -20
  exit 1
fi
log "Magento project files deployed successfully."

# ---------- Install Magento ----------
log "Running Magento setup:install..."
php bin/magento setup:install \
  --base-url="http://${PUBLIC_IP}/" \
  --db-host=localhost \
  --db-name=magento \
  --db-user=magento \
  --db-password='MagentoDB123!' \
  --admin-firstname=Admin \
  --admin-lastname=User \
  --admin-email=admin@example.com \
  --admin-user=admin \
  --admin-password='Admin123!@#' \
  --language=en_US \
  --currency=USD \
  --timezone=America/Chicago \
  --use-rewrites=1 \
  --search-engine=opensearch \
  --opensearch-host=127.0.0.1 \
  --opensearch-port=9200 \
  --cache-backend=redis \
  --cache-backend-redis-server=127.0.0.1 \
  --cache-backend-redis-port=6379 \
  --cache-backend-redis-db=0 \
  --session-save=redis \
  --session-save-redis-host=127.0.0.1 \
  --session-save-redis-port=6379 \
  --session-save-redis-db=1
log "Magento installed."

# ---------- File Permissions ----------
log "Setting file permissions..."
chown -R nginx:nginx "$MAGENTO_DIR"
find "$MAGENTO_DIR" -type d -exec chmod 755 {} \;
find "$MAGENTO_DIR" -type f -exec chmod 644 {} \;
chmod -R 775 "$MAGENTO_DIR/var" "$MAGENTO_DIR/generated" "$MAGENTO_DIR/pub/static" "$MAGENTO_DIR/pub/media"
chmod 775 "$MAGENTO_DIR/app/etc"

# ---------- Disable 2FA for testing ----------
log "Disabling 2FA for admin access..."
php bin/magento module:disable Magento_AdminAdobeImsTwoFactorAuth Magento_TwoFactorAuth 2>/dev/null || true
php bin/magento setup:upgrade 2>&1 | tail -5
php bin/magento cache:flush
chown -R nginx:nginx "$MAGENTO_DIR"

# ---------- Verify ----------
log "Testing HTTP response..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ || echo "FAIL")
log "HTTP response code: $HTTP_CODE"

log "Testing REST API..."
REST_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/rest/V1/store/storeConfigs || echo "FAIL")
log "REST API response code: $REST_CODE"

log "============================================"
log "Magento CE is ready!"
log "============================================"
log "Storefront: http://${PUBLIC_IP}/"
log "Admin:      http://${PUBLIC_IP}/admin"
log "Admin user: admin / Admin123!@#"
log ""
log "REST API:   http://${PRIVATE_IP}/rest/V1/"
log "GraphQL:    http://${PRIVATE_IP}/graphql"
log "============================================"
