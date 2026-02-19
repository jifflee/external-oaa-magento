"""
Shared Veza API client for identity mapping module.

Thin wrapper following the deployment_validator.py:_api_get pattern.
Reuses parent .env credentials via dotenv.
Uses core/preflight_checker.py for SSL auto-fix.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import requests

# Add parent directory to path so we can import core modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.preflight_checker import PreflightChecker
from core.veza_client import VezaClient
from core.provider_registry import ProviderRegistry


class VezaAPI:
    """
    Lightweight Veza API client for GET and PATCH operations.

    Reads VEZA_URL and VEZA_API_KEY from the specified .env file.
    Delegates SSL verification to the existing PreflightChecker.
    """

    def __init__(self, env_file: str = "../.env", debug: bool = False):
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            if debug:
                print(f"  DEBUG: Loaded env from {env_path.resolve()}")
        else:
            print(f"Warning: {env_file} not found, using environment variables")

        self.veza_url = os.getenv("VEZA_URL", "").rstrip("/")
        self.veza_api_key = os.getenv("VEZA_API_KEY", "")
        self.debug = debug

        if not self.veza_url:
            raise ValueError("VEZA_URL is not set")
        if not self.veza_api_key:
            raise ValueError("VEZA_API_KEY is not set")

        self._ensure_ssl()

    def _ensure_ssl(self) -> None:
        """
        Run SSL verification using the core PreflightChecker.

        Creates a minimal PreflightChecker instance just to exercise
        its SSL connectivity check and cert auto-fix logic.
        """
        veza_client = VezaClient(
            veza_url=self.veza_url,
            veza_api_key=self.veza_api_key,
            debug=self.debug,
        )
        registry = ProviderRegistry(output_dir="./output", debug=self.debug)
        checker = PreflightChecker(
            veza_client=veza_client,
            registry=registry,
            debug=self.debug,
        )

        # Reuse the checker's SSL methods directly
        from urllib.parse import urlparse
        import ssl

        hostname = urlparse(self.veza_url).hostname

        print("  Verifying SSL connectivity...", end=" ", flush=True)
        try:
            checker._verify_ssl_connectivity(self.veza_url)
            print("OK")
            return
        except (ssl.SSLError, ssl.SSLCertVerificationError, OSError) as ssl_err:
            print("FAILED")
            if self.debug:
                print(f"  DEBUG: SSL error: {ssl_err}")

        # Try cached cert bundle
        cached_cert = Path("./certs") / f"{hostname}.pem"
        if cached_cert.is_file():
            os.environ["REQUESTS_CA_BUNDLE"] = str(cached_cert.resolve())
            print("  Loading cached certificate bundle...", end=" ", flush=True)
            try:
                checker._verify_ssl_connectivity(self.veza_url)
                print("OK")
                return
            except (ssl.SSLError, ssl.SSLCertVerificationError, OSError):
                print("FAILED (stale cache)")
                os.environ.pop("REQUESTS_CA_BUNDLE", None)

        # Pull fresh certs via openssl
        print("  Attempting to retrieve server certificate chain...", end=" ", flush=True)
        if checker._pull_and_cache_cert(hostname):
            print("OK")
            print("  Retrying SSL verification...", end=" ", flush=True)
            try:
                checker._verify_ssl_connectivity(self.veza_url)
                print("OK")
                print(f"  Cached certificate bundle: ./certs/{hostname}.pem")
                return
            except (ssl.SSLError, ssl.SSLCertVerificationError, OSError):
                print("FAILED")
                os.environ.pop("REQUESTS_CA_BUNDLE", None)
        else:
            print("FAILED")

        # Interactive fallback
        if not checker._handle_ssl_failure(hostname, ssl_err):
            raise RuntimeError(
                f"SSL verification failed for {hostname}. "
                "Set REQUESTS_CA_BUNDLE to your corporate CA cert and retry."
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.veza_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def api_get(self, path: str) -> list:
        """
        Make a GET request to the Veza API and return the values list.

        Args:
            path: API path (e.g., "api/v1/providers/activedirectory")

        Returns:
            List of values from the response.
        """
        url = f"{self.veza_url}/{path}"

        if self.debug:
            print(f"  DEBUG: GET {url}")

        response = requests.get(url, headers=self._headers(), timeout=60)

        if self.debug:
            print(f"  DEBUG: Status: {response.status_code}")

        response.raise_for_status()
        data = response.json()
        return data.get("values", [])

    def api_patch(self, path: str, data: dict) -> dict:
        """
        Make a PATCH request to the Veza API.

        Args:
            path: API path
            data: Request body dictionary

        Returns:
            Response JSON dictionary.
        """
        url = f"{self.veza_url}/{path}"

        if self.debug:
            print(f"  DEBUG: PATCH {url}")
            print(f"  DEBUG: Body: {data}")

        response = requests.patch(
            url, headers=self._headers(), json=data, timeout=60
        )

        if self.debug:
            print(f"  DEBUG: Status: {response.status_code}")
            if not response.ok:
                print(f"  DEBUG: Response: {response.text}")

        if not response.ok:
            error_detail = ""
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text[:500]
            raise RuntimeError(
                f"PATCH {path} failed ({response.status_code}): {error_detail}"
            )
        return response.json()
