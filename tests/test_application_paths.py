"""Tests for source and packaged application paths."""

from pathlib import Path

from utils.application_paths import (
    get_default_config_path,
    get_log_file_path,
    get_resource_directory,
    get_user_data_directory,
)


def test_source_resources_resolve_from_project_root(monkeypatch):
    """Use the repository root for configuration in source checkouts."""
    monkeypatch.delattr("utils.application_paths.sys._MEIPASS", raising=False)

    resource_directory = get_resource_directory()

    assert get_default_config_path() == resource_directory / "config" / "config.json"


def test_bundle_resources_resolve_from_meipass(tmp_path, monkeypatch):
    """Find files bundled by PyInstaller below its extraction directory."""
    monkeypatch.setattr("utils.application_paths.sys._MEIPASS", str(tmp_path), raising=False)

    assert get_resource_directory() == tmp_path
    assert get_default_config_path() == tmp_path / "config" / "config.json"


def test_windows_user_data_directory_uses_local_appdata(monkeypatch, tmp_path):
    """Keep installed application state outside protected install folders."""
    monkeypatch.setattr("utils.application_paths.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert get_user_data_directory() == tmp_path / "TVMazeShowFinder"


def test_packaged_logs_use_writable_user_data_directory(monkeypatch, tmp_path):
    """Route packaged logs to per-user data instead of the install directory."""
    monkeypatch.setattr("utils.application_paths.sys.frozen", True, raising=False)
    monkeypatch.setattr("utils.application_paths.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert get_log_file_path() == (
        Path(tmp_path) / "TVMazeShowFinder" / "logs" / "application.log"
    )
