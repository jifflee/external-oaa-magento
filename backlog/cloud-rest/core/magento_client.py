"""
Commerce Cloud REST API Client - Handles all REST endpoint interactions.

Uses Adobe IMS OAuth (client_credentials) instead of customer token auth.

Endpoint reference (from official Magento B2B documentation):
- GET /rest/V1/customers/me
- GET /rest/V1/company/{id}
- GET /rest/V1/company/role?searchCriteria[...]
- GET /rest/V1/hierarchy/{companyId}
- GET /rest/V1/team/{id}
"""

import requests
from typing import Dict, Any, Optional, List

from .ims_auth import ImsAuthClient


class CloudRESTClient:
    """Client for Adobe Commerce Cloud B2B REST API using IMS OAuth."""

    def __init__(
        self,
        store_url: str,
        auth_client: ImsAuthClient,
        debug: bool = False,
    ):
        self.store_url = store_url.rstrip("/")
        self._auth = auth_client
        self.debug = debug
        self._token = None
        self._session = requests.Session()

    def authenticate(self) -> str:
        """Acquire IMS token and set Bearer header on session.

        Delegates token acquisition to ImsAuthClient, then injects
        the resulting Bearer token into all subsequent session requests.
        """
        self._token = self._auth.get_token()
        self._session.headers.update({"Authorization": f"Bearer {self._token}"})

        if self.debug:
            print(f"  Commerce Cloud session authenticated via IMS OAuth")

        return self._token

    def get_current_user(self) -> Dict[str, Any]:
        """Get current user profile.

        GET /rest/V1/customers/me
        Returns customer object with extension_attributes.company_attributes
        """
        self._ensure_auth()
        url = f"{self.store_url}/rest/V1/customers/me"

        if self.debug:
            print(f"  Fetching current user profile")

        response = self._session.get(url)
        response.raise_for_status()
        return response.json()

    def get_company(self, company_id: int) -> Dict[str, Any]:
        """Get company details.

        GET /rest/V1/company/{id}
        Returns company object with company_name, legal_name, etc.
        """
        self._ensure_auth()
        url = f"{self.store_url}/rest/V1/company/{company_id}"

        if self.debug:
            print(f"  Fetching company {company_id}")

        response = self._session.get(url)
        response.raise_for_status()
        return response.json()

    def get_company_roles(self, company_id: int) -> List[Dict]:
        """Get all roles for a company with permissions.

        GET /rest/V1/company/role?searchCriteria[filter_groups][0][filters][0][field]=company_id
            &searchCriteria[filter_groups][0][filters][0][value]={company_id}
            &searchCriteria[filter_groups][0][filters][0][condition_type]=eq

        Returns list of roles, each with:
        {
            "id": 6,
            "role_name": "Junior Buyer",
            "permissions": [
                {"resource_id": "Magento_Sales::place_order", "permission": "allow"},
                {"resource_id": "Magento_Company::roles_edit", "permission": "deny"}
            ],
            "company_id": 2
        }
        """
        self._ensure_auth()
        url = f"{self.store_url}/rest/V1/company/role"
        params = {
            "searchCriteria[filter_groups][0][filters][0][field]": "company_id",
            "searchCriteria[filter_groups][0][filters][0][value]": str(company_id),
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
        }

        if self.debug:
            print(f"  Fetching roles for company {company_id}")

        response = self._session.get(url, params=params)
        response.raise_for_status()

        result = response.json()
        roles = result.get("items", [])

        if self.debug:
            print(f"  Found {len(roles)} roles")

        return roles

    def get_hierarchy(self, company_id: int) -> Dict[str, Any]:
        """Get company hierarchy.

        GET /rest/V1/hierarchy/{companyId}
        Returns hierarchy tree with structure_id, entity_id, entity_type, structure_parent_id
        """
        self._ensure_auth()
        url = f"{self.store_url}/rest/V1/hierarchy/{company_id}"

        if self.debug:
            print(f"  Fetching hierarchy for company {company_id}")

        response = self._session.get(url)
        response.raise_for_status()
        return response.json()

    def get_team(self, team_id: int) -> Dict[str, Any]:
        """Get team details.

        GET /rest/V1/team/{id}
        Returns: {"id": 1, "name": "Western Region", "description": "..."}
        """
        self._ensure_auth()
        url = f"{self.store_url}/rest/V1/team/{team_id}"

        if self.debug:
            print(f"  Fetching team {team_id}")

        response = self._session.get(url)
        response.raise_for_status()
        return response.json()

    def _ensure_auth(self):
        """Ensure we have a valid token, refreshing via IMS if needed."""
        if not self._token:
            self.authenticate()

    @property
    def token(self) -> Optional[str]:
        return self._token
