"""
REST Orchestrator - Pipeline coordination for Magento B2B REST -> Veza OAA.

Steps:
1. Authenticate with Magento (REST token)
2. GET /V1/customers/me (current user + company_id)
3. GET /V1/company/{id} (company details)
4. GET /V1/company/role?company_id=X (roles + permissions)
5. GET /V1/hierarchy/{companyId} (hierarchy, IDs only)
6. GET /V1/team/{id} x N (team details)
7. role_gap_handler (workaround for user-role)
8. Transform -> OAA CustomApplication
9. Push to Veza or save JSON
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

from .magento_client import MagentoRESTClient
from .entity_extractor import EntityExtractor
from .application_builder import ApplicationBuilder
from .relationship_builder import RelationshipBuilder
from .role_gap_handler import RoleGapHandler
from .output_manager import OutputManager
from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .preflight_checker import PreflightChecker

from config import DEFAULT_SETTINGS
from config.settings import PROXY_ENV_VARS


class RESTOrchestrator:
    """Orchestrates the REST extraction pipeline."""

    def __init__(self, env_file: str = "./.env"):
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded configuration from: {env_file}")
        else:
            print(f"Warning: {env_file} not found, using defaults/environment")

        # Magento configuration
        self.store_url = os.getenv("MAGENTO_STORE_URL", "")
        self.username = os.getenv("MAGENTO_USERNAME", "")
        self.password = os.getenv("MAGENTO_PASSWORD", "")

        # Veza configuration
        self.veza_url = os.getenv("VEZA_URL", "")
        self.veza_api_key = os.getenv("VEZA_API_KEY", "")

        # Provider configuration
        self.provider_name = os.getenv("PROVIDER_NAME", DEFAULT_SETTINGS["PROVIDER_NAME"])
        self.provider_prefix = os.getenv("PROVIDER_PREFIX", DEFAULT_SETTINGS.get("PROVIDER_PREFIX", ""))

        # Output configuration
        output_dir = os.getenv("OUTPUT_DIR", DEFAULT_SETTINGS["OUTPUT_DIR"])
        retention_days = int(os.getenv("OUTPUT_RETENTION_DAYS", str(DEFAULT_SETTINGS["OUTPUT_RETENTION_DAYS"])))

        # Processing options
        self.dry_run = os.getenv("DRY_RUN", str(DEFAULT_SETTINGS["DRY_RUN"])).lower() == "true"
        self.save_json = os.getenv("SAVE_JSON", str(DEFAULT_SETTINGS["SAVE_JSON"])).lower() == "true"
        self.debug = os.getenv("DEBUG", str(DEFAULT_SETTINGS["DEBUG"])).lower() == "true"

        # REST-specific options
        self.user_role_strategy = os.getenv("USER_ROLE_STRATEGY", DEFAULT_SETTINGS.get("USER_ROLE_STRATEGY", "default_role"))
        self.user_role_mapping_path = os.getenv("USER_ROLE_MAPPING_PATH", DEFAULT_SETTINGS.get("USER_ROLE_MAPPING_PATH", ""))

        # Initialize modules
        self.output_manager = OutputManager(output_dir, self.provider_name, retention_days)
        self.veza_client = VezaClient(self.veza_url, self.veza_api_key, self.debug)
        self.registry = ProviderRegistry(output_dir, self.debug)
        self.preflight_checker = PreflightChecker(
            self.veza_client, self.registry, self.provider_prefix, self.debug
        )

    def validate_config(self) -> bool:
        errors = []
        if not self.store_url:
            errors.append("MAGENTO_STORE_URL is required")
        if not self.username:
            errors.append("MAGENTO_USERNAME is required")
        if not self.password:
            errors.append("MAGENTO_PASSWORD is required")
        if not self.dry_run:
            if not self.veza_url:
                errors.append("VEZA_URL is required when DRY_RUN=false")
            if not self.veza_api_key:
                errors.append("VEZA_API_KEY is required when DRY_RUN=false")

        if errors:
            print("\nConfiguration Errors:")
            for err in errors:
                print(f"  - {err}")
            return False
        return True

    def run(self) -> Dict[str, Any]:
        """Execute the full REST extraction pipeline."""
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "connector": "rest",
            "config": {
                "store_url": self.store_url,
                "dry_run": self.dry_run,
                "user_role_strategy": self.user_role_strategy,
            },
            "success": False,
        }

        try:
            # Step 1: Authenticate
            print(f"\n{'='*60}")
            print("STEP 1: AUTHENTICATION")
            print("="*60)
            magento = MagentoRESTClient(
                self.store_url, self.username, self.password, self.debug
            )
            magento.authenticate()
            print("  Authentication successful")

            # Step 2: Get current user
            print(f"\n{'='*60}")
            print("STEP 2: GET CURRENT USER")
            print("="*60)
            current_user = magento.get_current_user()
            company_attrs = current_user.get("extension_attributes", {}).get("company_attributes", {})
            company_id = company_attrs.get("company_id")
            print(f"  User: {current_user.get('email')}")
            print(f"  Company ID: {company_id}")

            if not company_id:
                raise RuntimeError("User is not associated with a company")

            # Step 3: Get company details
            print(f"\n{'='*60}")
            print("STEP 3: GET COMPANY DETAILS")
            print("="*60)
            company = magento.get_company(company_id)
            print(f"  Company: {company.get('company_name')}")

            # Step 4: Get roles
            print(f"\n{'='*60}")
            print("STEP 4: GET COMPANY ROLES")
            print("="*60)
            roles = magento.get_company_roles(company_id)
            print(f"  Found {len(roles)} roles")

            # Step 5: Get hierarchy
            print(f"\n{'='*60}")
            print("STEP 5: GET HIERARCHY")
            print("="*60)
            hierarchy = magento.get_hierarchy(company_id)
            print("  Hierarchy retrieved")

            # Step 6: Get team details
            print(f"\n{'='*60}")
            print("STEP 6: GET TEAM DETAILS")
            print("="*60)
            team_ids = self._extract_team_ids(hierarchy)
            team_details = {}
            for tid in team_ids:
                try:
                    team_details[tid] = magento.get_team(tid)
                except Exception as e:
                    if self.debug:
                        print(f"  Warning: Could not fetch team {tid}: {e}")
            print(f"  Fetched {len(team_details)} team details")

            # Step 7: Extract entities
            print(f"\n{'='*60}")
            print("STEP 7: EXTRACT ENTITIES")
            print("="*60)
            extractor = EntityExtractor(self.debug)
            entities = extractor.extract(current_user, company, roles, hierarchy, team_details)
            print(f"  Users: {len(entities['users'])}")
            print(f"  Teams: {len(entities['teams'])}")
            print(f"  Roles: {len(entities['roles'])}")

            # Step 8: Handle user-role gap
            print(f"\n{'='*60}")
            print("STEP 8: USER-ROLE GAP HANDLING")
            print("="*60)
            gap_handler = RoleGapHandler(
                strategy=self.user_role_strategy,
                csv_path=self.user_role_mapping_path,
                debug=self.debug,
            )
            entities["users"] = gap_handler.resolve(
                entities["users"], entities["roles"], entities["company"]["id"]
            )

            # Step 9: Build OAA application
            print(f"\n{'='*60}")
            print("STEP 9: BUILD OAA APPLICATION")
            print("="*60)
            builder = ApplicationBuilder(self.store_url, self.debug)
            app = builder.build(entities)
            print(f"  Application built: {app.name}")

            # Step 10: Build relationships
            print(f"\n{'='*60}")
            print("STEP 10: BUILD RELATIONSHIPS")
            print("="*60)
            rel_builder = RelationshipBuilder(self.debug)
            rel_builder.build_all(app, entities)
            print("  Relationships built")

            # Create output directory
            self.output_manager.create_timestamped_dir()

            # Save / Push
            if self.save_json:
                payload = app.get_payload()
                json_path = self.output_manager.get_output_path("oaa_payload.json")
                with open(json_path, "w") as f:
                    json.dump(payload, f, indent=2)
                results["json_path"] = json_path
                print(f"  Saved OAA payload: {json_path}")

            if not self.dry_run:
                print(f"\n{'='*60}")
                print("STEP 11: PUSH TO VEZA")
                print("="*60)

                preflight = self.preflight_checker.check(self.provider_name, dry_run=False)

                provider_name = VezaClient.generate_provider_name(
                    self.provider_name, self.provider_prefix
                )

                if preflight.override_provider and preflight.existing_provider_id:
                    if preflight.existing_data_source_id:
                        response = self.veza_client.push_application_by_ids(
                            app, preflight.existing_provider_id, preflight.existing_data_source_id,
                        )
                    else:
                        self.veza_client.ensure_provider(provider_name)
                        response = self.veza_client.push_application(
                            app, provider_name, entities["company"]["name"],
                        )
                else:
                    self.veza_client.ensure_provider(provider_name)
                    response = self.veza_client.push_application(
                        app, provider_name, entities["company"]["name"],
                    )

                results["veza_response"] = response
                results["provider_name"] = provider_name
                print(f"  Pushed to Veza as: {provider_name}")

                self._save_provider_ids(provider_name, entities["company"])

            results["success"] = True
            results["summary"] = {
                "company": entities["company"]["name"],
                "users": len(entities["users"]),
                "teams": len(entities["teams"]),
                "roles": len(entities["roles"]),
                "user_role_strategy": self.user_role_strategy,
            }

        except Exception as e:
            results["error"] = str(e)
            print(f"\n  ERROR: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()

        results["completed_at"] = datetime.now(timezone.utc).isoformat()

        if self.output_manager.current_dir:
            results_path = self.output_manager.get_output_path("extraction_results.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)

        return results

    def _extract_team_ids(self, hierarchy: Dict) -> list:
        """Extract team IDs from hierarchy tree for per-team GET calls."""
        team_ids = []
        self._walk_hierarchy_for_teams(hierarchy, team_ids)
        return team_ids

    def _walk_hierarchy_for_teams(self, node: Dict, team_ids: list):
        if not node:
            return
        if node.get("entity_type", "").lower() == "team":
            entity_id = node.get("entity_id")
            if entity_id:
                team_ids.append(entity_id)
        for child in node.get("children", []):
            self._walk_hierarchy_for_teams(child, team_ids)

    def _save_provider_ids(self, provider_name: str, company: Dict):
        try:
            provider = self.veza_client.get_provider(provider_name)
            if provider:
                provider_id = provider.get("id")
                data_sources = []
                try:
                    ds_list = self.veza_client.get_data_sources(provider_id)
                    for ds in ds_list:
                        data_sources.append({"name": ds.get("name"), "id": ds.get("id")})
                except Exception:
                    pass
                providers = [{
                    "name": provider_name,
                    "id": provider_id,
                    "app_name": company.get("name", ""),
                    "data_sources": data_sources,
                }]
                self.registry.save(providers, self.veza_url, self.provider_prefix)
        except Exception:
            pass

    def print_summary(self, results: Dict):
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print("="*60)
        print(f"Status: {'SUCCESS' if results.get('success') else 'FAILED'}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE PUSH'}")

        summary = results.get("summary", {})
        if summary:
            print(f"Company: {summary.get('company', 'N/A')}")
            print(f"Users: {summary.get('users', 0)}")
            print(f"Teams: {summary.get('teams', 0)}")
            print(f"Roles: {summary.get('roles', 0)}")
            print(f"User-Role Strategy: {summary.get('user_role_strategy', 'N/A')}")

        if results.get("error"):
            print(f"Error: {results['error']}")

        if self.dry_run:
            print(f"\nNEXT STEPS:")
            print("  You are in DRY RUN mode - no data was pushed to Veza.")
            print("  When ready: python run.py --push")
