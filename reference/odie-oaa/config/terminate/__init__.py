"""
Terminate module - Safe provider cleanup with multiple safety checkpoints.

Usage:
    python3 -m config.terminate.terminate --dry-run
    python3 -m config.terminate.terminate --execute
"""

from .terminate import TerminationScript, TerminationError

__all__ = ['TerminationScript', 'TerminationError']
