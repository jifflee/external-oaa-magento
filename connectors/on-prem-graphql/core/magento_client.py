"""
Magento API Client — Handles authentication and API calls to Adobe Commerce.

This module is responsible for all HTTP communication with the Magento store.
It uses two Magento API surfaces:

  1. REST API — Used for authentication (obtaining a customer JWT token) and
     optionally for fetching per-role ACL permissions.

  2. GraphQL API — Used for the primary data extraction. A single query
     retrieves the full B2B company structure in one call.

Authentication flow:
    POST /rest/V1/integration/customer/token
    Body: {"username": "company-admin@example.com", "password": "..."}
    Response: "eyJhbGciOiJIUzI1..."  (JWT token as a JSON string)

    The token is then attached as a Bearer header to all subsequent requests.

Pipeline context:
    This is used in Step 1 (authentication), Step 2 (GraphQL extraction),
    and Step 3 (REST role supplement) of the orchestrator pipeline.
"""

import requests
from typing import Dict, Any, Optional, List


class MagentoGraphQLClient:
    """Client for Magento B2B GraphQL and REST APIs.

    Manages a requests.Session with automatic Bearer token injection after
    authentication. All API calls go through this single session.

    Attributes:
        store_url: Base URL of the Magento store (trailing slash stripped).
        username: Magento customer email (B2B company admin).
        password: Magento customer password.
        debug: If True, print verbose request/response details.
    """

    def __init__(self, store_url: str, username: str, password: str, debug: bool = False):
        """Initialize the client.

        Args:
            store_url: Base URL (e.g., "https://magento.example.com").
            username: Customer email address.
            password: Customer password.
            debug: Enable verbose output.
        """
        self.store_url = store_url.rstrip("/")
        self.username = username
        self.password = password
        self.debug = debug
        self._token = None
        self._session = requests.Session()

    def authenticate(self) -> str:
        """Obtain a customer JWT token via the REST API.

        Calls POST /rest/V1/integration/customer/token with username/password.
        The returned token is stored internally and attached to the session
        headers for all subsequent requests.

        Returns:
            The JWT token string.

        Raises:
            requests.HTTPError: If authentication fails (e.g., 401 Unauthorized).
        """
        url = f"{self.store_url}/rest/V1/integration/customer/token"
        payload = {"username": self.username, "password": self.password}

        if self.debug:
            print(f"  Authenticating as: {self.username}")

        response = self._session.post(url, json=payload)
        response.raise_for_status()

        # Magento returns the token as a bare JSON string (quoted)
        self._token = response.json()
        self._session.headers.update({"Authorization": f"Bearer {self._token}"})

        if self.debug:
            print(f"  Authentication successful, token: {self._token[:20]}...")

        return self._token

    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the Magento store.

        Calls POST /graphql with the given query string. If the response
        contains a GraphQL "errors" array, raises a RuntimeError with the
        concatenated error messages.

        Args:
            query: The GraphQL query string.
            variables: Optional dict of GraphQL variables.

        Returns:
            The "data" portion of the GraphQL response (a dict).

        Raises:
            RuntimeError: If the GraphQL response contains errors.
            requests.HTTPError: If the HTTP request fails.
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
        """Fetch company roles with explicit ACL permissions via the REST API.

        Calls GET /rest/V1/company/role with a search filter for the given
        company_id. Each returned role includes a "permissions" array with
        entries like: {"resource_id": "Magento_Sales::place_order", "permission": "allow"}

        This supplements the GraphQL data, which only returns role id and name
        per user but not the per-role permission tree.

        Args:
            company_id: The numeric Magento company ID (decoded from GraphQL base64).

        Returns:
            A list of role dicts, each with "id", "role_name", and "permissions" keys.

        Raises:
            requests.HTTPError: If the REST call fails (e.g., 404 on CE without B2B).
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
        """The current JWT token, or None if not yet authenticated."""
        return self._token
