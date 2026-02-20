"""
Output Manager — Timestamped output directories and retention cleanup.

Each extraction run creates a folder under the base output directory with the
format: YYYYMMDD_HHMM_{provider_name} (e.g., "20260220_1430_Magento_OnPrem_GraphQL").

Inside each folder, the orchestrator saves:
  - oaa_payload.json:        The extracted OAA data
  - extraction_results.json: Run metadata, entity counts, errors

The retention policy automatically deletes folders older than OUTPUT_RETENTION_DAYS
at the start of each run (before creating a new folder). Set retention_days=0 to
keep all output indefinitely.

Pipeline context:
    The orchestrator creates the timestamped directory in Step 7 (Save Output)
    and uses get_output_path() to resolve filenames within it. Cleanup runs
    at the start of each extraction run (in run.py).
"""

import os
import re
import shutil
from datetime import datetime, timedelta


class OutputManager:
    """Manages output directories with timestamping and retention policies.

    Attributes:
        base_dir: Root output directory (default: ./output).
        provider_name: Used in folder naming (sanitized to alphanumeric + hyphens).
        retention_days: Delete folders older than this many days (0 = keep forever).
        current_dir: Path to the current run's output directory (None until created).
    """

    def __init__(self, base_dir: str, provider_name: str, retention_days: int = 30):
        """Initialize the output manager.

        Args:
            base_dir: Root directory for all output (e.g., "./output").
            provider_name: Label used in folder naming.
            retention_days: How many days to keep old output folders.
        """
        self.base_dir = base_dir
        self.provider_name = provider_name
        self.retention_days = retention_days
        self.current_dir = None
        self._run_timestamp = datetime.now()

    def create_timestamped_dir(self) -> str:
        """Create a timestamped output directory for the current run.

        Format: {base_dir}/YYYYMMDD_HHMM_{sanitized_provider_name}

        Returns:
            The full path to the created directory.
        """
        timestamp = self._run_timestamp.strftime("%Y%m%d_%H%M")
        safe_provider = "".join(
            c if c.isalnum() or c in '-_' else '_'
            for c in self.provider_name
        )
        folder_name = f"{timestamp}_{safe_provider}"
        self.current_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(self.current_dir, exist_ok=True)
        return self.current_dir

    def cleanup_old_folders(self, debug: bool = False) -> int:
        """Remove output folders older than retention_days.

        Scans the base directory for folders matching the YYYYMMDD_HHMM_* pattern,
        parses the timestamp, and deletes folders that are older than the cutoff.

        Args:
            debug: If True, print each deleted folder name.

        Returns:
            The number of folders deleted.
        """
        if self.retention_days <= 0:
            return 0

        if not os.path.exists(self.base_dir):
            return 0

        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        pattern = re.compile(r'^(\d{8})_(\d{4})_.*$')

        for folder_name in os.listdir(self.base_dir):
            folder_path = os.path.join(self.base_dir, folder_name)

            if not os.path.isdir(folder_path):
                continue

            match = pattern.match(folder_name)
            if not match:
                continue

            try:
                date_str = match.group(1)
                time_str = match.group(2)
                folder_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")

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
        """Get the full path for a file in the current output directory.

        Args:
            filename: The filename (e.g., "oaa_payload.json").

        Returns:
            The full path to the file.

        Raises:
            RuntimeError: If create_timestamped_dir() has not been called yet.
        """
        if not self.current_dir:
            raise RuntimeError("Output directory not created. Call create_timestamped_dir() first.")
        return os.path.join(self.current_dir, filename)
