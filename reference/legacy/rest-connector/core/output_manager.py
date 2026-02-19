"""
Output Manager - Timestamped output folder management.
Adapted from odie-oaa reference implementation.
"""

import os
import re
import shutil
from datetime import datetime, timedelta


class OutputManager:
    def __init__(self, base_dir: str, provider_name: str, retention_days: int = 30):
        self.base_dir = base_dir
        self.provider_name = provider_name
        self.retention_days = retention_days
        self.current_dir = None
        self._run_timestamp = datetime.now()

    def create_timestamped_dir(self) -> str:
        timestamp = self._run_timestamp.strftime("%Y%m%d_%H%M")
        safe_provider = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.provider_name)
        folder_name = f"{timestamp}_{safe_provider}"
        self.current_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(self.current_dir, exist_ok=True)
        return self.current_dir

    def cleanup_old_folders(self, debug: bool = False) -> int:
        if self.retention_days <= 0 or not os.path.exists(self.base_dir):
            return 0
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        pattern = re.compile(r"^(\d{8})_(\d{4})_.*$")
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
            except (ValueError, OSError):
                continue
        return deleted_count

    def get_output_path(self, filename: str) -> str:
        if not self.current_dir:
            raise RuntimeError("Output directory not created. Call create_timestamped_dir() first.")
        return os.path.join(self.current_dir, filename)
