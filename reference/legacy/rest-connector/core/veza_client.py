"""
Veza API Client - Manages all Veza API interactions.
Adapted from odie-oaa reference implementation.
"""

import json
import sys
from typing import Dict, List, Optional


class VezaClient:
    """Manages all Veza API interactions."""

    def __init__(self, veza_url: str, veza_api_key: str, debug: bool = False):
        self.veza_url = veza_url
        self.veza_api_key = veza_api_key
        self.debug = debug
        self._client = None

    def _get_client(self):
        if self._client is None:
            from oaaclient.client import OAAClient
            self._client = OAAClient(url=self.veza_url, api_key=self.veza_api_key)
        return self._client

    def get_provider(self, provider_name: str) -> Optional[Dict]:
        return self._get_client().get_provider(provider_name)

    def get_provider_list(self) -> list:
        return self._get_client().get_provider_list()

    def create_provider(self, provider_name: str) -> Dict:
        return self._get_client().create_provider(provider_name, "application")

    def delete_provider(self, provider_id: str) -> bool:
        self._get_client().delete_provider(provider_id)
        return True

    def push_application(self, app, provider_name: str, data_source_name: str) -> Dict:
        return self._get_client().push_application(
            provider_name=provider_name,
            data_source_name=data_source_name,
            application_object=app,
        )

    def get_data_sources(self, provider_id: str) -> List[Dict]:
        return self._get_client().get_data_sources(provider_id)

    def push_application_by_ids(self, app, provider_id: str, data_source_id: str) -> Dict:
        client = self._get_client()
        metadata = app.get_payload()
        json_data_str = json.dumps(metadata, separators=(",", ":"))
        json_data_size = sys.getsizeof(json_data_str)
        if client.enable_multipart and json_data_size > client.MULTIPART_THRESHOLD_SIZE:
            return client.datasource_push_parts(
                provider_id=provider_id, data_source_id=data_source_id, json_data=json_data_str,
            )
        return client.datasource_push(
            provider_id=provider_id, data_source_id=data_source_id, json_data=json_data_str,
        )

    def ensure_provider(self, provider_name: str) -> Dict:
        provider = self.get_provider(provider_name)
        if provider:
            if self.debug:
                print(f"  Using existing provider: {provider_name}")
        else:
            if self.debug:
                print(f"  Creating provider: {provider_name}")
            provider = self.create_provider(provider_name)
        return provider

    @staticmethod
    def generate_provider_name(app_name: str, prefix: str = "") -> str:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in app_name)
        return f"{prefix}_{safe_name}" if prefix else safe_name
