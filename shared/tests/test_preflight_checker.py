"""Tests for magento_oaa_shared.preflight_checker."""

from unittest.mock import MagicMock
import pytest

from magento_oaa_shared.preflight_checker import PreflightChecker, PreflightResult


def test_preflight_result_defaults():
    result = PreflightResult()
    assert result.proceed is True
    assert result.has_conflicts is False
    assert result.override_provider is False
    assert result.existing_provider_id is None
    assert result.existing_data_source_id is None
    assert result.conflicts == []


def test_dry_run_skips_checks():
    veza = MagicMock()
    registry = MagicMock()
    checker = PreflightChecker(veza, registry, debug=True)
    result = checker.check("test_provider", dry_run=True)
    assert result.proceed is True
    veza.get_provider.assert_not_called()


def test_no_credentials_skips_checks():
    veza = MagicMock()
    veza.veza_url = ""
    veza.veza_api_key = ""
    registry = MagicMock()
    checker = PreflightChecker(veza, registry, debug=True)
    result = checker.check("test_provider", dry_run=False)
    assert result.proceed is True


def test_no_existing_provider():
    veza = MagicMock()
    veza.veza_url = "https://veza.test"
    veza.veza_api_key = "key"
    veza.get_provider.return_value = None
    veza.generate_provider_name.return_value = "full_name"
    registry = MagicMock()
    checker = PreflightChecker(veza, registry)
    result = checker.check("test_provider", dry_run=False)
    assert result.proceed is True
    assert result.has_conflicts is False
    assert result.override_provider is False


def test_own_provider_detected():
    veza = MagicMock()
    veza.veza_url = "https://veza.test"
    veza.veza_api_key = "key"
    veza.get_provider.return_value = {"id": "prov-123"}
    veza.generate_provider_name.return_value = "full_name"
    veza.get_data_sources.return_value = [{"id": "ds-1", "name": "ds"}]
    registry = MagicMock()
    registry.is_our_provider.return_value = True
    checker = PreflightChecker(veza, registry)
    result = checker.check("test_provider", dry_run=False)
    assert result.override_provider is True
    assert result.existing_provider_id == "prov-123"
    assert result.existing_data_source_id == "ds-1"


def test_external_provider_conflict():
    veza = MagicMock()
    veza.veza_url = "https://veza.test"
    veza.veza_api_key = "key"
    veza.get_provider.return_value = {"id": "prov-999"}
    veza.generate_provider_name.return_value = "full_name"
    registry = MagicMock()
    registry.is_our_provider.return_value = False
    checker = PreflightChecker(veza, registry)
    result = checker.check("test_provider", dry_run=False)
    assert result.has_conflicts is True
    assert len(result.conflicts) == 1
