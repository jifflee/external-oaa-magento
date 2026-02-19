"""
Tests for core.orchestrator.RESTOrchestrator.validate_config().

These tests exercise configuration validation only; no live HTTP calls are made.
Environment variables are injected via unittest.mock.patch.dict.
"""

import os
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helper: build a fully-patched orchestrator without needing real credentials
# or a real .env file.
# ---------------------------------------------------------------------------


def _make_orchestrator(env_overrides: dict):
    """
    Instantiate RESTOrchestrator with a controlled set of environment variables.

    All heavy dependencies (VezaClient, ProviderRegistry, OutputManager,
    PreflightChecker) are patched to avoid side-effects at construction time.
    """
    # Patch the sub-modules that are instantiated inside __init__ so they
    # do not make real network calls or touch the filesystem.
    patches = [
        patch("core.orchestrator.OutputManager"),
        patch("core.orchestrator.VezaClient"),
        patch("core.orchestrator.ProviderRegistry"),
        patch("core.orchestrator.PreflightChecker"),
        patch("core.orchestrator.load_dotenv"),  # prevent .env file loading
    ]

    started = [p.start() for p in patches]

    # Provide a minimal env that every test can further override
    base_env = {
        "MAGENTO_STORE_URL": "",
        "MAGENTO_USERNAME": "",
        "MAGENTO_PASSWORD": "",
        "VEZA_URL": "",
        "VEZA_API_KEY": "",
        "DRY_RUN": "true",
        "SAVE_JSON": "false",
        "DEBUG": "false",
        "USER_ROLE_STRATEGY": "default_role",
        "USER_ROLE_MAPPING_PATH": "",
        "PROVIDER_NAME": "Magento_B2B",
        "PROVIDER_PREFIX": "",
        "OUTPUT_DIR": "/tmp/output_test",
        "OUTPUT_RETENTION_DAYS": "30",
    }
    base_env.update(env_overrides)

    with patch.dict(os.environ, base_env, clear=False):
        # Remove any existing values that might bleed in from the real environment
        keys_to_clear = [k for k in base_env if k not in env_overrides]
        # Actually set every key explicitly; patch.dict already handles this.
        from core.orchestrator import RESTOrchestrator
        orchestrator = RESTOrchestrator(env_file="/nonexistent/.env")

    for p in patches:
        p.stop()

    return orchestrator


# ---------------------------------------------------------------------------
# Tests: validate_config
# ---------------------------------------------------------------------------


class TestValidateConfigMissingStoreUrl:
    def test_returns_false_when_store_url_missing(self):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "",
                    "MAGENTO_USERNAME": "user",
                    "MAGENTO_PASSWORD": "pass",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                    "DRY_RUN": "true",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = ""
            orch.username = "user"
            orch.password = "pass"
            orch.dry_run = True
            assert orch.validate_config() is False

    def test_error_message_mentions_store_url(self, capsys):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "",
                    "MAGENTO_USERNAME": "user",
                    "MAGENTO_PASSWORD": "pass",
                    "DRY_RUN": "true",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = ""
            orch.username = "user"
            orch.password = "pass"
            orch.dry_run = True
            orch.validate_config()
            out = capsys.readouterr().out
            assert "MAGENTO_STORE_URL" in out


class TestValidateConfigMissingCredentials:
    def _make_orch_no_credentials(self, missing: str):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "https://store.test",
                    "MAGENTO_USERNAME": "user",
                    "MAGENTO_PASSWORD": "pass",
                    "DRY_RUN": "true",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = "https://store.test"
            orch.username = "user"
            orch.password = "pass"
            orch.dry_run = True
            if missing == "username":
                orch.username = ""
            elif missing == "password":
                orch.password = ""
            return orch

    def test_missing_username_returns_false(self):
        orch = self._make_orch_no_credentials("username")
        assert orch.validate_config() is False

    def test_missing_password_returns_false(self):
        orch = self._make_orch_no_credentials("password")
        assert orch.validate_config() is False

    def test_missing_username_message(self, capsys):
        orch = self._make_orch_no_credentials("username")
        orch.validate_config()
        out = capsys.readouterr().out
        assert "MAGENTO_USERNAME" in out

    def test_missing_password_message(self, capsys):
        orch = self._make_orch_no_credentials("password")
        orch.validate_config()
        out = capsys.readouterr().out
        assert "MAGENTO_PASSWORD" in out


class TestValidateConfigVezaRequiredForPush:
    def _base_orch(self):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "https://store.test",
                    "MAGENTO_USERNAME": "user",
                    "MAGENTO_PASSWORD": "pass",
                    "DRY_RUN": "false",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = "https://store.test"
            orch.username = "user"
            orch.password = "pass"
            orch.dry_run = False
            orch.veza_url = ""
            orch.veza_api_key = ""
            return orch

    def test_missing_veza_url_returns_false_when_not_dry_run(self):
        orch = self._base_orch()
        assert orch.validate_config() is False

    def test_missing_veza_api_key_returns_false(self):
        orch = self._base_orch()
        orch.veza_url = "https://veza.test"
        orch.veza_api_key = ""
        assert orch.validate_config() is False

    def test_veza_url_error_message(self, capsys):
        orch = self._base_orch()
        orch.validate_config()
        out = capsys.readouterr().out
        assert "VEZA_URL" in out

    def test_veza_api_key_error_message(self, capsys):
        orch = self._base_orch()
        orch.veza_url = "https://veza.test"
        orch.validate_config()
        out = capsys.readouterr().out
        assert "VEZA_API_KEY" in out

    def test_veza_not_required_when_dry_run(self):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "https://store.test",
                    "MAGENTO_USERNAME": "user",
                    "MAGENTO_PASSWORD": "pass",
                    "DRY_RUN": "true",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = "https://store.test"
            orch.username = "user"
            orch.password = "pass"
            orch.dry_run = True
            orch.veza_url = ""
            orch.veza_api_key = ""
            # With dry_run=True, Veza credentials are NOT required
            assert orch.validate_config() is True


class TestValidateConfigValid:
    def _valid_dry_run_orch(self):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "https://store.test",
                    "MAGENTO_USERNAME": "admin",
                    "MAGENTO_PASSWORD": "secret",
                    "DRY_RUN": "true",
                    "SAVE_JSON": "true",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                    "VEZA_URL": "",
                    "VEZA_API_KEY": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = "https://store.test"
            orch.username = "admin"
            orch.password = "secret"
            orch.dry_run = True
            return orch

    def test_valid_dry_run_config_returns_true(self):
        orch = self._valid_dry_run_orch()
        assert orch.validate_config() is True

    def test_valid_live_push_config_returns_true(self):
        with (
            patch("core.orchestrator.OutputManager"),
            patch("core.orchestrator.VezaClient"),
            patch("core.orchestrator.ProviderRegistry"),
            patch("core.orchestrator.PreflightChecker"),
            patch("core.orchestrator.load_dotenv"),
            patch.dict(
                os.environ,
                {
                    "MAGENTO_STORE_URL": "https://store.test",
                    "MAGENTO_USERNAME": "admin",
                    "MAGENTO_PASSWORD": "secret",
                    "VEZA_URL": "https://veza.test",
                    "VEZA_API_KEY": "veza-key-123",
                    "DRY_RUN": "false",
                    "SAVE_JSON": "false",
                    "DEBUG": "false",
                    "OUTPUT_DIR": "/tmp",
                    "OUTPUT_RETENTION_DAYS": "30",
                    "PROVIDER_NAME": "Magento_B2B",
                    "PROVIDER_PREFIX": "",
                },
                clear=False,
            ),
        ):
            from core.orchestrator import RESTOrchestrator
            orch = RESTOrchestrator(env_file="/nonexistent/.env")
            orch.store_url = "https://store.test"
            orch.username = "admin"
            orch.password = "secret"
            orch.dry_run = False
            orch.veza_url = "https://veza.test"
            orch.veza_api_key = "veza-key-123"
            assert orch.validate_config() is True

    def test_valid_config_produces_no_errors(self, capsys):
        orch = self._valid_dry_run_orch()
        orch.validate_config()
        out = capsys.readouterr().out
        assert "Configuration Errors" not in out
