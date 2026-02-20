"""Tests for core.orchestrator.GraphQLOrchestrator.validate_config()."""

import os
from unittest.mock import patch, MagicMock

import pytest


_BASE_ENV = {
    "MAGENTO_STORE_URL": "https://store.example.com",
    "MAGENTO_USERNAME": "admin",
    "MAGENTO_PASSWORD": "secret",
    "SAVE_JSON": "false",
    "DEBUG": "false",
    "OUTPUT_DIR": "/tmp/magento_test_output",
    "OUTPUT_RETENTION_DAYS": "30",
    "USE_REST_ROLE_SUPPLEMENT": "false",
    "PROVIDER_NAME": "Magento_OnPrem_GraphQL",
}


def _make_orchestrator(env_overrides=None):
    env = dict(_BASE_ENV)
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=True), \
         patch("core.orchestrator.OutputManager", return_value=MagicMock()):
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


def test_validate_config_valid():
    orch = _make_orchestrator()
    assert orch.validate_config() is True
