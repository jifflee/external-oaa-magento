"""Shared utilities for the Magento B2B Veza OAA connector."""

from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .output_manager import OutputManager
from .preflight_checker import PreflightChecker, PreflightResult
from .permissions import (
    MAGENTO_ACL_PERMISSIONS,
    PERMISSION_CATEGORIES,
    define_oaa_permissions,
    get_permission_name,
    get_permission_category,
)
from .application_builder_base import BaseApplicationBuilder
from .push_helper import execute_veza_push
