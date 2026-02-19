"""
Adobe IMS OAuth Client - Token acquisition for Commerce Cloud.
Uses OAuth 2.0 client_credentials grant.
"""

import time
import requests
from typing import Optional


class ImsAuthClient:
    """Acquires Adobe IMS access tokens for Commerce Cloud API calls."""

    IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: str = "openid,AdobeID",
        debug: bool = False,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.debug = debug
        self._token = None
        self._expires_at = 0

    def get_token(self) -> str:
        """Acquire or return cached IMS access token."""
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        if self.debug:
            print(f"  Acquiring Adobe IMS token (scopes: {self.scopes})")

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scopes,
        }

        response = requests.post(self.IMS_TOKEN_URL, data=payload)
        response.raise_for_status()

        data = response.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)

        if self.debug:
            print(f"  IMS token acquired, expires in {data.get('expires_in', 3600)}s")

        return self._token

    @property
    def token(self) -> Optional[str]:
        return self._token
