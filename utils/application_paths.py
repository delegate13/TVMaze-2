"""Resolve bundled resources and writable application data locations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APPLICATION_NAME = "TVMazeShowFinder"


def get_resource_directory() -> Path:
    """Return the directory containing bundled or source application resources."""
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory is not None:
        return Path(bundle_directory)
    return Path(__file__).resolve().parents[1]


def get_user_data_directory() -> Path:
    """Return a per-user writable directory for logs and application state."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APPLICATION_NAME
        return Path.home() / "AppData" / "Local" / APPLICATION_NAME

    state_directory = os.environ.get("XDG_STATE_HOME")
    if state_directory:
        return Path(state_directory) / APPLICATION_NAME
    return Path.home() / ".local" / "state" / APPLICATION_NAME


def get_log_file_path() -> Path:
    """Return the writable log path for packaged and source deployments."""
    if getattr(sys, "frozen", False):
        return get_user_data_directory() / "logs" / "application.log"
    return get_resource_directory() / "logs" / "application.log"


def get_default_config_path() -> Path:
    """Return the bundled default configuration file path."""
    return get_resource_directory() / "config" / "config.json"
