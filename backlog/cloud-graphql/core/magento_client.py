"""
Commerce Cloud GraphQL Client - Uses Adobe IMS OAuth for authentication.
"""

import requests
from typing import Dict, Any, Optional, List

from .ims_auth import ImsAuthClient


class CloudGraphQLClient:
    """Client for Commerce Cloud B2B GraphQL + REST API."""

    def __init__(self, store_url: str, auth_client: ImsAuthClient, debug: bool = False):
        self.store_url = store_url.rstrip("/")
        self._auth = auth_client
        self.debug = debug
        self._token = None
        self._session = requests.Session()

    def authenticate(self) -> str:
        """Get access token via Adobe IMS OAuth."""
        if self.debug:
            print(f"  Authenticating via Adobe IMS")

        self._token = self._auth.get_token()
        self._session.headers.update({"Authorization": f"Bearer {self._token}"})

        if self.debug:
            print(f"  IMS authentication successful")

        return self._token

    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Commerce Cloud."""
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
        """Get company roles with permissions via REST (same endpoint as on-prem)."""
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
