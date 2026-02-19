#!/bin/bash
# activate.sh — Source this before running terraform/aws commands.
# Fixes SSL cert issues for corporate proxy environments.
#
# Usage: source activate.sh [profile_name]
# Example: source activate.sh magento-mvp

set -euo pipefail

PROFILE="${1:-magento-mvp}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/certs"
BUNDLE_PATH="$CERTS_DIR/combined-ca-bundle.pem"

echo "=== Magento MVP Environment Setup ==="

# ---------- Build combined CA bundle ----------
# Corporate proxies replace TLS certs with their own CA.
# Python/AWS CLI need the full Mozilla CA chain + the corporate CA.
# Same approach as odie-oaa/core/preflight_checker.py

_build_ca_bundle() {
    mkdir -p "$CERTS_DIR"

    # Start with certifi's Mozilla CA bundle (ships with Python)
    local certifi_bundle
    certifi_bundle=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || true)

    if [ -z "$certifi_bundle" ] || [ ! -f "$certifi_bundle" ]; then
        # Fallback: try pip-installed certifi or system certs
        certifi_bundle=$(python3 -m certifi 2>/dev/null || true)
    fi

    if [ -n "$certifi_bundle" ] && [ -f "$certifi_bundle" ]; then
        cp "$certifi_bundle" "$BUNDLE_PATH"
    else
        echo "  WARN: certifi not found, starting with empty bundle"
        : > "$BUNDLE_PATH"
    fi

    # Append corporate CA cert if it exists
    local corp_cert="/tmp/corporate-ca-bundle.pem"
    if [ -f "$corp_cert" ]; then
        echo "" >> "$BUNDLE_PATH"
        echo "# --- Corporate proxy CA certificate ---" >> "$BUNDLE_PATH"
        cat "$corp_cert" >> "$BUNDLE_PATH"
        echo "  Added corporate CA from $corp_cert"
    fi

    # Append any SSL_CERT_FILE if different from what we already have
    if [ -n "${SSL_CERT_FILE:-}" ] && [ -f "$SSL_CERT_FILE" ] && [ "$SSL_CERT_FILE" != "$corp_cert" ]; then
        echo "" >> "$BUNDLE_PATH"
        echo "# --- SSL_CERT_FILE certificate ---" >> "$BUNDLE_PATH"
        cat "$SSL_CERT_FILE" >> "$BUNDLE_PATH"
        echo "  Added certs from SSL_CERT_FILE=$SSL_CERT_FILE"
    fi

    # Pull AWS endpoint certs via openssl as a fallback
    # (same technique as odie-oaa preflight_checker._pull_and_cache_cert)
    if command -v openssl &>/dev/null; then
        for host in "oidc.us-east-1.amazonaws.com" "portal.sso.us-east-1.amazonaws.com"; do
            local pem_blocks
            pem_blocks=$(echo "" | openssl s_client -showcerts -connect "$host:443" 2>/dev/null | \
                sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' || true)
            if [ -n "$pem_blocks" ]; then
                echo "" >> "$BUNDLE_PATH"
                echo "# --- Pulled from $host ---" >> "$BUNDLE_PATH"
                echo "$pem_blocks" >> "$BUNDLE_PATH"
                echo "  Pulled certs from $host"
            fi
        done
    fi

    echo "  Combined CA bundle: $BUNDLE_PATH ($(wc -l < "$BUNDLE_PATH") lines)"
}

# Build bundle if it doesn't exist or is older than 24 hours
if [ ! -f "$BUNDLE_PATH" ] || [ "$(find "$BUNDLE_PATH" -mmin +1440 2>/dev/null)" ]; then
    echo "Building combined CA bundle..."
    _build_ca_bundle
else
    echo "Using cached CA bundle: $BUNDLE_PATH"
fi

# ---------- Export environment ----------
export AWS_CA_BUNDLE="$BUNDLE_PATH"
export REQUESTS_CA_BUNDLE="$BUNDLE_PATH"
export SSL_CERT_FILE="$BUNDLE_PATH"
export AWS_PROFILE="$PROFILE"

echo ""
echo "Environment:"
echo "  AWS_PROFILE=$AWS_PROFILE"
echo "  AWS_CA_BUNDLE=$AWS_CA_BUNDLE"
echo "  REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE"

# ---------- SSO Login ----------
echo ""
echo "Testing AWS credentials..."
if aws sts get-caller-identity --profile "$PROFILE" &>/dev/null; then
    echo "  AWS session is active."
    aws sts get-caller-identity --profile "$PROFILE" --output table
else
    echo "  Session expired or not logged in. Starting SSO login..."
    aws sso login --profile "$PROFILE"

    if aws sts get-caller-identity --profile "$PROFILE" &>/dev/null; then
        echo "  Login successful."
        aws sts get-caller-identity --profile "$PROFILE" --output table
    else
        echo "  ERROR: SSO login failed. Check your profile config."
        return 1 2>/dev/null || exit 1
    fi
fi

echo ""
echo "=== Ready. Run 'terraform init && terraform apply' ==="
