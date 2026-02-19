#!/bin/bash
# All-in-one Magento CE setup for Amazon Linux 2023
# Run as root: sudo bash setup-magento.sh <repo_public_key> <repo_private_key> [admin_password]
#
# Installs: MariaDB 10.5, PHP 8.2, Nginx, Redis, OpenSearch, Composer, Magento 2.4.7
# B2B extension requires Adobe Commerce (Enterprise) keys — see README.md
# ~15-25 min on t3.medium

set -euo pipefail

REPO_PUBLIC_KEY="${1:?Usage: $0 <repo_public_key> <repo_private_key> [admin_password]}"
REPO_PRIVATE_KEY="${2:?Usage: $0 <repo_public_key> <repo_private_key> [admin_password]}"
ADMIN_PASSWORD="${3:-Admin123!@#}"
MAGENTO_DIR="/var/www/magento"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# SSM sessions don't set HOME — Composer needs it
export HOME=/root
# Allow Composer plugins to run as root (needed for Magento installer plugin to deploy project files)
export COMPOSER_ALLOW_SUPERUSER=1

# EC2 metadata (IMDSv2)
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300" 2>/dev/null || true)
get_meta() { curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || echo ""; }

# ---------- System ----------
log "Updating system packages..."
dnf update -y -q
dnf install -y -q git unzip tar wget jq java-17-amazon-corretto-headless

# ---------- MariaDB 10.5 ----------
log "Installing MariaDB 10.5..."
dnf install -y -q mariadb105-server
systemctl enable --now mariadb

mysql -u root <<SQL
CREATE DATABASE IF NOT EXISTS magento CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'magento'@'localhost' IDENTIFIED BY 'MagentoDB123!';
GRANT ALL PRIVILEGES ON magento.* TO 'magento'@'localhost';
FLUSH PRIVILEGES;
SQL
log "MariaDB ready."

# ---------- Redis ----------
log "Installing Redis..."
dnf install -y -q redis6
systemctl enable --now redis6
log "Redis ready."

# ---------- OpenSearch 2.x ----------
log "Installing OpenSearch..."

# Import GPG key and add repo
rpm --import https://artifacts.opensearch.org/publickeys/opensearch.pgp 2>/dev/null || true
cat > /etc/yum.repos.d/opensearch.repo <<'REPO'
[opensearch-2.x]
name=OpenSearch 2.x
baseurl=https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/yum
enabled=1
gpgcheck=1
gpgkey=https://artifacts.opensearch.org/publickeys/opensearch.pgp
REPO

# Install and configure for minimal memory
dnf install -y -q opensearch 2>/dev/null || {
  # Fallback: download and install directly
  log "Repo install failed, downloading OpenSearch 2.11 directly..."
  wget -q https://artifacts.opensearch.org/releases/bundle/opensearch/2.11.1/opensearch-2.11.1-linux-x64.tar.gz -O /tmp/opensearch.tar.gz
  mkdir -p /opt/opensearch
  tar -xzf /tmp/opensearch.tar.gz -C /opt/opensearch --strip-components=1
  rm /tmp/opensearch.tar.gz

  # Create opensearch user
  useradd -r -s /sbin/nologin opensearch 2>/dev/null || true
  chown -R opensearch:opensearch /opt/opensearch

  # Minimal config
  cat > /opt/opensearch/config/opensearch.yml <<'YML'
cluster.name: magento-mvp
node.name: node-1
path.data: /opt/opensearch/data
path.logs: /opt/opensearch/logs
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
plugins.security.disabled: true
YML

  # JVM heap — 512MB for MVP
  sed -i 's/-Xms[0-9]*[gm]/-Xms512m/' /opt/opensearch/config/jvm.options
  sed -i 's/-Xmx[0-9]*[gm]/-Xmx512m/' /opt/opensearch/config/jvm.options

  # Systemd unit
  cat > /etc/systemd/system/opensearch.service <<'UNIT'
[Unit]
Description=OpenSearch
After=network.target

[Service]
Type=simple
User=opensearch
Group=opensearch
ExecStart=/opt/opensearch/bin/opensearch
LimitNOFILE=65535
LimitMEMLOCK=infinity
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

  # Required sysctl for OpenSearch
  sysctl -w vm.max_map_count=262144 2>/dev/null || true
  echo "vm.max_map_count=262144" >> /etc/sysctl.conf

  systemctl daemon-reload
}

# If installed via dnf, configure similarly
if [ -f /etc/opensearch/opensearch.yml ]; then
  cat > /etc/opensearch/opensearch.yml <<'YML'
cluster.name: magento-mvp
node.name: node-1
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
plugins.security.disabled: true
YML
  # JVM heap — 512MB
  if [ -f /etc/opensearch/jvm.options ]; then
    sed -i 's/-Xms[0-9]*[gm]/-Xms512m/' /etc/opensearch/jvm.options
    sed -i 's/-Xmx[0-9]*[gm]/-Xmx512m/' /etc/opensearch/jvm.options
  fi
  sysctl -w vm.max_map_count=262144 2>/dev/null || true
fi

systemctl enable --now opensearch

# Wait for OpenSearch to be ready
log "Waiting for OpenSearch..."
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:9200 >/dev/null 2>&1; then
    log "OpenSearch ready."
    break
  fi
  sleep 2
done

# ---------- PHP 8.2 ----------
log "Installing PHP 8.2..."
dnf install -y -q \
  php8.2 \
  php8.2-fpm \
  php8.2-mysqlnd \
  php8.2-pdo \
  php8.2-bcmath \
  php8.2-gd \
  php8.2-intl \
  php8.2-mbstring \
  php8.2-opcache \
  php8.2-soap \
  php8.2-sodium \
  php8.2-xml \
  php8.2-zip \
  php8.2-process

# Tune PHP for t3.medium (4GB RAM)
cat > /etc/php.d/99-magento.ini <<'INI'
memory_limit = 768M
max_execution_time = 600
max_input_vars = 10000
realpath_cache_size = 10M
realpath_cache_ttl = 7200
opcache.memory_consumption = 256
opcache.max_accelerated_files = 60000
opcache.validate_timestamps = 1
INI

# FPM pool — conservative for 4GB
sed -i 's/^pm.max_children.*/pm.max_children = 10/' /etc/php-fpm.d/www.conf
sed -i 's/^pm = .*/pm = ondemand/' /etc/php-fpm.d/www.conf
sed -i 's/^;*pm.process_idle_timeout.*/pm.process_idle_timeout = 10s/' /etc/php-fpm.d/www.conf
sed -i 's/^user = .*/user = nginx/' /etc/php-fpm.d/www.conf
sed -i 's/^group = .*/group = nginx/' /etc/php-fpm.d/www.conf

systemctl enable --now php-fpm
log "PHP 8.2 ready."

# ---------- Nginx ----------
log "Installing Nginx..."
dnf install -y -q nginx

cat > /etc/nginx/conf.d/magento.conf <<'NGINX'
upstream fastcgi_backend {
    server unix:/run/php-fpm/www.sock;
}

server {
    listen 80;
    server_name _;

    set $MAGE_ROOT /var/www/magento;
    set $MAGE_MODE developer;

    root $MAGE_ROOT/pub;
    index index.php;

    autoindex off;
    client_max_body_size 64M;

    location / {
        try_files $uri $uri/ /index.php$is_args$args;
    }

    location /pub/ {
        alias $MAGE_ROOT/pub/;
    }

    location /static/ {
        expires max;
        log_not_found off;

        location ~* \.(ico|jpg|jpeg|png|gif|svg|svgz|webp|avif|avifs|js|css|eot|ttf|otf|woff|woff2|html|json)$ {
            expires max;
            add_header Cache-Control "public";
        }
    }

    location /media/ {
        try_files $uri $uri/ /get.php$is_args$args;

        location ~* \.(ico|jpg|jpeg|png|gif|svg|svgz|webp|avif|avifs|js|css|eot|ttf|otf|woff|woff2|html|json)$ {
            expires max;
            add_header Cache-Control "public";
        }
    }

    location ~ ^/(index|get|static|errors/report|errors/404|errors/503|health_check)\.php$ {
        fastcgi_pass fastcgi_backend;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;

        fastcgi_buffers 16 16k;
        fastcgi_buffer_size 32k;
        fastcgi_read_timeout 600s;
        fastcgi_connect_timeout 600s;
    }

    location ~ \.php$ {
        return 404;
    }

    location /rest/ {
        try_files $uri $uri/ /index.php$is_args$args;
    }

    location /graphql {
        try_files $uri $uri/ /index.php$is_args$args;
    }
}
NGINX

rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
nginx -t
systemctl enable --now nginx
log "Nginx ready."

# ---------- Composer ----------
log "Installing Composer..."
php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
php composer-setup.php --install-dir=/usr/local/bin --filename=composer
rm composer-setup.php

mkdir -p /root/.config/composer
cat > /root/.config/composer/auth.json <<EOF
{
    "http-basic": {
        "repo.magento.com": {
            "username": "${REPO_PUBLIC_KEY}",
            "password": "${REPO_PRIVATE_KEY}"
        }
    }
}
EOF

# Disable security advisory blocking globally (Magento 2.4.7 has known advisory PKSA-db8d-773v-rd1n)
composer config --global audit.block-insecure false 2>/dev/null || true
log "Composer ready."

# ---------- Magento 2.4.7 ----------
log "Installing Magento 2.4.7 via Composer (this takes a few minutes)..."
rm -rf "${MAGENTO_DIR:?}" 2>/dev/null || true
mkdir -p "$MAGENTO_DIR"

composer create-project --repository-url=https://repo.magento.com/ \
  magento/project-community-edition=2.4.7 "$MAGENTO_DIR" \
  --no-interaction --no-dev --no-audit 2>&1 | tail -15

cd "$MAGENTO_DIR"

# Verify project files were deployed by Composer plugin
if [ ! -f bin/magento ]; then
  log "ERROR: bin/magento not found — Composer plugin may have failed"
  exit 1
fi

# Try to install B2B extension (requires Adobe Commerce keys)
log "Attempting B2B extension install..."
composer config audit.block-insecure false 2>/dev/null || true
if composer require magento/extension-b2b --no-interaction --no-audit 2>&1 | tail -5; then
  B2B_INSTALLED=true
  log "B2B extension installed."
else
  B2B_INSTALLED=false
  log "B2B extension not available (requires Adobe Commerce keys). Continuing with CE only."
fi

PRIVATE_IP=$(get_meta local-ipv4)
PUBLIC_IP=$(get_meta public-ipv4)
[ -z "$PRIVATE_IP" ] && PRIVATE_IP=$(hostname -I | awk '{print $1}')
[ -z "$PUBLIC_IP" ] && PUBLIC_IP="$PRIVATE_IP"

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
  --admin-password="${ADMIN_PASSWORD}" \
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

# ---------- Enable B2B Modules (if installed) ----------
if [ "$B2B_INSTALLED" = true ]; then
  log "Enabling B2B modules..."
  php bin/magento module:enable \
    Magento_B2b \
    Magento_Company \
    Magento_CompanyCredit \
    Magento_CompanyPayment \
    Magento_NegotiableQuote \
    Magento_PurchaseOrder \
    Magento_SharedCatalog \
    2>/dev/null || log "Some B2B modules may already be enabled"

  php bin/magento setup:upgrade
  php bin/magento cache:flush

  php bin/magento config:set btob/website_configuration/company_active 1
  php bin/magento config:set btob/website_configuration/sharedcatalog_active 1
  php bin/magento config:set btob/website_configuration/negotiablequote_active 1
  php bin/magento config:set btob/website_configuration/purchaseorder_default 1

  php bin/magento cache:flush
  php bin/magento indexer:reindex
fi

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
php bin/magento setup:upgrade
php bin/magento cache:flush
chown -R nginx:nginx "$MAGENTO_DIR"

# ---------- Done ----------
log "============================================"
if [ "$B2B_INSTALLED" = true ]; then
  log "Magento 2.4.7 + B2B is ready!"
else
  log "Magento 2.4.7 CE is ready! (B2B not installed — needs Commerce keys)"
fi
log "============================================"
log "Storefront: http://${PUBLIC_IP}/"
log "Admin:      http://${PUBLIC_IP}/admin"
log "Admin user: admin / ${ADMIN_PASSWORD}"
log ""
log "REST API:   http://${PRIVATE_IP}/rest/V1/"
log "GraphQL:    http://${PRIVATE_IP}/graphql"
log "============================================"
