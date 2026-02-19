"""
================================================================================
OUTPUT MANAGER - Output Folder and Retention Management (Core Module)
================================================================================

PURPOSE:
    Manages timestamped output folders and retention cleanup.
    This is a CORE module - do not modify.

FEATURES:
    - Creates timestamped output folders (YYYYMMDD_HHMM_<name>)
    - Automatic cleanup of folders older than retention period
    - Safe deletion (only deletes matching folder patterns)

================================================================================
"""

import os
import re
import shutil
from datetime import datetime, timedelta


class OutputManager:
    """
    Manages output directories with timestamping and retention policies.
    """

    def __init__(self, base_dir: str, provider_name: str, retention_days: int = 30):
        """
        Initialize output manager.

        ARGS:
            base_dir: Base output directory (e.g., "./output")
            provider_name: Name used in folder naming
            retention_days: Days to keep old folders (0 = no cleanup)
        """
        self.base_dir = base_dir
        self.provider_name = provider_name
        self.retention_days = retention_days
        self.current_dir = None
        self._run_timestamp = datetime.now()

    def create_timestamped_dir(self) -> str:
        """
        Create a timestamped output directory for this run.

        FORMAT: YYYYMMDD_HHMM_<provider_name>

        RETURNS:
            Path to the created directory
        """
        # Format timestamp
        timestamp = self._run_timestamp.strftime("%Y%m%d_%H%M")

        # Sanitize provider name for filesystem
        safe_provider = "".join(
            c if c.isalnum() or c in '-_' else '_'
            for c in self.provider_name
        )

        # Create folder name and path
        folder_name = f"{timestamp}_{safe_provider}"
        self.current_dir = os.path.join(self.base_dir, folder_name)

        # Create directory
        os.makedirs(self.current_dir, exist_ok=True)

        return self.current_dir

    def cleanup_old_folders(self, debug: bool = False) -> int:
        """
        Remove output folders older than retention_days.

        ARGS:
            debug: If True, print deleted folder names

        RETURNS:
            Number of folders deleted

        NOTE:
            Only deletes folders matching pattern YYYYMMDD_HHMM_*
        """
        if self.retention_days <= 0:
            return 0

        if not os.path.exists(self.base_dir):
            return 0

        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        # Pattern: YYYYMMDD_HHMM_*
        pattern = re.compile(r'^(\d{8})_(\d{4})_.*$')

        for folder_name in os.listdir(self.base_dir):
            folder_path = os.path.join(self.base_dir, folder_name)

            # Skip non-directories
            if not os.path.isdir(folder_path):
                continue

            # Skip non-matching patterns
            match = pattern.match(folder_name)
            if not match:
                continue

            try:
                # Parse date from folder name
                date_str = match.group(1)
                time_str = match.group(2)
                folder_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")

                # Delete if older than retention
                if folder_datetime < cutoff_date:
                    shutil.rmtree(folder_path)
                    deleted_count += 1
                    if debug:
                        print(f"  Deleted old output folder: {folder_name}")

            except (ValueError, OSError) as e:
                if debug:
                    print(f"  Warning: Could not process folder {folder_name}: {e}")
                continue

        return deleted_count

    def get_output_path(self, filename: str) -> str:
        """
        Get full path for a file in current output directory.

        ARGS:
            filename: Name of the file

        RETURNS:
            Full path to the file

        RAISES:
            RuntimeError: If create_timestamped_dir() hasn't been called
        """
        if not self.current_dir:
            raise RuntimeError("Output directory not created. Call create_timestamped_dir() first.")
        return os.path.join(self.current_dir, filename)
