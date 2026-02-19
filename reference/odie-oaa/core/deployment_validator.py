"""
================================================================================
DEPLOYMENT VALIDATOR - Post-Deployment Identity Mapping Validation (Core Module)
================================================================================

PURPOSE:
    Validates that identity mapping is configured between the Identity Provider
    (IdP) and the OAA custom applications created by this connector.

    WITHOUT identity mapping, users in OAA applications will NOT link to IdP
    identities and relationships will NOT appear in the Veza graph.

    This is a CORE module - do not modify.

SUPPORTED IDENTITY PROVIDERS:
    - Active Directory (implemented)
    - Okta (planned)
    - OneLogin (planned)
    - Azure AD (planned)

================================================================================
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class DeploymentValidator:
    """
    Validates post-deployment identity mapping configuration.

    Checks that:
    1. Identity providers exist in Veza
    2. Identity mapping is configured (identity_mapping_configuration != null)
    3. OAA custom providers were created successfully
    4. Relationships can be established in the graph
    """

    # Supported IdP types and their API paths
    IDP_TYPES = {
        "activedirectory": {
            "name": "Active Directory",
            "api_path": "api/v1/providers/activedirectory",
            "enabled": True
        },
        "okta": {
            "name": "Okta",
            "api_path": "api/v1/providers/okta",
            "enabled": False  # Future implementation
        },
        "onelogin": {
            "name": "OneLogin",
            "api_path": "api/v1/providers/onelogin",
            "enabled": False  # Future implementation
        }
    }

    def __init__(self, veza_url: str, veza_api_key: str, output_dir: str = "./output"):
        """
        Initialize validator.

        ARGS:
            veza_url: Veza tenant URL
            veza_api_key: Veza API key
            output_dir: Directory for saving validation results
        """
        self.veza_url = veza_url
        self.veza_api_key = veza_api_key
        self.output_dir = output_dir
        self.debug = False

        # Veza client (lazy loaded)
        self._veza_client = None

    def get_veza_client(self):
        """Get or create Veza OAA client."""
        if self._veza_client is None:
            from oaaclient.client import OAAClient
            self._veza_client = OAAClient(
                url=self.veza_url,
                api_key=self.veza_api_key
            )
        return self._veza_client

    def _api_get(self, path: str) -> List[Dict]:
        """
        Make a GET request to the Veza API and return the values list.

        ARGS:
            path: API path (e.g., "api/v1/providers/activedirectory")

        RETURNS:
            List of values from the response
        """
        import requests

        url = f"{self.veza_url}/{path}"
        headers = {
            "Authorization": f"Bearer {self.veza_api_key}",
            "Accept": "application/json"
        }

        if self.debug:
            print(f"  DEBUG: GET {url}")

        response = requests.get(url, headers=headers, timeout=60)

        if self.debug:
            print(f"  DEBUG: Status: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        # Return only the values array
        return data.get("values", [])

    def list_identity_providers(self, idp_type: str = "activedirectory") -> List[Dict]:
        """
        List identity providers and return only the fields we care about.

        API: GET /api/v1/providers/{idp_type}

        ARGS:
            idp_type: Type of IdP (activedirectory, okta, onelogin)

        RETURNS:
            List of dicts with: id, name, state, identity_mapping_configuration
        """
        if idp_type not in self.IDP_TYPES:
            raise ValueError(f"Unknown IdP type: {idp_type}")

        idp_config = self.IDP_TYPES[idp_type]
        if not idp_config["enabled"]:
            raise ValueError(f"IdP type '{idp_type}' is not yet implemented")

        try:
            raw_providers = self._api_get(idp_config["api_path"])

            # Extract only the fields we care about
            providers = []
            for p in raw_providers:
                providers.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "state": p.get("state"),
                    "identity_mapping_configuration": p.get("identity_mapping_configuration")
                })

            if self.debug:
                print(f"  DEBUG: Found {len(providers)} {idp_type} provider(s)")

            return providers

        except Exception as e:
            if self.debug:
                print(f"  DEBUG: Error fetching {idp_type} providers: {e}")
            return []

    def list_oaa_providers(self, prefix_filter: str = None) -> List[Dict]:
        """
        List OAA custom providers and return only the fields we care about.

        ARGS:
            prefix_filter: Optional prefix to filter providers (e.g., "ODIE_")

        RETURNS:
            List of dicts with: id, name, state
        """
        try:
            client = self.get_veza_client()
            raw_providers = client.get_provider_list()

            # Filter by prefix if specified
            if prefix_filter:
                raw_providers = [
                    p for p in raw_providers
                    if p.get("name", "").startswith(prefix_filter)
                ]

            # Extract only the fields we care about
            providers = []
            for p in raw_providers:
                providers.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "state": p.get("state")
                })

            return providers

        except Exception as e:
            if self.debug:
                print(f"  DEBUG: Error fetching custom providers: {e}")
            return []

    def check_identity_mapping(self, idp_type: str = "activedirectory") -> Dict[str, Any]:
        """
        Check if identity mapping is configured for the IdP.

        Only checks ENABLED providers - disabled providers are skipped.

        ARGS:
            idp_type: Type of IdP to check

        RETURNS:
            Dict with:
                - has_mapping: bool - whether any ENABLED IdP has identity mapping configured
                - enabled_providers: list - ENABLED providers with mapping details
                - disabled_providers: list - disabled providers (skipped)
        """
        result = {
            "has_mapping": False,
            "idp_type": idp_type,
            "idp_name": self.IDP_TYPES[idp_type]["name"],
            "enabled_providers": [],
            "disabled_providers": []
        }

        providers = self.list_identity_providers(idp_type)

        for p in providers:
            state = (p.get("state") or "").upper()

            if state != "ENABLED":
                result["disabled_providers"].append(p)
                continue

            # Extract mapping configuration details
            mapping_config = p.get("identity_mapping_configuration")
            has_mapping = mapping_config is not None

            provider_info = {
                "id": p["id"],
                "name": p["name"],
                "has_identity_mapping": has_mapping,
                "mapping_attribute": None
            }

            # Extract the mapping attribute if configured
            if has_mapping and isinstance(mapping_config, dict):
                # Common mapping attributes: email, samAccountName, userPrincipalName, etc.
                provider_info["mapping_attribute"] = mapping_config.get("attribute") or mapping_config.get("source_attribute")
                provider_info["mapping_config"] = mapping_config

            result["enabled_providers"].append(provider_info)

            if has_mapping:
                result["has_mapping"] = True

        return result

    def validate(
        self,
        idp_type: str = "activedirectory",
        provider_prefix: str = None,
        print_output: bool = True
    ) -> Dict[str, Any]:
        """
        Run full post-deployment validation.

        ARGS:
            idp_type: Identity provider type to check
            provider_prefix: Filter OAA providers by prefix
            print_output: Whether to print validation output

        RETURNS:
            Validation results dict with:
                - validation_passed: bool
                - has_identity_mapping: bool
                - idp_providers: list of enabled IdP providers
                - oaa_providers: list of OAA providers
                - mappings: list of IdP -> OAA mapping records
                - issues: list of issues found
                - recommendations: list of actions to take
        """
        results = {
            "validation_time": datetime.now(timezone.utc).isoformat(),
            "veza_url": self.veza_url,
            "idp_type": idp_type,
            "idp_providers": [],
            "oaa_providers": [],
            "mappings": [],
            "validation_passed": False,
            "has_identity_mapping": False,
            "issues": [],
            "recommendations": []
        }

        idp_name = self.IDP_TYPES[idp_type]["name"]

        if print_output:
            print(f"\n{'-'*60}")
            print("POST-DEPLOYMENT VALIDATION - Identity Mapping Check")
            print('-'*60)

        # Step 1: Get Identity Providers
        idp_check = self.check_identity_mapping(idp_type)
        results["idp_providers"] = idp_check["enabled_providers"]
        results["has_identity_mapping"] = idp_check["has_mapping"]

        # Step 2: Get OAA Custom Providers
        filter_prefix = f"{provider_prefix}_" if provider_prefix else None
        oaa_providers = self.list_oaa_providers(filter_prefix)
        results["oaa_providers"] = oaa_providers

        # Step 3: Build mapping records (IdP -> OAA relationships)
        # Each combination of IdP provider and OAA provider is a potential mapping
        for idp in idp_check["enabled_providers"]:
            for oaa in oaa_providers:
                mapping_record = {
                    "source": {
                        "type": idp_name,
                        "name": idp["name"],
                        "id": idp["id"]
                    },
                    "target": {
                        "type": "OAA Custom Application",
                        "name": oaa["name"],
                        "id": oaa["id"]
                    },
                    "has_mapping": idp["has_identity_mapping"],
                    "mapping_attribute": idp.get("mapping_attribute"),
                    "status": "LINKED" if idp["has_identity_mapping"] else "NO RELATIONSHIP"
                }
                results["mappings"].append(mapping_record)

        # Print relationship table
        if print_output:
            print(f"\n  IDENTITY MAPPING RELATIONSHIPS")
            print(f"  {'-'*56}")
            print(f"  {'SOURCE (IdP)':<25} {'MAPPING':<12} {'TARGET (OAA)':<20}")
            print(f"  {'-'*25} {'-'*12} {'-'*20}")

            if not results["mappings"]:
                # No mappings possible - show why
                if not idp_check["enabled_providers"]:
                    print(f"  (No ENABLED {idp_name} providers found)")
                elif not oaa_providers:
                    print(f"  (No OAA custom providers found)")
            else:
                for m in results["mappings"]:
                    source = m["source"]["name"][:23]
                    target = m["target"]["name"][:18]

                    if m["has_mapping"]:
                        attr = m["mapping_attribute"] or "configured"
                        link = f"--[{attr[:8]}]-->"
                    else:
                        link = "    X    "

                    print(f"  {source:<25} {link:<12} {target:<20}")

            # Show disabled providers if any
            if idp_check["disabled_providers"]:
                print(f"\n  (Skipped {len(idp_check['disabled_providers'])} disabled {idp_name} provider(s))")

        # Step 4: Determine validation result
        has_enabled_idp = len(idp_check["enabled_providers"]) > 0
        has_mapping = idp_check["has_mapping"]
        has_oaa = len(oaa_providers) > 0

        if has_mapping and has_oaa:
            results["validation_passed"] = True
        else:
            # Build issues list
            if not has_enabled_idp:
                results["issues"].append(f"No ENABLED {idp_name} providers found")
                results["recommendations"].append(f"Configure and enable an {idp_name} integration in Veza")

            if has_enabled_idp and not has_mapping:
                results["issues"].append(f"{idp_name} provider(s) have identity_mapping_configuration = null")
                results["recommendations"].append("Configure identity mapping in Veza UI")
                results["recommendations"].append(f"Go to: Integrations > {idp_name} > Edit > Identity Mapping")

            if not has_oaa:
                results["issues"].append("No OAA custom providers found")
                results["recommendations"].append("Run: python run.py --push")

        # Print summary
        if print_output:
            print(f"\n  {'='*56}")
            if results["validation_passed"]:
                linked_count = sum(1 for m in results["mappings"] if m["has_mapping"])
                print(f"  RESULT: PASSED - {linked_count} mapping(s) configured")
                print("  Graph relationships between IdP users and OAA apps will work.")
            else:
                print("  RESULT: FAILED - NO IDENTITY MAPPING RELATIONSHIP")
                print("  " + "-"*56)
                print("\n  ISSUES:")
                for issue in results["issues"]:
                    print(f"    - {issue}")

                print("\n  RECOMMENDATIONS:")
                for rec in results["recommendations"]:
                    print(f"    - {rec}")

                if has_enabled_idp and not has_mapping:
                    print("\n  WHY THIS MATTERS:")
                    print("    Without identity_mapping_configuration, OAA application users")
                    print(f"    will NOT link to {idp_name} identities in the Veza graph.")
                    print("    Access reviews and queries will not show user relationships.")

            print(f"  {'='*56}")

        return results

    def save_results(self, results: Dict, output_path: str = None) -> str:
        """
        Save validation results to file.

        ARGS:
            results: Validation results dict
            output_path: Optional specific output path

        RETURNS:
            Path to saved file
        """
        os.makedirs(self.output_dir, exist_ok=True)

        if output_path:
            filepath = output_path
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.output_dir, f"identity_mapping_validation_{timestamp}.json")

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Also save a "latest" file for easy checking
        latest_path = os.path.join(self.output_dir, "identity_mapping_validation_latest.json")
        with open(latest_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Save OAA provider IDs separately for reference
        if results.get("oaa_providers"):
            providers_path = os.path.join(self.output_dir, "oaa_provider_ids.json")
            provider_ids = {
                "generated_at": results["validation_time"],
                "veza_url": self.veza_url,
                "has_identity_mapping": results["has_identity_mapping"],
                "providers": results["oaa_providers"]
            }
            with open(providers_path, 'w') as f:
                json.dump(provider_ids, f, indent=2)

        return filepath

    def load_previous_results(self) -> Optional[Dict]:
        """
        Load the most recent validation results.

        RETURNS:
            Previous results dict or None if not found
        """
        latest_path = os.path.join(self.output_dir, "identity_mapping_validation_latest.json")

        if os.path.exists(latest_path):
            try:
                with open(latest_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def revalidate_if_failed(
        self,
        idp_type: str = "activedirectory",
        provider_prefix: str = None
    ) -> Dict[str, Any]:
        """
        Check previous results and re-validate if identity mapping was missing.

        This is useful for automated re-checking after a user configures
        identity mapping in the Veza UI.

        ARGS:
            idp_type: Identity provider type to check
            provider_prefix: Filter OAA providers by prefix

        RETURNS:
            Validation results dict with additional 'previous_status' field
        """
        previous = self.load_previous_results()

        print(f"\n{'='*60}")
        print("RE-VALIDATION CHECK")
        print('='*60)

        if previous:
            prev_passed = previous.get("validation_passed", False)
            prev_time = previous.get("validation_time", "unknown")
            print(f"  Previous validation: {'PASSED' if prev_passed else 'FAILED'}")
            print(f"  Previous time: {prev_time}")

            if prev_passed:
                print("  Previous validation passed - no re-validation needed")
                return {
                    "revalidation_skipped": True,
                    "reason": "Previous validation passed",
                    "previous_results": previous
                }
            else:
                print("  Previous validation FAILED - running re-validation...")
        else:
            print("  No previous validation results found - running validation...")

        # Run new validation
        results = self.validate(
            idp_type=idp_type,
            provider_prefix=provider_prefix,
            print_output=True
        )

        # Add comparison info
        results["previous_validation"] = previous
        if previous:
            results["status_changed"] = (
                results["validation_passed"] != previous.get("validation_passed", False)
            )
            if results["status_changed"] and results["validation_passed"]:
                print("\n  STATUS CHANGE: Identity mapping is now configured!")

        return results
