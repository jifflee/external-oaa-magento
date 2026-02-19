"""
Magento API Client - Handles authentication and API calls.

Uses REST for token generation (simpler) and GraphQL for data extraction.
Optionally supplements with REST role endpoint for explicit allow/deny permissions.
"""

import requests
from typing import Dict, Any, Optional, List


class MagentoGraphQLClient:
    """Client for Magento B2B GraphQL + REST API."""

    def __init__(self, store_url: str, username: str, password: str, debug: bool = False):
        self.store_url = store_url.rstrip("/")
        self.username = username
        self.password = password
        self.debug = debug
        self._token = None
        self._session = requests.Session()

    def authenticate(self) -> str:
        """Get customer token via REST API.

        POST /rest/V1/integration/customer/token
        Body: {"username": "email", "password": "password"}
        Returns: token string (JWT)
        """
        url = f"{self.store_url}/rest/V1/integration/customer/token"
        payload = {"username": self.username, "password": self.password}

        if self.debug:
            print(f"  Authenticating as: {self.username}")

        response = self._session.post(url, json=payload)
        response.raise_for_status()

        # Response is a JSON string (token wrapped in quotes)
        self._token = response.json()
        self._session.headers.update({"Authorization": f"Bearer {self._token}"})

        if self.debug:
            print(f"  Authentication successful, token: {self._token[:20]}...")

        return self._token

    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Magento.

        POST /graphql
        Headers: Authorization: Bearer {token}, Content-Type: application/json
        Body: {"query": "...", "variables": {...}}
        """
        if not self._token:
            self.authenticate()

        url = f"{self.store_url}/graphql"
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        if self.debug:
            print(f"  Executing GraphQL query ({len(query)} chars)")

        response = self._session.post(url, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()

        if "errors" in result:
            error_messages = [e.get("message", str(e)) for e in result["errors"]]
            raise RuntimeError(f"GraphQL errors: {'; '.join(error_messages)}")

        return result.get("data", {})

    def get_company_roles_rest(self, company_id: str) -> List[Dict]:
        """Get company roles with explicit permissions via REST.

        GET /rest/V1/company/role?searchCriteria[filter_groups][0][filters][0][field]=company_id
            &searchCriteria[filter_groups][0][filters][0][value]={company_id}
            &searchCriteria[filter_groups][0][filters][0][condition_type]=eq

        Returns list of roles with permissions array containing:
        [{"resource_id": "Magento_Sales::place_order", "permission": "allow"}, ...]
        """
        if not self._token:
            self.authenticate()

        url = f"{self.store_url}/rest/V1/company/role"
        params = {
            "searchCriteria[filter_groups][0][filters][0][field]": "company_id",
            "searchCriteria[filter_groups][0][filters][0][value]": str(company_id),
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
        }

        headers = {"Authorization": f"Bearer {self._token}"}

        if self.debug:
            print(f"  Fetching roles for company_id={company_id} via REST")

        response = self._session.get(url, params=params, headers=headers)
        response.raise_for_status()

        result = response.json()
        roles = result.get("items", [])

        if self.debug:
            print(f"  Found {len(roles)} roles via REST")

        return roles

    @property
    def token(self) -> Optional[str]:
        return self._token
