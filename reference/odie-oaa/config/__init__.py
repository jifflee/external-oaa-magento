"""
Config module - Customer-editable configuration files.
"""

from .settings import KNOWN_PERMISSIONS, DEFAULT_SETTINGS
from .roles import (
    ROLE_DEFINITIONS,
    PERMISSION_TO_ROLE,
    ROLE_TO_EFFECTIVE,
    define_roles,
    map_permission_to_role,
    get_role_effective_permissions
)
from .permissions import BASE_PERMISSIONS, define_base_permissions

__all__ = [
    'KNOWN_PERMISSIONS',
    'DEFAULT_SETTINGS',
    'ROLE_DEFINITIONS',
    'PERMISSION_TO_ROLE',
    'ROLE_TO_EFFECTIVE',
    'BASE_PERMISSIONS',
    'define_roles',
    'map_permission_to_role',
    'get_role_effective_permissions',
    'define_base_permissions',
]
