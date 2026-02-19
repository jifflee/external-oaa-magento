"""
================================================================================
PREFLIGHT CHECKER - Provider Conflict Detection (Core Module)
================================================================================

PURPOSE:
    Checks for existing providers in Veza before processing.
    Detects conflicts and provides resolution options.

    This is a CORE module - do not modify.

================================================================================
"""

import os
import re
import shutil
import socket
import ssl
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse

from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .csv_loader import load_csv, group_by_application


class PreflightResult:
    """Result of preflight check."""

    def __init__(self):
        self.proceed = True
        self.skip_providers: Set[str] = set()
        self.delete_providers: Set[str] = set()
        self.override_providers: Set[str] = set()
        self.conflicts: List[Dict] = []
        self.has_conflicts = False


class PreflightChecker:
    """
    Checks for provider conflicts before processing.

    Detects:
    - Our own providers from previous runs (auto-override)
    - External providers with same name (conflict)
    """

    def __init__(
        self,
        veza_client: VezaClient,
        registry: ProviderRegistry,
        provider_prefix: str = "",
        debug: bool = False
    ):
        """
        Initialize preflight checker.

        Args:
            veza_client: Veza API client
            registry: Provider registry for tracking IDs
            provider_prefix: Prefix for provider names
            debug: Enable debug output
        """
        self.veza_client = veza_client
        self.registry = registry
        self.provider_prefix = provider_prefix
        self.debug = debug

    def check(
        self,
        csv_path: str,
        auto_mode: Optional[str] = None,
        dry_run: bool = False
    ) -> PreflightResult:
        """
        Run preflight check for provider conflicts.

        Args:
            csv_path: Path to CSV file
            auto_mode: "skip" or "delete" for automatic resolution
            dry_run: If True, just report (don't prompt)

        Returns:
            PreflightResult with conflict information
        """
        result = PreflightResult()

        print(f"\n{'='*60}")
        print("PREFLIGHT CHECK - Validating against Veza")
        print('='*60)

        # Check credentials
        if not self.veza_client.veza_url or not self.veza_client.veza_api_key:
            if dry_run:
                print("  SKIPPED: VEZA_URL/VEZA_API_KEY not configured")
                print("  (Configure credentials to check for existing providers)")
                return result
            else:
                print("  ERROR: VEZA_URL and VEZA_API_KEY required for live push")
                result.proceed = False
                return result

        # ----------------------------------------------------------
        # SSL connectivity check – fast-fail before OAAClient init
        # Only triggers cert handling if the initial test fails.
        # ----------------------------------------------------------
        veza_url = self.veza_client.veza_url
        hostname = urlparse(veza_url).hostname

        print("  Verifying SSL connectivity...", end=" ", flush=True)
        try:
            self._verify_ssl_connectivity(veza_url)
            print("OK")
        except (ssl.SSLError, ssl.SSLCertVerificationError, OSError) as ssl_err:
            print("FAILED")

            # --- Try cached cert first ---
            cached_cert = Path("./certs") / f"{hostname}.pem"
            if cached_cert.is_file():
                os.environ["REQUESTS_CA_BUNDLE"] = str(cached_cert.resolve())
                print("  Loading cached certificate bundle...", end=" ", flush=True)
                try:
                    self._verify_ssl_connectivity(veza_url)
                    print("OK")
                    ssl_err = None  # resolved
                except (ssl.SSLError, ssl.SSLCertVerificationError, OSError):
                    print("FAILED (stale cache)")
                    os.environ.pop("REQUESTS_CA_BUNDLE", None)

            # --- If still failing, pull fresh certs via openssl ---
            if ssl_err is not None:
                print("  Attempting to retrieve server certificate chain...", end=" ", flush=True)
                if self._pull_and_cache_cert(hostname):
                    print("OK")
                    print("  Retrying SSL verification...", end=" ", flush=True)
                    try:
                        self._verify_ssl_connectivity(veza_url)
                        print("OK")
                        print(f"  Cached certificate bundle: ./certs/{hostname}.pem")
                        ssl_err = None  # resolved
                    except (ssl.SSLError, ssl.SSLCertVerificationError, OSError):
                        print("FAILED")
                else:
                    print("FAILED")

            # --- If nothing worked, prompt user ---
            if ssl_err is not None:
                if not self._handle_ssl_failure(hostname, ssl_err):
                    result.proceed = False
                    return result

        # Load previous provider IDs
        previous_ids = self.registry.load()
        if previous_ids:
            print(f"  Found {len(previous_ids)} provider(s) from previous run")

        # Load CSV and get applications
        rows = load_csv(csv_path)
        apps_data = group_by_application(rows)

        # Show prefix status
        if self.provider_prefix:
            print(f"  Provider prefix: {self.provider_prefix}_")
        else:
            print("  Provider prefix: (none configured)")

        print(f"  Connecting to Veza...", end=" ", flush=True)

        # Fetch all providers in a single API call
        try:
            all_providers = self.veza_client.get_provider_list()
            provider_lookup = {p.get("name"): p for p in all_providers}
            print("OK")
        except Exception as e:
            print("FAILED")
            print(f"  ERROR: Cannot connect to Veza API: {e}")
            if dry_run:
                print("  (Skipping provider conflict check)")
                return result
            result.proceed = False
            return result

        print(f"  Checking {len(apps_data)} applications against Veza...")

        # Check each application
        overrides = []

        for app_id, app_rows in apps_data.items():
            app_name = app_rows[0].get('Application_FIN_Name', app_id)
            provider_name = VezaClient.generate_provider_name(app_name, self.provider_prefix)

            existing = provider_lookup.get(provider_name)

            if existing:
                existing_id = existing.get("id")
                previous_id = previous_ids.get(provider_name)

                if previous_id and existing_id == previous_id:
                    # Our own provider - auto-override
                    result.override_providers.add(provider_name)
                    overrides.append({
                        "app_id": app_id,
                        "app_name": app_name,
                        "provider_name": provider_name,
                        "provider_id": existing_id
                    })
                else:
                    # External conflict
                    conflict = {
                        "app_id": app_id,
                        "app_name": app_name,
                        "provider_name": provider_name,
                        "provider_id": existing_id,
                        "template": existing.get("custom_template")
                    }
                    result.conflicts.append(conflict)
                    result.has_conflicts = True

        # Report overrides
        if overrides:
            print(f"\n  AUTO-OVERRIDE: {len(overrides)} provider(s) match previous run (will update)")
            for o in overrides:
                print(f"    - {o['provider_name']} (ID: {o['provider_id'][:8]}...)")

        # No conflicts - good to go
        if not result.conflicts:
            if overrides:
                print(f"\n  OK: No external conflicts - {len(overrides)} provider(s) will be updated")
            else:
                print("  OK: No conflicts - all providers are new")
            return result

        # Report conflicts
        self._print_conflicts(result.conflicts)

        # Handle resolution
        if dry_run:
            self._print_resolution_options(result.conflicts)
            return result

        result = self._handle_resolution(result, auto_mode)
        return result

    # ------------------------------------------------------------------
    # SSL connectivity helpers
    # ------------------------------------------------------------------

    def _verify_ssl_connectivity(self, veza_url: str) -> bool:
        """
        Quick TLS handshake test using Python's ssl module.

        Returns True on success, raises ssl.SSLError (or subclass) on
        certificate problems.  Uses a 10-second timeout so we fail fast
        instead of falling into OAAClient's retry loop.
        """
        hostname = urlparse(veza_url).hostname
        port = urlparse(veza_url).port or 443

        ctx = ssl.create_default_context()

        # If REQUESTS_CA_BUNDLE is already set (e.g. from a cached cert),
        # load that bundle so we test with the same trust store requests will use.
        ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
        if ca_bundle and os.path.isfile(ca_bundle):
            ctx.load_verify_locations(ca_bundle)

        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                ssock.do_handshake()
        return True

    def _pull_and_cache_cert(self, hostname: str) -> bool:
        """
        Use ``openssl s_client`` to grab the remote certificate chain,
        append it to a *copy* of the certifi CA bundle, and save the
        combined file to ``./certs/<hostname>.pem``.

        Sets ``REQUESTS_CA_BUNDLE`` to point at the new bundle so that
        both the quick SSL recheck and all subsequent ``requests`` calls
        use it automatically.

        Returns True on success, False on any failure.
        """
        if not shutil.which("openssl"):
            if self.debug:
                print("  [debug] openssl not found on PATH")
            return False

        # --- pull cert chain via openssl -----------------------------------
        try:
            proc = subprocess.run(
                ["openssl", "s_client", "-showcerts", "-connect", f"{hostname}:443"],
                input=b"",
                capture_output=True,
                timeout=15,
            )
            output = proc.stdout.decode("utf-8", errors="replace")
        except (subprocess.TimeoutExpired, OSError) as exc:
            if self.debug:
                print(f"  [debug] openssl s_client failed: {exc}")
            return False

        # Extract all PEM blocks
        pem_blocks = re.findall(
            r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
            output,
            re.DOTALL,
        )

        if not pem_blocks:
            if self.debug:
                print("  [debug] No PEM certificates found in openssl output")
            return False

        # --- build combined bundle ----------------------------------------
        try:
            import certifi
            base_bundle = Path(certifi.where()).read_text()
        except Exception:
            base_bundle = ""

        combined = base_bundle.rstrip("\n") + "\n\n# --- Certificates pulled for " + hostname + " ---\n"
        for block in pem_blocks:
            combined += block + "\n"

        # --- write to ./certs/<hostname>.pem ------------------------------
        certs_dir = Path("./certs")
        certs_dir.mkdir(exist_ok=True)
        cert_path = certs_dir / f"{hostname}.pem"
        cert_path.write_text(combined)

        os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path.resolve())

        if self.debug:
            print(f"  [debug] Saved {len(pem_blocks)} cert(s) to {cert_path}")

        return True

    def _handle_ssl_failure(self, hostname: str, error: Exception) -> bool:
        """
        Interactive prompt when SSL auto-fix fails.

        Returns True if the user chose an option that allows us to continue,
        False if they chose to abort.
        """
        print(f"\n  SSL ERROR: {error}")
        print(f"  Python cannot verify the TLS certificate for {hostname}.")
        print("  This is common behind corporate proxies that perform SSL inspection.\n")
        print("  Options:")
        print("    [P] Provide path to your corporate CA certificate (.pem)")
        print("    [B] Bypass SSL verification (insecure – not recommended)")
        print("    [A] Abort")

        while True:
            try:
                choice = input("\n  Enter choice [P/B/A]: ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\n  Aborted by user.")
                return False

            if choice == "P":
                try:
                    cert_path = input("  Path to CA certificate: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Aborted by user.")
                    return False
                resolved = Path(cert_path).expanduser().resolve()
                if not resolved.is_file():
                    print(f"  File not found: {resolved}")
                    continue
                os.environ["REQUESTS_CA_BUNDLE"] = str(resolved)
                print(f"  Using CA bundle: {resolved}")
                return True

            elif choice == "B":
                os.environ["VEZA_UNSAFE_HTTPS"] = "true"
                os.environ.pop("REQUESTS_CA_BUNDLE", None)
                # Also disable SSL warnings so they don't clutter output
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                except ImportError:
                    pass
                print("  SSL verification disabled for this session.")
                return True

            elif choice == "A":
                print("  Aborting. Fix your CA certificates and try again.")
                return False

            else:
                print("  Invalid choice. Please enter P, B, or A.")

    def _print_conflicts(self, conflicts: List[Dict]):
        """Print conflict details."""
        print(f"\n  CONFLICTS FOUND: {len(conflicts)} provider(s) already exist in Veza")
        print("  " + "-"*56)

        for conflict in conflicts:
            print(f"\n  Provider: {conflict['provider_name']}")
            print(f"    - Application: {conflict['app_name']} (ID: {conflict['app_id']})")
            print(f"    - Veza Provider ID: {conflict['provider_id']}")

    def _print_resolution_options(self, conflicts: List[Dict]):
        """Print resolution options for dry-run mode."""
        print(f"\n  " + "="*56)
        print("  ACTION REQUIRED - Resolve conflicts before pushing:")
        print("  " + "="*56)

        if not self.provider_prefix:
            example_app = conflicts[0]["app_name"]
            example_current = conflicts[0]["provider_name"]
            example_prefixed = f"ODIE_{example_current}"

            print("\n  Option 1: Add a provider prefix (RECOMMENDED)")
            print("            Edit .env and uncomment PROVIDER_PREFIX:")
            print("            PROVIDER_PREFIX=ODIE")
            print(f"            This changes: {example_current}")
            print(f"                     to: {example_prefixed}")

            print("\n  Option 2: Delete existing providers in Veza UI")
            print("            Then run: python3 run.py --push")
            print("\n  Option 3: Skip existing providers")
            print("            Run: python3 run.py --push --skip-existing")
            print("\n  Option 4: Delete and recreate providers automatically")
            print("            Run: python3 run.py --push --delete-existing")
        else:
            print("\n  Option 1: Delete existing providers in Veza UI")
            print("            Then run: python3 run.py --push")
            print("\n  Option 2: Skip existing providers")
            print("            Run: python3 run.py --push --skip-existing")
            print("\n  Option 3: Delete and recreate providers automatically")
            print("            Run: python3 run.py --push --delete-existing")
            print("\n  Option 4: Change PROVIDER_PREFIX in .env")
            print(f"            Current prefix: {self.provider_prefix}")

    def _handle_resolution(self, result: PreflightResult, auto_mode: Optional[str]) -> PreflightResult:
        """Handle conflict resolution."""
        if auto_mode == "skip":
            print("\n  Auto-mode: Skipping all existing providers")
            for conflict in result.conflicts:
                result.skip_providers.add(conflict["provider_name"])
            return result

        if auto_mode == "delete":
            print("\n  Auto-mode: Will delete and recreate all existing providers")
            for conflict in result.conflicts:
                result.delete_providers.add(conflict["provider_name"])
            return result

        # Interactive mode
        print("\n  How would you like to proceed?")
        print("    [S] Skip existing providers (process only new ones)")
        print("    [D] Delete existing providers and recreate them")
        print("    [A] Abort - exit to resolve manually")
        print("    [C] Continue anyway (will likely fail)")

        while True:
            try:
                choice = input("\n  Enter choice [S/D/A/C]: ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\n  Aborted by user")
                result.proceed = False
                return result

            if choice == 'S':
                print("  Skipping existing providers...")
                for conflict in result.conflicts:
                    result.skip_providers.add(conflict["provider_name"])
                break
            elif choice == 'D':
                print("  Will delete existing providers before recreating...")
                for conflict in result.conflicts:
                    result.delete_providers.add(conflict["provider_name"])
                break
            elif choice == 'A':
                print("  Aborting. Resolve conflicts and try again.")
                result.proceed = False
                break
            elif choice == 'C':
                print("  Continuing - errors may occur")
                break
            else:
                print("  Invalid choice. Please enter S, D, A, or C.")

        return result
