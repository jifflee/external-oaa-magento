"""
================================================================================
ORCHESTRATOR - Processing Coordination (Core Module)
================================================================================

PURPOSE:
    Coordinates the OAA processing pipeline by delegating to specialized modules:
    - VezaClient: API interactions
    - ProviderRegistry: Provider ID tracking
    - PreflightChecker: Conflict detection
    - OutputManager: File management
    - DeploymentValidator: Identity mapping checks

    This is a CORE module - do not modify.

================================================================================
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from dotenv import load_dotenv

from .csv_loader import load_csv, group_by_application, get_unique_permissions
from .application_builder import build_application
from .output_manager import OutputManager
from .deployment_validator import DeploymentValidator
from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .preflight_checker import PreflightChecker

from config import KNOWN_PERMISSIONS, DEFAULT_SETTINGS, get_role_effective_permissions
from config.settings import PROXY_ENV_VARS


class MultiSourceOrchestrator:
    """
    Orchestrates multi-source OAA connector operations.

    Coordinates workflow between specialized modules for:
    - Configuration loading
    - Preflight conflict checking
    - CSV processing and application building
    - Veza API interactions
    - Results persistence
    """

    def __init__(self, env_file: str = "./.env"):
        """Initialize orchestrator with configuration."""
        # Load .env
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded configuration from: {env_file}")
        else:
            print(f"Warning: {env_file} not found, using defaults/environment")

        # Veza configuration
        self.veza_url = os.getenv("VEZA_URL", "")
        self.veza_api_key = os.getenv("VEZA_API_KEY", "")

        # Provider configuration
        self.provider_name = os.getenv("PROVIDER_NAME", DEFAULT_SETTINGS["PROVIDER_NAME"])
        self.provider_prefix = os.getenv("PROVIDER_PREFIX", DEFAULT_SETTINGS.get("PROVIDER_PREFIX", ""))

        # Input paths
        csv_filename = os.getenv("CSV_FILENAME", "")
        if csv_filename:
            self.csv_input_path = os.path.join("./data", csv_filename)
        else:
            self.csv_input_path = os.getenv("CSV_INPUT_PATH", f"./data/{DEFAULT_SETTINGS['CSV_FILENAME']}")

        # Output configuration
        output_dir = os.getenv("OUTPUT_DIR", DEFAULT_SETTINGS["OUTPUT_DIR"])
        retention_days = int(os.getenv("OUTPUT_RETENTION_DAYS", DEFAULT_SETTINGS["OUTPUT_RETENTION_DAYS"]))

        # Processing options
        self.dry_run = os.getenv("DRY_RUN", str(DEFAULT_SETTINGS["DRY_RUN"])).lower() == "true"
        self.save_json = os.getenv("SAVE_JSON", str(DEFAULT_SETTINGS["SAVE_JSON"])).lower() == "true"
        self.debug = os.getenv("DEBUG", str(DEFAULT_SETTINGS["DEBUG"])).lower() == "true"

        # Initialize modules
        self.output_manager = OutputManager(output_dir, self.provider_name, retention_days)
        self.veza_client = VezaClient(self.veza_url, self.veza_api_key, self.debug)
        self.registry = ProviderRegistry(output_dir, self.debug)
        self.preflight_checker = PreflightChecker(
            self.veza_client, self.registry, self.provider_prefix, self.debug
        )

    def validate_config(self) -> bool:
        """Validate configuration before running."""
        errors = []

        if not self.dry_run:
            if not self.veza_url:
                errors.append("VEZA_URL is required when DRY_RUN=false")
            if not self.veza_api_key:
                errors.append("VEZA_API_KEY is required when DRY_RUN=false")

        if not os.path.exists(self.csv_input_path):
            errors.append(f"CSV file not found: {self.csv_input_path}")

        if errors:
            print("\nConfiguration Errors:")
            for err in errors:
                print(f"  - {err}")
            return False

        return True

    def print_proxy_status(self):
        """Print proxy configuration status."""
        proxy_config = {}
        for var in PROXY_ENV_VARS:
            value = os.getenv(var)
            if value:
                display_value = value
                if '@' in value:
                    parts = value.split('@')
                    display_value = f"***@{parts[-1]}"
                proxy_config[var] = display_value

        if proxy_config:
            print("Proxy configuration:")
            for var, value in proxy_config.items():
                print(f"  {var}={value}")
        elif self.debug:
            print("Proxy: Not configured (direct connection)")

    def preflight_check(self, auto_mode: str = None, dry_run_check: bool = False) -> Dict[str, Any]:
        """Run preflight check for provider conflicts."""
        result = self.preflight_checker.check(
            self.csv_input_path,
            auto_mode=auto_mode,
            dry_run=dry_run_check
        )

        # Convert PreflightResult to dict for backward compatibility
        return {
            "proceed": result.proceed,
            "skip_providers": result.skip_providers,
            "delete_providers": result.delete_providers,
            "override_providers": result.override_providers,
            "conflicts": result.conflicts,
            "has_conflicts": result.has_conflicts
        }

    def process_all_applications(self, preflight_result: Dict = None) -> Dict[str, Any]:
        """Main processing: Load CSV, group by app, process each."""
        skip_providers = set()
        delete_providers = set()
        override_providers = set()

        if preflight_result:
            skip_providers = preflight_result.get("skip_providers", set())
            delete_providers = preflight_result.get("delete_providers", set())
            override_providers = preflight_result.get("override_providers", set())

        # Load full registry (provider + data source IDs) for ID-based updates
        registry_data = self.registry.load_full()

        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "csv_path": self.csv_input_path,
                "mode": "separate_integrations",
                "dry_run": self.dry_run,
            },
            "summary": {},
            "applications": [],
            "all_unclassified_permissions": set(),
            "errors": [],
            "skipped": [],
            "deleted_providers": [],
            "overridden_providers": list(override_providers)
        }

        # Load CSV
        print(f"\n{'='*60}")
        print("LOADING MULTI-SOURCE DATA")
        print('='*60)

        rows = load_csv(self.csv_input_path)
        print(f"Loaded {len(rows)} total rows from CSV")

        apps_data = group_by_application(rows)
        print(f"Found {len(apps_data)} unique applications to process")

        # Check permissions
        all_permissions = get_unique_permissions(rows)
        all_unclassified = {p for p in all_permissions if p.lower().strip() not in KNOWN_PERMISSIONS}

        print(f"Found {len(all_permissions)} unique permissions across all applications")

        if all_unclassified:
            print(f"\n*** NEEDS REVIEW: {len(all_unclassified)} unclassified permissions ***")
            for perm in sorted(all_unclassified):
                print(f"    - {perm}")
            results["all_unclassified_permissions"] = list(all_unclassified)

        # Create output directory
        self.output_manager.create_timestamped_dir()
        print(f"Output directory: {self.output_manager.current_dir}")

        # Delete providers that need to be recreated
        if delete_providers:
            print(f"\n{'='*60}")
            print("DELETING EXISTING PROVIDERS")
            print('='*60)
            for provider_name in delete_providers:
                if self._delete_provider(provider_name):
                    results["deleted_providers"].append(provider_name)

        # Process each application
        print(f"\n{'='*60}")
        print("PROCESSING INDIVIDUAL APPLICATIONS")
        print('='*60)

        total_apps = len(apps_data)
        successful = 0
        failed = 0
        skipped = 0

        for idx, (app_id, app_rows) in enumerate(apps_data.items(), 1):
            app_name = app_rows[0].get('Application_FIN_Name', app_id)
            provider_name = VezaClient.generate_provider_name(app_name, self.provider_prefix)

            if provider_name in skip_providers:
                print(f"\n[{idx}/{total_apps}] SKIPPED: {app_name} (provider exists)")
                results["skipped"].append({
                    "app_id": app_id,
                    "app_name": app_name,
                    "provider_name": provider_name,
                    "reason": "Provider already exists"
                })
                skipped += 1
                continue

            app_result = self._process_single_application(app_id, app_rows, idx, total_apps, registry_data)
            results["applications"].append(app_result)

            if app_result.get("success"):
                successful += 1
            else:
                failed += 1

        # Summary
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["summary"] = {
            "total_rows": len(rows),
            "total_applications": total_apps,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "all_permissions": sorted(all_permissions),
            "unclassified_permissions": sorted(all_unclassified) if all_unclassified else []
        }

        return results

    def _delete_provider(self, provider_name: str) -> bool:
        """Delete an existing provider by name."""
        try:
            provider = self.veza_client.get_provider(provider_name)
            if provider:
                print(f"  Deleting provider: {provider_name} (ID: {provider.get('id')})")
                self.veza_client.delete_provider(provider["id"])
                return True
            return False
        except Exception as e:
            print(f"  ERROR deleting provider {provider_name}: {e}")
            return False

    def _process_single_application(self, app_id: str, app_rows: List[Dict], current: int, total: int, registry_data: Dict = None) -> Dict:
        """Process a single application."""
        result = {
            "app_id": app_id,
            "success": False,
            "user_count": 0,
            "unclassified_permissions": []
        }

        try:
            app_name = app_rows[0].get('Application_FIN_Name', app_id)
            print(f"\n[{current}/{total}] Processing: {app_name} (ID: {app_id})")

            # Build application
            app, unclassified = build_application(app_id, app_rows)

            result["app_name"] = app.name
            result["user_count"] = len(app.local_users)
            result["role_count"] = len(app.local_roles)

            if unclassified:
                result["unclassified_permissions"] = list(unclassified)
                print(f"  Unclassified permissions: {list(unclassified)}")

            print(f"  Users: {result['user_count']}")

            # Display roles
            print(f"  Roles:")
            for role_id, role_obj in app.local_roles.items():
                display_name = role_obj.name if hasattr(role_obj, 'name') else role_id
                effective = get_role_effective_permissions(display_name)
                print(f"    - {display_name} -> {effective}")

            # Save JSON
            if self.save_json:
                safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in app_id)
                output_path = self.output_manager.get_output_path(f"{safe_name}_oaa.json")

                payload = app.get_payload()

                if "permissions" in payload:
                    for perm in payload["permissions"]:
                        if perm.get("name") == "?":
                            perm["description"] = "Uncategorized"

                with open(output_path, 'w') as f:
                    json.dump(payload, f, indent=2)

                result["json_path"] = output_path
                print(f"  Saved: {output_path}")

            # Push to Veza
            if not self.dry_run:
                provider_name = VezaClient.generate_provider_name(app_name, self.provider_prefix)

                # Check registry for stored IDs (provider + data source)
                stored = (registry_data or {}).get(provider_name, {})
                stored_provider_id = stored.get("id")
                stored_ds_list = stored.get("data_sources", [])
                stored_ds_id = stored_ds_list[0]["id"] if stored_ds_list else None

                if stored_provider_id and stored_ds_id:
                    # Update existing — push by ID to avoid creating duplicates
                    response = self.veza_client.push_application_by_ids(
                        app, stored_provider_id, stored_ds_id
                    )
                    result["provider_id"] = stored_provider_id
                    result["data_source_id"] = stored_ds_id
                    if self.debug:
                        print(f"  Pushed by ID (provider={stored_provider_id[:8]}..., ds={stored_ds_id[:8]}...)")
                else:
                    # New provider — use name-based creation
                    self.veza_client.ensure_provider(provider_name)
                    data_source_name = app_name
                    response = self.veza_client.push_application(app, provider_name, data_source_name)
                    result["data_source_name"] = data_source_name

                result["veza_response"] = response
                result["provider_name"] = provider_name
                print(f"  Pushed to Veza as integration: {provider_name}")

            result["success"] = True

        except Exception as e:
            error_msg = str(e)
            error_details = []

            if hasattr(e, 'error') and hasattr(e, 'message'):
                error_msg = f"{e.error}: {e.message}"
                if hasattr(e, 'status_code') and e.status_code:
                    error_msg += f" (HTTP {e.status_code})"

            if hasattr(e, 'details') and e.details:
                error_details = e.details

            result["error"] = error_msg
            result["error_details"] = error_details

            print(f"  ERROR: {error_msg}")
            if error_details:
                print(f"  Details:")
                for detail in error_details:
                    if isinstance(detail, dict):
                        for k, v in detail.items():
                            print(f"    {k}: {v}")
                    else:
                        print(f"    - {detail}")

            if self.debug:
                import traceback
                traceback.print_exc()

        return result

    def print_summary(self, results: Dict):
        """Print processing summary."""
        print(f"\n{'='*60}")
        print("PROCESSING COMPLETE")
        print('='*60)

        summary = results.get("summary", {})
        print(f"Total Rows Processed: {summary.get('total_rows', 0)}")
        print(f"Total Applications: {summary.get('total_applications', 0)}")
        print(f"Successful: {summary.get('successful', 0)}")
        print(f"Failed: {summary.get('failed', 0)}")
        print(f"Skipped: {summary.get('skipped', 0)}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE PUSH'}")

        if results.get("overridden_providers"):
            print(f"\nOverridden Providers (updated from previous run):")
            for provider in results["overridden_providers"]:
                print(f"  - {provider}")

        if results.get("deleted_providers"):
            print(f"\nDeleted Providers (recreated):")
            for provider in results["deleted_providers"]:
                print(f"  - {provider}")

        if results.get("skipped"):
            print(f"\nSkipped Applications (provider already exists):")
            for skip in results["skipped"]:
                print(f"  - {skip['app_name']} ({skip['provider_name']})")

        if summary.get("unclassified_permissions"):
            print(f"\n*** NEEDS REVIEW - Unclassified Permissions: ***")
            for perm in summary["unclassified_permissions"]:
                print(f"  - {perm}")

        errors = [a for a in results.get("applications", []) if a.get("error")]
        if errors:
            print(f"\nFailed Applications:")
            for err in errors:
                print(f"  - {err['app_id']}: {err['error']}")

        # Notify user about dry run mode
        if self.dry_run:
            print(f"\n{'='*60}")
            print("NEXT STEPS")
            print('='*60)
            print("  You are in DRY RUN mode - no data was pushed to Veza.")
            print("\n  When ready to push to Veza:")
            print("    Option 1: python3 run.py --push")
            print("    Option 2: Set DRY_RUN=false in .env, then run python3 run.py")

    def save_results(self, results: Dict) -> str:
        """Save results JSON to output folder and persist provider IDs."""
        results_path = self.output_manager.get_output_path("multi_source_results.json")

        if isinstance(results.get("all_unclassified_permissions"), set):
            results["all_unclassified_permissions"] = list(results["all_unclassified_permissions"])

        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Save provider IDs
        if not self.dry_run:
            self._save_provider_ids(results)

        return results_path

    def _save_provider_ids(self, results: Dict):
        """Save provider and data source IDs for next run correlation."""
        successful_apps = [
            app for app in results.get("applications", [])
            if app.get("success") and app.get("provider_name")
        ]

        if not successful_apps:
            return

        providers = []
        for app in successful_apps:
            provider_name = app.get("provider_name")
            provider = self.veza_client.get_provider(provider_name)
            if provider:
                provider_id = provider.get("id")

                # Fetch data source IDs for this provider
                data_sources = []
                try:
                    ds_list = self.veza_client.get_data_sources(provider_id)
                    for ds in ds_list:
                        data_sources.append({
                            "name": ds.get("name"),
                            "id": ds.get("id"),
                        })
                except Exception as e:
                    if self.debug:
                        print(f"  DEBUG: Could not fetch data sources for {provider_name}: {e}")

                providers.append({
                    "name": provider_name,
                    "id": provider_id,
                    "app_id": app.get("app_id"),
                    "app_name": app.get("app_name"),
                    "data_sources": data_sources,
                })

        if providers:
            path = self.registry.save(providers, self.veza_url, self.provider_prefix)
            print(f"  Provider IDs saved to: {path}")

            # Also save to timestamped folder
            if self.output_manager.current_dir:
                timestamped_path = self.output_manager.get_output_path("oaa_provider_ids.json")
                with open(timestamped_path, 'w') as f:
                    json.dump({
                        "generated_at": results.get("completed_at"),
                        "veza_url": self.veza_url,
                        "provider_prefix": self.provider_prefix,
                        "providers": providers
                    }, f, indent=2)

    def validate_identity_mapping(self, idp_type: str = "activedirectory", save_results: bool = True) -> Dict[str, Any]:
        """Validate identity mapping configuration after deployment."""
        if not self.veza_url or not self.veza_api_key:
            print("\n  SKIPPED: Identity mapping validation requires VEZA_URL and VEZA_API_KEY")
            return {"validation_skipped": True, "reason": "No Veza credentials"}

        validator = DeploymentValidator(
            veza_url=self.veza_url,
            veza_api_key=self.veza_api_key,
            output_dir=self.output_manager.current_dir or self.output_manager.base_dir
        )
        validator.debug = self.debug

        results = validator.validate(
            idp_type=idp_type,
            provider_prefix=self.provider_prefix,
            print_output=True
        )

        if save_results and self.output_manager.current_dir:
            output_path = self.output_manager.get_output_path("identity_mapping_validation.json")
            validator.save_results(results, output_path)
            print(f"  Validation results saved to: {output_path}")

        return results

    def revalidate_identity_mapping(self, idp_type: str = "activedirectory") -> Dict[str, Any]:
        """Re-check identity mapping if previous validation failed."""
        if not self.veza_url or not self.veza_api_key:
            print("\n  SKIPPED: Re-validation requires VEZA_URL and VEZA_API_KEY")
            return {"validation_skipped": True, "reason": "No Veza credentials"}

        validator = DeploymentValidator(
            veza_url=self.veza_url,
            veza_api_key=self.veza_api_key,
            output_dir=self.output_manager.base_dir
        )
        validator.debug = self.debug

        return validator.revalidate_if_failed(
            idp_type=idp_type,
            provider_prefix=self.provider_prefix
        )
