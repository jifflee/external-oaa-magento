"""Tests for magento_oaa_shared.push_helper."""

from unittest.mock import MagicMock, patch
import pytest

from magento_oaa_shared.push_helper import execute_veza_push
from magento_oaa_shared.preflight_checker import PreflightResult


def _make_mocks(preflight_result=None):
    veza_client = MagicMock()
    veza_client.generate_provider_name.return_value = "full_provider_name"
    veza_client.push_application.return_value = {"status": "ok"}
    veza_client.push_application_by_ids.return_value = {"status": "ok"}
    veza_client.get_provider.return_value = {"id": "prov-1"}
    veza_client.get_data_sources.return_value = [{"id": "ds-1", "name": "ds"}]

    preflight_checker = MagicMock()
    if preflight_result is None:
        preflight_result = PreflightResult()
    preflight_checker.check.return_value = preflight_result

    registry = MagicMock()
    app = MagicMock()
    company = {"name": "Acme Corp", "id": "1"}

    return veza_client, preflight_checker, registry, app, company


def test_execute_fresh_push():
    veza_client, preflight_checker, registry, app, company = _make_mocks()
    result = execute_veza_push(
        veza_client=veza_client,
        preflight_checker=preflight_checker,
        registry=registry,
        app=app,
        provider_name="test_provider",
        provider_prefix="prefix",
        company=company,
        veza_url="https://veza.test",
    )
    assert result["provider_name"] == "full_provider_name"
    assert result["veza_response"] == {"status": "ok"}
    veza_client.ensure_provider.assert_called_once()
    veza_client.push_application.assert_called_once()


def test_execute_override_push():
    preflight = PreflightResult(
        override_provider=True,
        existing_provider_id="prov-1",
        existing_data_source_id="ds-1",
    )
    veza_client, preflight_checker, registry, app, company = _make_mocks(preflight)
    result = execute_veza_push(
        veza_client=veza_client,
        preflight_checker=preflight_checker,
        registry=registry,
        app=app,
        provider_name="test_provider",
        provider_prefix="",
        company=company,
        veza_url="https://veza.test",
    )
    veza_client.push_application_by_ids.assert_called_once_with(app, "prov-1", "ds-1")


def test_execute_override_without_data_source():
    preflight = PreflightResult(
        override_provider=True,
        existing_provider_id="prov-1",
        existing_data_source_id=None,
    )
    veza_client, preflight_checker, registry, app, company = _make_mocks(preflight)
    execute_veza_push(
        veza_client=veza_client,
        preflight_checker=preflight_checker,
        registry=registry,
        app=app,
        provider_name="test_provider",
        provider_prefix="",
        company=company,
        veza_url="https://veza.test",
    )
    veza_client.ensure_provider.assert_called_once()
    veza_client.push_application.assert_called_once()


def test_save_provider_ids_called():
    veza_client, preflight_checker, registry, app, company = _make_mocks()
    execute_veza_push(
        veza_client=veza_client,
        preflight_checker=preflight_checker,
        registry=registry,
        app=app,
        provider_name="test_provider",
        provider_prefix="",
        company=company,
        veza_url="https://veza.test",
    )
    registry.save.assert_called_once()
