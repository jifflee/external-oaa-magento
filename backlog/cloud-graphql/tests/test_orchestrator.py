"""Tests for core.orchestrator.CloudGraphQLOrchestrator.validate_config().

Covers required IMS OAuth credentials (ADOBE_IMS_CLIENT_ID,
ADOBE_IMS_CLIENT_SECRET) and the Veza URL/API key requirements that only
apply when DRY_RUN=false.
"""

import os
from unittest.mock import patch, MagicMock
import pytest


_BASE_ENV = {
    "MAGENTO_STORE_URL": "https://cloud.example.com",
    "ADOBE_IMS_CLIENT_ID": "ims-client-id",
    "ADOBE_IMS_CLIENT_SECRET": "ims-secret",
    "ADOBE_IMS_SCOPES": "openid,AdobeID",
    "VEZA_URL": "https://veza.example.com",
    "VEZA_API_KEY": "api-key-abc",
    "DRY_RUN": "true",
    "SAVE_JSON": "false",
    "DEBUG": "false",
    "OUTPUT_DIR": "/tmp/test_output",
    "OUTPUT_RETENTION_DAYS": "30",
    "USE_REST_ROLE_SUPPLEMENT": "false",
    "PROVIDER_NAME": "Commerce_Cloud_GraphQL",
    "PROVIDER_PREFIX": "",
}


def _make_orchestrator(env_overrides=None):
    env = dict(_BASE_ENV)
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=True), \
         patch("magento_oaa_shared.output_manager.OutputManager", return_value=MagicMock()), \
         patch("magento_oaa_shared.veza_client.VezaClient", return_value=MagicMock()), \
         patch("magento_oaa_shared.provider_registry.ProviderRegistry", return_value=MagicMock()), \
         patch("magento_oaa_shared.preflight_checker.PreflightChecker", return_value=MagicMock()):
        from core.orchestrator import CloudGraphQLOrchestrator
        orch = CloudGraphQLOrchestrator(env_file="/nonexistent/.env")
    return orch


def test_validate_config_missing_store_url():
    orch = _make_orchestrator(env_overrides={"MAGENTO_STORE_URL": ""})
    assert orch.validate_config() is False


def test_validate_config_missing_ims_client_id():
    orch = _make_orchestrator(env_overrides={"ADOBE_IMS_CLIENT_ID": ""})
    assert orch.validate_config() is False


def test_validate_config_missing_ims_client_secret():
    orch = _make_orchestrator(env_overrides={"ADOBE_IMS_CLIENT_SECRET": ""})
    assert orch.validate_config() is False


def test_validate_config_veza_required_for_push():
    orch = _make_orchestrator(env_overrides={"DRY_RUN": "false", "VEZA_URL": ""})
    assert orch.validate_config() is False


def test_validate_config_veza_not_required_in_dry_run():
    orch = _make_orchestrator(
        env_overrides={"DRY_RUN": "true", "VEZA_URL": "", "VEZA_API_KEY": ""}
    )
    assert orch.validate_config() is True


def test_validate_config_valid():
    orch = _make_orchestrator()
    assert orch.validate_config() is True


def test_validate_config_valid_live_push():
    orch = _make_orchestrator(
        env_overrides={
            "DRY_RUN": "false",
            "VEZA_URL": "https://veza.example.com",
            "VEZA_API_KEY": "real-key",
        }
    )
    assert orch.validate_config() is True
