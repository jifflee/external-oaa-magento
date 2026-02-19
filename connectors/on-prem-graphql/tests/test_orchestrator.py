"""Tests for core.orchestrator.GraphQLOrchestrator.validate_config()."""

import os
from unittest.mock import patch, MagicMock

import pytest


_BASE_ENV = {
    "MAGENTO_STORE_URL": "https://store.example.com",
    "MAGENTO_USERNAME": "admin",
    "MAGENTO_PASSWORD": "secret",
    "VEZA_URL": "https://veza.example.com",
    "VEZA_API_KEY": "api-key-abc",
    "DRY_RUN": "true",
    "SAVE_JSON": "false",
    "DEBUG": "false",
    "OUTPUT_DIR": "/tmp/magento_test_output",
    "OUTPUT_RETENTION_DAYS": "30",
    "USE_REST_ROLE_SUPPLEMENT": "false",
    "PROVIDER_NAME": "Magento_OnPrem_GraphQL",
    "PROVIDER_PREFIX": "",
}


def _make_orchestrator(env_overrides=None):
    env = dict(_BASE_ENV)
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=True), \
         patch("core.orchestrator.OutputManager", return_value=MagicMock()), \
         patch("core.orchestrator.VezaClient", return_value=MagicMock()), \
         patch("core.orchestrator.ProviderRegistry", return_value=MagicMock()), \
         patch("core.orchestrator.PreflightChecker", return_value=MagicMock()):
        from core.orchestrator import GraphQLOrchestrator
        orchestrator = GraphQLOrchestrator(env_file="/nonexistent/.env")
    return orchestrator


def test_validate_config_missing_store_url():
    orch = _make_orchestrator(env_overrides={"MAGENTO_STORE_URL": ""})
    assert orch.validate_config() is False


def test_validate_config_missing_credentials():
    orch_no_user = _make_orchestrator(env_overrides={"MAGENTO_USERNAME": ""})
    assert orch_no_user.validate_config() is False
    orch_no_pass = _make_orchestrator(env_overrides={"MAGENTO_PASSWORD": ""})
    assert orch_no_pass.validate_config() is False


def test_validate_config_veza_required_for_push():
    orch_no_veza_url = _make_orchestrator(
        env_overrides={"DRY_RUN": "false", "VEZA_URL": ""}
    )
    assert orch_no_veza_url.validate_config() is False
    orch_no_key = _make_orchestrator(
        env_overrides={"DRY_RUN": "false", "VEZA_API_KEY": ""}
    )
    assert orch_no_key.validate_config() is False


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
            "VEZA_API_KEY": "real-api-key",
        }
    )
    assert orch.validate_config() is True
