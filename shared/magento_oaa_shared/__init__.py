"""
magento-oaa-shared — Shared library for the Magento B2B data extractor.

This package provides the common building blocks used by the GraphQL connector:

  permissions.py              34 Magento B2B ACL permission definitions and
                              the function to register them on an OAA app.
  application_builder_base.py Base class for building OAA CustomApplications
                              with standardized property definitions.
  output_manager.py           Timestamped output directory creation and
                              retention-based cleanup of old runs.

Install with: pip install -e . (from the shared/ directory)
"""

from .output_manager import OutputManager
from .permissions import (
    MAGENTO_ACL_PERMISSIONS,
    PERMISSION_CATEGORIES,
    define_oaa_permissions,
)
from .application_builder_base import BaseApplicationBuilder
