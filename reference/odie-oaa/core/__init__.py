"""
Core module - Do not modify. Contains Veza OAA processing logic.
"""

from .orchestrator import MultiSourceOrchestrator
from .csv_loader import load_csv, group_by_application, get_unique_permissions
from .application_builder import build_application
from .output_manager import OutputManager
from .deployment_validator import DeploymentValidator
from .veza_client import VezaClient
from .provider_registry import ProviderRegistry
from .preflight_checker import PreflightChecker, PreflightResult

__all__ = [
    'MultiSourceOrchestrator',
    'load_csv',
    'group_by_application',
    'get_unique_permissions',
    'build_application',
    'OutputManager',
    'DeploymentValidator',
    'VezaClient',
    'ProviderRegistry',
    'PreflightChecker',
    'PreflightResult',
]
