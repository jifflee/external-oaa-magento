#!/usr/bin/env python3
"""
Magento CE GraphQL Extraction Script — Standalone, no Veza/OAA dependencies.

Authenticates against a Magento CE 2.4.7 instance, runs all available CE GraphQL
queries, and saves raw + combined JSON output. Use this to validate the data
extraction pipeline before B2B/Adobe Commerce is available.

Usage:
    python extract_ce.py                              # Uses .env defaults
    python extract_ce.py --url http://localhost        # Override store URL
    python extract_ce.py --admin                       # Use admin token
    python extract_ce.py --output ./output             # Override output dir
    python extract_ce.py --debug                       # Verbose logging
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# GraphQL query fragments
# ---------------------------------------------------------------------------

QUERY_STORE_CONFIG = """
query {
  storeConfig {
    store_name
    store_code
    base_url
    base_currency_code
    default_display_currency_code
    locale
    timezone
    weight_unit
  }
}
"""

QUERY_PRODUCTS = """
query Products($pageSize: Int!, $currentPage: Int!) {
  products(search: "", pageSize: $pageSize, currentPage: $currentPage) {
    total_count
    page_info {
      current_page
      page_size
      total_pages
    }
    items {
      id
      uid
      sku
      name
      type_id
      url_key
      price_range {
        minimum_price {
          regular_price { value currency }
          final_price   { value currency }
        }
      }
      categories {
        id
        name
      }
      stock_status
    }
  }
}
"""

QUERY_CATEGORIES = """
query {
  categories {
    total_count
    items {
      id
      uid
      name
      url_path
      level
      children_count
      product_count
      path
      children {
        id
        name
        url_path
        level
        product_count
        children {
          id
          name
          url_path
          level
          product_count
        }
      }
    }
  }
}
"""

QUERY_CMS_PAGE = """
query CmsPage($identifier: String!) {
  cmsPage(identifier: $identifier) {
    identifier
    url_key
    title
    content
    content_heading
    page_layout
    meta_title
    meta_description
  }
}
"""

QUERY_CUSTOMER = """
query {
  customer {
    id
    email
    firstname
    lastname
    middlename
    prefix
    suffix
    date_of_birth
    gender
    is_subscribed
    created_at
    default_billing
    default_shipping
    addresses {
      id
      firstname
      lastname
      street
      city
      region { region region_code }
      postcode
      country_code
      telephone
      default_billing
      default_shipping
    }
  }
}
"""

QUERY_ORDERS = """
query Orders($pageSize: Int!, $currentPage: Int!) {
  customer {
    orders(pageSize: $pageSize, currentPage: $currentPage) {
      total_count
      page_info {
        current_page
        page_size
        total_pages
      }
      items {
        order_number
        id
        order_date
        status
        carrier
        shipping_method
        total {
          grand_total { value currency }
          subtotal    { value currency }
          total_tax   { value currency }
          total_shipping { value currency }
          discounts { amount { value currency } label }
        }
        items {
          product_name
          product_sku
          quantity_ordered
          product_sale_price { value currency }
        }
        shipping_address {
          firstname
          lastname
          city
          region
          postcode
          country_code
        }
        payment_methods {
          name
          type
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class MagentoCEExtractor:
    """Extracts CE-available data from a Magento 2 instance via GraphQL."""

    def __init__(self, store_url: str, username: str, password: str,
                 auth_type: str = "customer", output_dir: str = "./output",
                 debug: bool = False):
        self.store_url = store_url.rstrip("/")
        self.username = username
        self.password = password
        self.auth_type = auth_type  # "customer" or "admin"
        self.output_dir = output_dir
        self.debug = debug
        self._token = None
        self._session = requests.Session()
        self._errors = []

    # -- authentication -----------------------------------------------------

    def authenticate(self) -> str:
        """Get bearer token via REST API."""
        if self.auth_type == "admin":
            url = f"{self.store_url}/rest/V1/integration/admin/token"
        else:
            url = f"{self.store_url}/rest/V1/integration/customer/token"

        payload = {"username": self.username, "password": self.password}

        if self.debug:
            print(f"  AUTH: POST {url}  (type={self.auth_type})")

        resp = self._session.post(url, json=payload, timeout=30)
        resp.raise_for_status()

        self._token = resp.json()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        })

        if self.debug:
            print(f"  AUTH: token={self._token[:20]}...")

        return self._token

    # -- GraphQL helper -----------------------------------------------------

    def graphql(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query and return the data dict."""
        url = f"{self.store_url}/graphql"
        body = {"query": query}
        if variables:
            body["variables"] = variables

        if self.debug:
            print(f"  GQL:  POST {url}  ({len(query)} chars)")

        resp = self._session.post(url, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if "errors" in result:
            msgs = [e.get("message", str(e)) for e in result["errors"]]
            raise RuntimeError(f"GraphQL errors: {'; '.join(msgs)}")

        return result.get("data", {})

    # -- individual fetchers ------------------------------------------------

    def fetch_store_config(self) -> dict:
        """Fetch store configuration (no auth required)."""
        data = self.graphql(QUERY_STORE_CONFIG)
        return data.get("storeConfig", {})

    def fetch_all_products(self, page_size: int = 50) -> dict:
        """Fetch all products, paginating automatically."""
        all_items = []
        current_page = 1
        total_count = 0

        while True:
            data = self.graphql(QUERY_PRODUCTS, {
                "pageSize": page_size,
                "currentPage": current_page,
            })
            products = data.get("products", {})
            total_count = products.get("total_count", 0)
            page_info = products.get("page_info", {})
            items = products.get("items", [])

            # Save raw page
            self._save_raw(f"products_page_{current_page}.json", {"data": {"products": products}})

            all_items.extend(items)

            if self.debug:
                print(f"  PRODUCTS: page {current_page}/{page_info.get('total_pages', 1)}  "
                      f"({len(items)} items)")

            if current_page >= page_info.get("total_pages", 1):
                break
            current_page += 1

        return {"total_count": total_count, "items": all_items}

    def fetch_categories(self) -> dict:
        """Fetch category tree."""
        data = self.graphql(QUERY_CATEGORIES)
        categories = data.get("categories", {})
        return categories

    def fetch_cms_page(self, identifier: str = "home") -> dict:
        """Fetch a single CMS page by identifier."""
        data = self.graphql(QUERY_CMS_PAGE, {"identifier": identifier})
        return data.get("cmsPage") or {}

    def fetch_customer(self) -> dict:
        """Fetch authenticated customer profile (requires customer token)."""
        data = self.graphql(QUERY_CUSTOMER)
        return data.get("customer", {})

    def fetch_all_orders(self, page_size: int = 50) -> dict:
        """Fetch all orders for the authenticated customer, paginating automatically."""
        all_items = []
        current_page = 1
        total_count = 0

        while True:
            data = self.graphql(QUERY_ORDERS, {
                "pageSize": page_size,
                "currentPage": current_page,
            })
            orders = data.get("customer", {}).get("orders", {})
            total_count = orders.get("total_count", 0)
            page_info = orders.get("page_info", {})
            items = orders.get("items", [])

            self._save_raw(f"orders_page_{current_page}.json", {"data": {"customer": {"orders": orders}}})

            all_items.extend(items)

            if self.debug:
                print(f"  ORDERS: page {current_page}/{page_info.get('total_pages', 1)}  "
                      f"({len(items)} items)")

            if current_page >= page_info.get("total_pages", 1):
                break
            current_page += 1

        return {"total_count": total_count, "items": all_items}

    # -- output helpers -----------------------------------------------------

    def _ensure_output_dirs(self):
        """Create timestamped output directory."""
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        self._run_dir = Path(self.output_dir) / f"{ts}_ce_extraction"
        self._raw_dir = self._run_dir / "raw"
        self._raw_dir.mkdir(parents=True, exist_ok=True)

    def _save_raw(self, filename: str, data: dict):
        """Save a raw JSON response to the raw/ subdirectory."""
        path = self._raw_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if self.debug:
            print(f"  SAVED: {path}")

    def _save_json(self, filename: str, data: dict):
        """Save a JSON file to the run directory root."""
        path = self._run_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return str(path)

    # -- main orchestrator --------------------------------------------------

    def run(self) -> dict:
        """Run all extractions, save output, return summary."""
        started = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        self._ensure_output_dirs()
        self._errors = []

        print(f"\n{'='*60}")
        print("MAGENTO CE GRAPHQL EXTRACTION")
        print("=" * 60)
        print(f"Store URL:   {self.store_url}")
        print(f"Auth type:   {self.auth_type}")
        print(f"Output dir:  {self._run_dir}")

        # -- authenticate ---------------------------------------------------
        print(f"\n--- Authenticate ({self.auth_type}) ---")
        try:
            self.authenticate()
            print("  OK")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"query": "authenticate", "error": str(e)})
            if self.debug:
                traceback.print_exc()
            # Auth failure is fatal — nothing else will work
            return self._build_summary(started, started_at, {})

        # -- queries --------------------------------------------------------
        payload = {
            "extracted_at": started_at,
            "store_url": self.store_url,
            "auth_type": self.auth_type,
            "magento_version": "CE 2.4.7",
        }

        queries = [
            ("store_config",  "storeConfig",   lambda: self.fetch_store_config()),
            ("products",      "products",      lambda: self.fetch_all_products()),
            ("categories",    "categories",    lambda: self.fetch_categories()),
            ("cms_home",      "cms_pages",     lambda: [self.fetch_cms_page("home")]),
            ("customer",      "customer",      lambda: self.fetch_customer()),
            ("orders",        "orders",        lambda: self.fetch_all_orders()),
        ]

        for name, payload_key, fetcher in queries:
            print(f"\n--- {name} ---")
            try:
                data = fetcher()
                payload[payload_key] = data

                # Products and orders save per-page raw files inside their fetchers;
                # everything else gets a single raw file here.
                if name not in ("products", "orders"):
                    self._save_raw(f"{name}.json", {"data": {payload_key: data}})

                # Pretty-print counts
                if isinstance(data, dict) and "total_count" in data:
                    print(f"  OK — {data['total_count']} items")
                elif isinstance(data, list):
                    print(f"  OK — {len(data)} items")
                elif isinstance(data, dict) and "items" in data:
                    print(f"  OK — {len(data['items'])} items")
                else:
                    print("  OK")

            except Exception as e:
                print(f"  FAILED: {e}")
                self._errors.append({"query": name, "error": str(e)})
                if self.debug:
                    traceback.print_exc()

        # -- save combined payload ------------------------------------------
        self._save_json("ce_payload.json", payload)
        summary = self._build_summary(started, started_at, payload)
        self._save_json("extraction_summary.json", summary)

        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Output: {self._run_dir}")
        print(f"Errors: {len(self._errors)}")
        print(f"Time:   {summary['elapsed_seconds']:.1f}s")

        return summary

    def _build_summary(self, started: float, started_at: str, payload: dict) -> dict:
        elapsed = time.time() - started
        counts = {}
        for key in ("products", "categories", "orders"):
            section = payload.get(key, {})
            if isinstance(section, dict):
                counts[key] = section.get("total_count", len(section.get("items", [])))
        if "cms_pages" in payload:
            counts["cms_pages"] = len(payload["cms_pages"])
        counts["customer"] = 1 if payload.get("customer") else 0

        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "store_url": self.store_url,
            "auth_type": self.auth_type,
            "output_dir": str(self._run_dir),
            "counts": counts,
            "errors": self._errors,
            "success": len(self._errors) < len(
                ["store_config", "products", "categories", "cms_home", "customer", "orders"]
            ),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Magento CE GraphQL Extraction — standalone, no Veza dependencies"
    )
    parser.add_argument("--url", default=None, help="Magento store URL (overrides MAGENTO_STORE_URL)")
    parser.add_argument("--username", default=None, help="Login username/email (overrides MAGENTO_USERNAME)")
    parser.add_argument("--password", default=None, help="Login password (overrides MAGENTO_PASSWORD)")
    parser.add_argument("--admin", action="store_true", help="Use admin token instead of customer token")
    parser.add_argument("--output", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--env", default="./.env", help="Path to .env file (default: ./.env)")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output")

    args = parser.parse_args()

    # Load .env if present (best effort — dotenv is optional here)
    env_path = Path(args.env)
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print(f"Loaded .env from: {env_path}")
        except ImportError:
            # Parse .env manually if python-dotenv not installed
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        value = value.strip().strip("'\"")
                        os.environ.setdefault(key.strip(), value)
            print(f"Loaded .env from: {env_path}  (manual parse, python-dotenv not installed)")

    # Resolve config: CLI args > env vars > defaults
    store_url = args.url or os.getenv("MAGENTO_STORE_URL", "http://localhost")
    username = args.username or os.getenv("MAGENTO_USERNAME", "")
    password = args.password or os.getenv("MAGENTO_PASSWORD", "")
    auth_type = "admin" if args.admin else "customer"

    if not username or not password:
        print("ERROR: Username and password are required.")
        print("  Set MAGENTO_USERNAME / MAGENTO_PASSWORD in .env, or use --username / --password")
        sys.exit(1)

    extractor = MagentoCEExtractor(
        store_url=store_url,
        username=username,
        password=password,
        auth_type=auth_type,
        output_dir=args.output,
        debug=args.debug,
    )

    summary = extractor.run()
    sys.exit(0 if summary.get("success") else 1)


if __name__ == "__main__":
    main()
