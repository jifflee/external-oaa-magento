"""
GraphQL Orchestrator - Pipeline coordination for Magento B2B -> Veza OAA.

Steps:
1. Authenticate with Magento (REST token)
2. Execute GraphQL extraction query
3. Optionally fetch REST role supplement
4. Extract entities from response
5. Build OAA CustomApplication
6. Build relationships
7. Push to Veza or save JSON
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

from .magento_client import MagentoGraphQLClient
from .graphql_queries import FULL_EXTRACTION_QUERY
from .entity_extractor import EntityExtractor, decode_graphql_id
from .application_builder import ApplicationBuilder
from .relationship_builder import RelationshipBuilder
from .output_manager import OutputManager
from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .preflight_checker import PreflightChecker

from config import DEFAULT_SETTINGS
from config.settings import PROXY_ENV_VARS


class GraphQLOrchestrator:
    """Orchestrates the GraphQL extraction pipeline."""

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
        self.use_rest_supplement = (
            os.getenv(
                "USE_REST_ROLE_SUPPLEMENT",
                str(DEFAULT_SETTINGS.get("USE_REST_ROLE_SUPPLEMENT", True)),
            ).lower()
            == "true"
        )

        # Initialize modules
        self.output_manager = OutputManager(output_dir, self.provider_name, retention_days)
        self.veza_client = VezaClient(self.veza_url, self.veza_api_key, self.debug)
        self.registry = ProviderRegistry(output_dir, self.debug)
        self.preflight_checker = PreflightChecker(
            self.veza_client, self.registry, self.provider_prefix, self.debug
        )

    def validate_config(self) -> bool:
        """Validate configuration."""
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
        """Execute the full extraction pipeline."""
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "connector": "graphql",
            "config": {
                "store_url": self.store_url,
                "dry_run": self.dry_run,
                "use_rest_supplement": self.use_rest_supplement,
            },
            "success": False,
        }

        try:
            # Step 1: Authenticate
            print(f"\n{'='*60}")
            print("STEP 1: AUTHENTICATION")
            print("="*60)
            magento = MagentoGraphQLClient(
                self.store_url, self.username, self.password, self.debug
            )
            magento.authenticate()
            print("  Authentication successful")

            # Step 2: GraphQL extraction
            print(f"\n{'='*60}")
            print("STEP 2: GRAPHQL EXTRACTION")
            print("="*60)
            graphql_data = magento.execute_graphql(FULL_EXTRACTION_QUERY)
            print("  GraphQL query executed successfully")

            # Step 3: Optional REST role supplement
            rest_roles = None
            if self.use_rest_supplement:
                print(f"\n{'='*60}")
                print("STEP 3: REST ROLE SUPPLEMENT")
                print("="*60)
                try:
                    company_data = graphql_data.get("company", {})
                    company_id = decode_graphql_id(company_data.get("id", ""))
                    if company_id:
                        rest_roles = magento.get_company_roles_rest(company_id)
                        print(f"  Fetched {len(rest_roles)} roles via REST")
                except Exception as e:
                    print(f"  Warning: REST role supplement failed: {e}")
                    print("  Continuing without explicit permission data")

            # Step 4: Extract entities
            print(f"\n{'='*60}")
            print("STEP 4: ENTITY EXTRACTION")
            print("="*60)
            extractor = EntityExtractor(self.debug)
            entities = extractor.extract(graphql_data)
            print(f"  Company: {entities['company']['name']}")
            print(f"  Users: {len(entities['users'])}")
            print(f"  Teams: {len(entities['teams'])}")
            print(f"  Roles: {len(entities['roles'])}")

            # Step 5: Build OAA application
            print(f"\n{'='*60}")
            print("STEP 5: BUILD OAA APPLICATION")
            print("="*60)
            builder = ApplicationBuilder(self.store_url, self.debug)
            app = builder.build(entities)
            print(f"  Application built: {app.name}")

            # Step 6: Build relationships
            print(f"\n{'='*60}")
            print("STEP 6: BUILD RELATIONSHIPS")
            print("="*60)
            rel_builder = RelationshipBuilder(self.debug)
            rel_builder.build_all(app, entities, rest_roles)
            print("  Relationships built")

            # Create output directory
            self.output_manager.create_timestamped_dir()

            # Step 7: Save JSON / Push to Veza
            if self.save_json:
                payload = app.get_payload()
                json_path = self.output_manager.get_output_path("oaa_payload.json")
                with open(json_path, "w") as f:
                    json.dump(payload, f, indent=2)
                results["json_path"] = json_path
                print(f"  Saved OAA payload: {json_path}")

            if not self.dry_run:
                print(f"\n{'='*60}")
                print("STEP 7: PUSH TO VEZA")
                print("="*60)

                # Preflight check
                preflight = self.preflight_checker.check(
                    self.provider_name, dry_run=False
                )

                if preflight.has_conflicts:
                    print("  WARNING: Provider conflicts detected")
                    for conflict in preflight.conflicts:
                        print(f"    - {conflict['provider_name']}: {conflict['reason']}")

                provider_name = VezaClient.generate_provider_name(
                    self.provider_name, self.provider_prefix
                )

                if preflight.override_provider and preflight.existing_provider_id:
                    if preflight.existing_data_source_id:
                        response = self.veza_client.push_application_by_ids(
                            app,
                            preflight.existing_provider_id,
                            preflight.existing_data_source_id,
                        )
                    else:
                        self.veza_client.ensure_provider(provider_name)
                        response = self.veza_client.push_application(
                            app,
                            provider_name,
                            entities["company"]["name"],
                        )
                else:
                    self.veza_client.ensure_provider(provider_name)
                    response = self.veza_client.push_application(
                        app,
                        provider_name,
                        entities["company"]["name"],
                    )

                results["veza_response"] = response
                results["provider_name"] = provider_name
                print(f"  Pushed to Veza as: {provider_name}")

                # Save provider IDs
                self._save_provider_ids(provider_name, entities["company"])

            results["success"] = True
            results["summary"] = {
                "company": entities["company"]["name"],
                "users": len(entities["users"]),
                "teams": len(entities["teams"]),
                "roles": len(entities["roles"]),
            }

        except Exception as e:
            results["error"] = str(e)
            print(f"\n  ERROR: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()

        results["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Save results
        if self.output_manager.current_dir:
            results_path = self.output_manager.get_output_path("extraction_results.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  Results saved to: {results_path}")

        return results

    def _save_provider_ids(self, provider_name: str, company: Dict):
        """Save provider IDs after successful push."""
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

                providers = [
                    {
                        "name": provider_name,
                        "id": provider_id,
                        "app_name": company.get("name", ""),
                        "data_sources": data_sources,
                    }
                ]
                self.registry.save(providers, self.veza_url, self.provider_prefix)
        except Exception as e:
            if self.debug:
                print(f"  Warning: Could not save provider IDs: {e}")

    def print_summary(self, results: Dict):
        """Print execution summary."""
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

        if results.get("error"):
            print(f"Error: {results['error']}")

        if self.dry_run:
            print(f"\nNEXT STEPS:")
            print("  You are in DRY RUN mode - no data was pushed to Veza.")
            print("  When ready: python run.py --push")
