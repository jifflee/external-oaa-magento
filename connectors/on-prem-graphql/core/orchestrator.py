"""
GraphQL Orchestrator — Pipeline coordination for Magento B2B data extraction.

This module is the core of the extraction pipeline. It ties together all other
modules (MagentoGraphQLClient, EntityExtractor, ApplicationBuilder,
RelationshipBuilder) into a sequential 7-step workflow:

  Step 1: AUTHENTICATION
      Calls MagentoGraphQLClient.authenticate() to obtain a customer JWT token
      via POST /rest/V1/integration/customer/token.

  Step 2: GRAPHQL EXTRACTION
      Executes the FULL_EXTRACTION_QUERY (a single GraphQL call) to retrieve
      the complete B2B company structure: company info, users, teams, roles,
      and organizational hierarchy.

  Step 3: REST ROLE SUPPLEMENT (optional)
      If USE_REST_ROLE_SUPPLEMENT is enabled, calls GET /rest/V1/company/role
      to fetch per-role ACL permission trees with explicit allow/deny values.
      Without this, roles are extracted but their permissions are unknown.

  Step 4: ENTITY EXTRACTION
      Passes the raw GraphQL response to EntityExtractor, which normalizes it
      into a dict of {company, users, teams, roles, hierarchy, admin_email}.

  Step 5: BUILD OAA APPLICATION
      ApplicationBuilder creates a Veza OAA CustomApplication and populates it
      with users, groups (company + teams), roles, and the 34 ACL permissions.

  Step 6: BUILD RELATIONSHIPS
      RelationshipBuilder wires 6 relationship types: user→company,
      user→team, user→role, role→permission, team→company, user→user (reports_to).

  Step 7: SAVE OUTPUT
      Serializes the OAA payload to JSON in a timestamped output directory.

Configuration:
    All settings are loaded from environment variables (typically via .env file).
    Required: MAGENTO_STORE_URL, MAGENTO_USERNAME, MAGENTO_PASSWORD.
    See config/settings.py for defaults.

Typical usage:
    orchestrator = GraphQLOrchestrator(env_file="./.env")
    if orchestrator.validate_config():
        results = orchestrator.run()
        orchestrator.print_summary(results)
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

import requests

from .magento_client import MagentoGraphQLClient
from .graphql_queries import FULL_EXTRACTION_QUERY
from .entity_extractor import EntityExtractor, decode_graphql_id
from .application_builder import ApplicationBuilder
from .relationship_builder import RelationshipBuilder
from .ce_data_builder import build_synthetic_graphql_response, build_synthetic_roles_response

from magento_oaa_shared import OutputManager

from config import DEFAULT_SETTINGS


class GraphQLOrchestrator:
    """Orchestrates the Magento B2B GraphQL extraction pipeline.

    Attributes:
        store_url: Base URL of the Magento store (e.g., "https://magento.example.com").
        username: Magento customer email (must be a B2B company admin).
        password: Magento customer password.
        provider_name: Label used in output folder naming (default: "Magento_OnPrem_GraphQL").
        save_json: Whether to write OAA payload to disk (default: True).
        debug: Whether to enable verbose output (default: False).
        use_rest_supplement: Whether to call REST for per-role permissions (default: True).
        ce_mode: If True, use CE fallback (synthetic B2B from real CE customers).
        admin_username: Admin username for CE mode REST API access.
        admin_password: Admin password for CE mode REST API access.
        output_manager: Handles timestamped output directories and retention cleanup.
    """

    def __init__(self, env_file: str = "./.env"):
        """Initialize the orchestrator by loading configuration from environment.

        Args:
            env_file: Path to a .env file. If the file exists, it is loaded via
                      python-dotenv. Otherwise, falls back to system environment.
        """
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded configuration from: {env_file}")
        else:
            print(f"Warning: {env_file} not found, using defaults/environment")

        # Magento connection credentials (required)
        self.store_url = os.getenv("MAGENTO_STORE_URL", "")
        self.username = os.getenv("MAGENTO_USERNAME", "")
        self.password = os.getenv("MAGENTO_PASSWORD", "")

        # Provider name — used only for naming the output folder
        self.provider_name = os.getenv("PROVIDER_NAME", DEFAULT_SETTINGS["PROVIDER_NAME"])

        # Output directory and how many days to keep old runs
        output_dir = os.getenv("OUTPUT_DIR", DEFAULT_SETTINGS["OUTPUT_DIR"])
        retention_days = int(os.getenv("OUTPUT_RETENTION_DAYS", str(DEFAULT_SETTINGS["OUTPUT_RETENTION_DAYS"])))

        # Processing options
        self.save_json = os.getenv("SAVE_JSON", str(DEFAULT_SETTINGS["SAVE_JSON"])).lower() == "true"
        self.debug = os.getenv("DEBUG", str(DEFAULT_SETTINGS["DEBUG"])).lower() == "true"
        self.use_rest_supplement = (
            os.getenv(
                "USE_REST_ROLE_SUPPLEMENT",
                str(DEFAULT_SETTINGS.get("USE_REST_ROLE_SUPPLEMENT", True)),
            ).lower()
            == "true"
        )

        # CE fallback mode settings
        self.ce_mode = (
            os.getenv("CE_MODE", str(DEFAULT_SETTINGS.get("CE_MODE", False))).lower() == "true"
        )
        self.admin_username = os.getenv("MAGENTO_ADMIN_USERNAME", "")
        self.admin_password = os.getenv("MAGENTO_ADMIN_PASSWORD", "")

        # Initialize the output manager (creates timestamped dirs, handles cleanup)
        self.output_manager = OutputManager(output_dir, self.provider_name, retention_days)

    def validate_config(self) -> bool:
        """Validate that all required configuration values are present.

        Checks:
            - MAGENTO_STORE_URL is set
            - MAGENTO_USERNAME and MAGENTO_PASSWORD are set
            - In CE mode: MAGENTO_ADMIN_USERNAME and MAGENTO_ADMIN_PASSWORD are set

        Returns:
            True if all required values are present, False otherwise.
            Prints specific error messages for each missing value.
        """
        errors = []
        if not self.store_url:
            errors.append("MAGENTO_STORE_URL is required")
        if not self.username:
            errors.append("MAGENTO_USERNAME is required")
        if not self.password:
            errors.append("MAGENTO_PASSWORD is required")

        if self.ce_mode:
            if not self.admin_username:
                errors.append("MAGENTO_ADMIN_USERNAME is required for CE mode")
            if not self.admin_password:
                errors.append("MAGENTO_ADMIN_PASSWORD is required for CE mode")

        if errors:
            print("\nConfiguration Errors:")
            for err in errors:
                print(f"  - {err}")
            return False
        return True

    def run(self) -> Dict[str, Any]:
        """Execute the full 7-step extraction pipeline.

        Returns:
            A dict containing:
                - started_at/completed_at: ISO timestamps
                - connector: "magento-graphql"
                - config: Store URL and REST supplement setting
                - success: True if all steps completed without error
                - summary: Entity counts (company, users, teams, roles)
                - json_path: Path to saved OAA payload (if save_json=True)
                - error: Error message (if success=False)
        """
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "connector": "magento-graphql",
            "config": {
                "store_url": self.store_url,
                "use_rest_supplement": self.use_rest_supplement,
                "ce_mode": self.ce_mode,
            },
            "success": False,
        }

        try:
            # Step 1: Authenticate with Magento
            print(f"\n{'='*60}")
            print("STEP 1: AUTHENTICATION")
            print("="*60)
            magento = MagentoGraphQLClient(
                self.store_url, self.username, self.password, self.debug
            )
            magento.authenticate()
            print("  Authentication successful")

            # Steps 2-3: Data acquisition (CE mode or standard GraphQL)
            if self.ce_mode:
                graphql_data, rest_roles = self._extract_ce_data()
            else:
                graphql_data, rest_roles = self._extract_graphql_data(magento)

            # Step 4: Parse GraphQL response into normalized entities
            print(f"\n{'='*60}")
            print("STEP 4: ENTITY EXTRACTION")
            print("="*60)
            extractor = EntityExtractor(self.debug)
            entities = extractor.extract(graphql_data)
            print(f"  Company: {entities['company']['name']}")
            print(f"  Users: {len(entities['users'])}")
            print(f"  Teams: {len(entities['teams'])}")
            print(f"  Roles: {len(entities['roles'])}")

            # Step 5: Build the OAA CustomApplication structure
            print(f"\n{'='*60}")
            print("STEP 5: BUILD OAA APPLICATION")
            print("="*60)
            builder = ApplicationBuilder(self.store_url, self.debug)
            app = builder.build(entities)
            print(f"  Application built: {app.name}")

            # Step 6: Wire all entity relationships
            print(f"\n{'='*60}")
            print("STEP 6: BUILD RELATIONSHIPS")
            print("="*60)
            rel_builder = RelationshipBuilder(self.debug)
            rel_builder.build_all(app, entities, rest_roles)
            print("  Relationships built")

            # Step 7: Save output to timestamped directory
            print(f"\n{'='*60}")
            print("STEP 7: SAVE OUTPUT")
            print("="*60)

            self.output_manager.create_timestamped_dir()

            if self.save_json:
                payload = app.get_payload()
                json_path = self.output_manager.get_output_path("oaa_payload.json")
                with open(json_path, "w") as f:
                    json.dump(payload, f, indent=2)
                results["json_path"] = json_path
                print(f"  Saved OAA payload: {json_path}")

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

        # Save run metadata alongside the OAA payload
        if self.output_manager.current_dir:
            results_path = self.output_manager.get_output_path("extraction_results.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  Results saved to: {results_path}")

        return results

    def _extract_graphql_data(self, magento: MagentoGraphQLClient):
        """Standard data acquisition: GraphQL query + optional REST supplement.

        Returns:
            Tuple of (graphql_data, rest_roles) where rest_roles may be None.
        """
        # Step 2: Execute the single GraphQL extraction query
        print(f"\n{'='*60}")
        print("STEP 2: GRAPHQL EXTRACTION")
        print("="*60)
        graphql_data = magento.execute_graphql(FULL_EXTRACTION_QUERY)
        print("  GraphQL query executed successfully")

        # Step 3: Optionally fetch per-role permissions via REST
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

        return graphql_data, rest_roles

    def _extract_ce_data(self):
        """CE fallback: fetch real customers via REST, build synthetic B2B structures.

        Uses admin credentials to call the Magento REST API for customer data,
        then wraps those identities in synthetic B2B company/team/role structures.

        Returns:
            Tuple of (graphql_data, rest_roles) in the same format as standard mode.
        """
        # Step 2: Fetch real CE customers via admin REST API
        print(f"\n{'='*60}")
        print("STEP 2: CE MODE - FETCH CUSTOMERS VIA REST")
        print("="*60)

        admin_user = self.admin_username
        admin_pass = self.admin_password
        if not admin_user or not admin_pass:
            raise ValueError(
                "CE mode requires MAGENTO_ADMIN_USERNAME and MAGENTO_ADMIN_PASSWORD. "
                "Set them in .env or use environment variables."
            )

        # Get admin bearer token
        token_url = f"{self.store_url}/rest/V1/integration/admin/token"
        if self.debug:
            print(f"  Authenticating as admin: {admin_user}")
        resp = requests.post(
            token_url,
            json={"username": admin_user, "password": admin_pass},
            timeout=30,
        )
        resp.raise_for_status()
        admin_token = resp.json()
        print("  Admin authentication successful")

        # Fetch all customers
        search_url = f"{self.store_url}/rest/V1/customers/search"
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }
        params = {
            "searchCriteria[pageSize]": 100,
            "searchCriteria[currentPage]": 1,
        }
        if self.debug:
            print(f"  Fetching customers from: {search_url}")
        resp = requests.get(search_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        customers = resp.json().get("items", [])
        print(f"  Fetched {len(customers)} real CE customers")

        if self.debug:
            for c in customers:
                print(f"    {c['email']} ({c.get('firstname', '')} {c.get('lastname', '')})")

        # Step 3: Build synthetic B2B structures
        print(f"\n{'='*60}")
        print("STEP 3: CE MODE - BUILD SYNTHETIC B2B STRUCTURES")
        print("="*60)

        graphql_data = build_synthetic_graphql_response(customers)
        rest_roles = build_synthetic_roles_response()

        company_name = graphql_data.get("company", {}).get("name", "Unknown")
        items = graphql_data.get("company", {}).get("structure", {}).get("items", [])
        user_count = sum(1 for i in items if i["entity"]["__typename"] == "Customer")
        team_count = sum(1 for i in items if i["entity"]["__typename"] == "CompanyTeam")
        print(f"  Company: {company_name}")
        print(f"  Users: {user_count} ({len(customers)} real + {user_count - len(customers)} synthetic)")
        print(f"  Teams: {team_count}")
        print(f"  Roles: {len(rest_roles)} (with 34 permissions each)")

        return graphql_data, rest_roles

    def print_summary(self, results: Dict):
        """Print a human-readable execution summary.

        Args:
            results: The dict returned by run().
        """
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print("="*60)
        print(f"Status: {'SUCCESS' if results.get('success') else 'FAILED'}")

        summary = results.get("summary", {})
        if summary:
            print(f"Company: {summary.get('company', 'N/A')}")
            print(f"Users: {summary.get('users', 0)}")
            print(f"Teams: {summary.get('teams', 0)}")
            print(f"Roles: {summary.get('roles', 0)}")

        if results.get("error"):
            print(f"Error: {results['error']}")
