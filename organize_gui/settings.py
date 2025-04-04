# organize_gui/settings.py
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from platformdirs import user_config_path


class Settings:
    """Application settings manager"""
    
    def __init__(self):
        """Initialize settings"""
        self.config_dir = Path(user_config_path(appname="organize", ensure_exists=True))
        self.settings_file = self.config_dir / "gui_settings.json"
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except Exception:
                return self._default_settings()
        else:
            return self._default_settings()
    
    def save(self) -> None:
        """Save settings to file"""
        with open(self.settings_file, "w") as f:
            json.dump(self.data, f, indent=2)
    
    def _default_settings(self) -> Dict[str, Any]:
        """Return default settings"""
        return {
            "start_minimized": False,
            "minimize_to_tray": True,
            "show_notifications": True,
            "parallel_processing": True,
            "max_workers": 4,
            "default_config": "",
            "indexing_enabled": True,
            "index_on_startup": False,
            "index_directories": [],
            "watch_directories": [],
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value"""
        self.data[key] = value
    
    def reset(self) -> None:
        """Reset all settings to defaults"""
        self.data = self._default_settings()
        self.save()