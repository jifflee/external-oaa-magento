#!/bin/bash
# Veza Insight Point setup — Amazon Linux 2023
# Run as root: sudo bash setup-insight-point.sh
#
# Installs: Python 3.11, git, clones connectors, creates venvs
# ~3-5 min on t3.micro

set -euo pipefail

CONNECTOR_DIR="/opt/veza-connectors"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ---------- System ----------
log "Updating system..."
dnf update -y -q
dnf install -y -q git python3.11 python3.11-pip jq

# ---------- Clone Connectors ----------
log "Setting up connector directories..."
mkdir -p "$CONNECTOR_DIR"

# Copy connector code — adjust source as needed
# Option 1: Clone from repo (fill in your git URL)
# git clone https://your-repo.git /tmp/magento-connectors
# cp -r /tmp/magento-connectors/rest-connector "$CONNECTOR_DIR/"
# cp -r /tmp/magento-connectors/graphql-connector "$CONNECTOR_DIR/"
# cp -r /tmp/magento-connectors/odie-oaa "$CONNECTOR_DIR/"

# Option 2: SCP from local (run from your machine):
#   scp -i ~/.ssh/key.pem -r rest-connector graphql-connector odie-oaa \
#       ec2-user@<insight-point-ip>:/tmp/
#   Then on EC2: sudo cp -r /tmp/{rest,graphql}-connector /tmp/odie-oaa /opt/veza-connectors/

# For now, create placeholder dirs — replace with actual code
for connector in rest-connector graphql-connector odie-oaa; do
  mkdir -p "$CONNECTOR_DIR/$connector"
done

log "Connectors directory ready at $CONNECTOR_DIR"

# ---------- Virtual Environments ----------
log "Creating Python virtual environments..."

# rest-connector and graphql-connector share the same deps (oaaclient>=2.0.0)
python3.11 -m venv "$CONNECTOR_DIR/rest-connector/venv"
"$CONNECTOR_DIR/rest-connector/venv/bin/pip" install -q --upgrade pip
if [ -f "$CONNECTOR_DIR/rest-connector/requirements.txt" ]; then
  "$CONNECTOR_DIR/rest-connector/venv/bin/pip" install -q \
    -r "$CONNECTOR_DIR/rest-connector/requirements.txt"
else
  "$CONNECTOR_DIR/rest-connector/venv/bin/pip" install -q \
    'oaaclient>=2.0.0' 'requests>=2.28.0' 'python-dotenv>=0.21.0'
fi

python3.11 -m venv "$CONNECTOR_DIR/graphql-connector/venv"
"$CONNECTOR_DIR/graphql-connector/venv/bin/pip" install -q --upgrade pip
if [ -f "$CONNECTOR_DIR/graphql-connector/requirements.txt" ]; then
  "$CONNECTOR_DIR/graphql-connector/venv/bin/pip" install -q \
    -r "$CONNECTOR_DIR/graphql-connector/requirements.txt"
else
  "$CONNECTOR_DIR/graphql-connector/venv/bin/pip" install -q \
    'oaaclient>=2.0.0' 'requests>=2.28.0' 'python-dotenv>=0.21.0'
fi

# odie-oaa needs separate venv (oaaclient>=1.0.0, different version range)
python3.11 -m venv "$CONNECTOR_DIR/odie-oaa/venv"
"$CONNECTOR_DIR/odie-oaa/venv/bin/pip" install -q --upgrade pip
if [ -f "$CONNECTOR_DIR/odie-oaa/requirements.txt" ]; then
  "$CONNECTOR_DIR/odie-oaa/venv/bin/pip" install -q \
    -r "$CONNECTOR_DIR/odie-oaa/requirements.txt"
else
  "$CONNECTOR_DIR/odie-oaa/venv/bin/pip" install -q \
    'oaaclient>=1.0.0' 'python-dotenv>=1.0.0' 'requests>=2.28.0'
fi

log "Virtual environments created."

# ---------- Env Templates ----------
log "Creating .env files from templates..."

# REST connector
cat > "$CONNECTOR_DIR/rest-connector/.env" <<'ENV'
# Magento B2B Configuration
MAGENTO_STORE_URL=http://MAGENTO_PRIVATE_IP
MAGENTO_USERNAME=company-admin@example.com
MAGENTO_PASSWORD=your-password-here

# Veza Configuration (required for push mode)
VEZA_URL=https://your-tenant.vezacloud.com
VEZA_API_KEY=your-api-key-here

# Provider Configuration
PROVIDER_NAME=Magento_B2B_REST
PROVIDER_PREFIX=

# Processing Options
DRY_RUN=true
SAVE_JSON=true
DEBUG=false

# Output Configuration
OUTPUT_DIR=./output
OUTPUT_RETENTION_DAYS=30

# REST-specific: User-Role gap workaround strategy
# Options: default_role | csv_supplement | all_roles | skip
USER_ROLE_STRATEGY=default_role
USER_ROLE_MAPPING_PATH=./data/user_role_mapping.csv
ENV

# GraphQL connector
cat > "$CONNECTOR_DIR/graphql-connector/.env" <<'ENV'
# Magento B2B Configuration
MAGENTO_STORE_URL=http://MAGENTO_PRIVATE_IP
MAGENTO_USERNAME=company-admin@example.com
MAGENTO_PASSWORD=your-password-here

# Veza Configuration (required for push mode)
VEZA_URL=https://your-tenant.vezacloud.com
VEZA_API_KEY=your-api-key-here

# Provider Configuration
PROVIDER_NAME=Magento_B2B_GraphQL
PROVIDER_PREFIX=

# Processing Options
DRY_RUN=true
SAVE_JSON=true
DEBUG=false

# Output Configuration
OUTPUT_DIR=./output
OUTPUT_RETENTION_DAYS=30

# GraphQL-specific: Supplement with REST role details for explicit allow/deny
USE_REST_ROLE_SUPPLEMENT=true
ENV

# ODIE OAA connector
cat > "$CONNECTOR_DIR/odie-oaa/.env" <<'ENV'
# Veza Configuration
VEZA_URL=https://your-tenant.vezacloud.com
VEZA_API_KEY=your_api_key_here

# Provider Configuration
PROVIDER_NAME=Odie

# Input/Output Paths
CSV_FILENAME=odie.csv
OUTPUT_DIR=./output
OUTPUT_RETENTION_DAYS=180

# Processing Options
DRY_RUN=true
SAVE_JSON=true
DEBUG=false
ENV

log "============================================"
log "Insight Point setup complete!"
log "============================================"
log ""
log "Next steps:"
log "1. Copy connector code to $CONNECTOR_DIR/"
log "   scp -r rest-connector graphql-connector odie-oaa ec2-user@\$(hostname):/tmp/"
log "   sudo cp -r /tmp/{rest,graphql}-connector /tmp/odie-oaa $CONNECTOR_DIR/"
log ""
log "2. Edit .env files with real values:"
log "   - Replace MAGENTO_PRIVATE_IP with Magento EC2 private IP"
log "   - Set VEZA_URL and VEZA_API_KEY"
log "   - Set Magento B2B company admin credentials"
log ""
log "3. Test connectors (dry run):"
log "   cd $CONNECTOR_DIR/rest-connector"
log "   venv/bin/python run.py --dry-run"
log ""
log "   cd $CONNECTOR_DIR/graphql-connector"
log "   venv/bin/python run.py --dry-run"
log "============================================"
