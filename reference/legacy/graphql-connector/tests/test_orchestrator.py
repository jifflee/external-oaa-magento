"""
Tests for core.orchestrator.GraphQLOrchestrator.validate_config().

These tests are self-contained and do not require network access, an installed
oaaclient package, or a running Magento instance.  They exercise only the
configuration-validation logic by controlling environment variables and
patching the I/O side-effects of the orchestrator's __init__.

Environment variables are injected via unittest.mock.patch.dict so that each
test is fully isolated.
"""

import os
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Base env with all required keys present so individual tests can omit one at
# a time to trigger the specific error they are testing.
_BASE_ENV = {
    "MAGENTO_STORE_URL": "https://store.example.com",
    "MAGENTO_USERNAME": "admin",
    "MAGENTO_PASSWORD": "secret",
    "VEZA_URL": "https://veza.example.com",
    "VEZA_API_KEY": "api-key-abc",
    "DRY_RUN": "true",        # default to dry-run so Veza vars are not required
    "SAVE_JSON": "false",
    "DEBUG": "false",
    "OUTPUT_DIR": "/tmp/magento_test_output",
    "OUTPUT_RETENTION_DAYS": "30",
    "USE_REST_ROLE_SUPPLEMENT": "false",
    "PROVIDER_NAME": "Magento_B2B",
    "PROVIDER_PREFIX": "",
}


def _make_orchestrator(env_overrides=None):
    """
    Build a GraphQLOrchestrator instance in a controlled environment.

    Patches:
    - os.environ via the supplied dict (merged on top of _BASE_ENV)
    - Path.exists() so no .env file is needed on disk
    - OutputManager, VezaClient, ProviderRegistry, PreflightChecker constructors
      to avoid real I/O in __init__
    """
    env = dict(_BASE_ENV)
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=True), \
         patch("core.orchestrator.Path.exists", return_value=False), \
         patch("core.orchestrator.OutputManager", return_value=MagicMock()), \
         patch("core.orchestrator.VezaClient", return_value=MagicMock()), \
         patch("core.orchestrator.ProviderRegistry", return_value=MagicMock()), \
         patch("core.orchestrator.PreflightChecker", return_value=MagicMock()):
        from core.orchestrator import GraphQLOrchestrator
        orchestrator = GraphQLOrchestrator(env_file="./.env")
    return orchestrator


# ---------------------------------------------------------------------------
# validate_config tests
# ---------------------------------------------------------------------------


def test_validate_config_missing_store_url():
    """validate_config returns False when MAGENTO_STORE_URL is absent."""
    orch = _make_orchestrator(env_overrides={"MAGENTO_STORE_URL": ""})
    result = orch.validate_config()
    assert result is False


def test_validate_config_missing_credentials():
    """validate_config returns False when MAGENTO_USERNAME or MAGENTO_PASSWORD is absent."""
    # Missing username
    orch_no_user = _make_orchestrator(env_overrides={"MAGENTO_USERNAME": ""})
    assert orch_no_user.validate_config() is False

    # Missing password
    orch_no_pass = _make_orchestrator(env_overrides={"MAGENTO_PASSWORD": ""})
    assert orch_no_pass.validate_config() is False


def test_validate_config_veza_required_for_push():
    """validate_config returns False when DRY_RUN=false and VEZA_URL/VEZA_API_KEY absent."""
    # Live push mode, no Veza URL
    orch_no_veza_url = _make_orchestrator(
        env_overrides={"DRY_RUN": "false", "VEZA_URL": ""}
    )
    assert orch_no_veza_url.validate_config() is False

    # Live push mode, no Veza API key
    orch_no_key = _make_orchestrator(
        env_overrides={"DRY_RUN": "false", "VEZA_API_KEY": ""}
    )
    assert orch_no_key.validate_config() is False


def test_validate_config_veza_not_required_in_dry_run():
    """When DRY_RUN=true, missing Veza credentials do NOT cause validation failure."""
    orch = _make_orchestrator(
        env_overrides={
            "DRY_RUN": "true",
            "VEZA_URL": "",
            "VEZA_API_KEY": "",
        }
    )
    assert orch.validate_config() is True


def test_validate_config_valid():
    """validate_config returns True when all required fields are present."""
    orch = _make_orchestrator()
    assert orch.validate_config() is True


def test_validate_config_valid_live_push():
    """validate_config returns True with DRY_RUN=false and all Veza credentials present."""
    orch = _make_orchestrator(
        env_overrides={
            "DRY_RUN": "false",
            "VEZA_URL": "https://veza.example.com",
            "VEZA_API_KEY": "real-api-key",
        }
    )
    assert orch.validate_config() is True
