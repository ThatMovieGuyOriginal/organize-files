# organize_gui/config_manager.py
import os
from pathlib import Path
from typing import List, Optional

from organize import Config
from organize.find_config import list_configs as list_organize_configs
from organize.rule import Rule

from .settings import Settings


class ConfigManager:
    """Manages organize configurations"""
    
    def __init__(self, settings: Settings):
        """Initialize config manager"""
        self.settings = settings
        self.current_config: Optional[Config] = None
        self.current_config_path: Optional[Path] = None
    
    def list_configs(self) -> List[str]:
        """List available configurations"""
        configs = []
        
        # Add configs from organize's default locations
        for path in list_organize_configs():
            configs.append(path.stem)
            
        # Add user's default config if it exists and isn't already listed
        default_config = self.settings.get("default_config", "")
        if default_config and os.path.exists(default_config):
            name = os.path.basename(default_config)
            if name not in configs:
                configs.append(name)
                
        return configs
    
    def load_config(self, name: str) -> None:
        """Load a configuration by name"""
        # Check if it's a file path
        if os.path.isfile(name):
            self.load_config_from_path(name)
            return
            
        # Look in organize's default locations
        for path in list_organize_configs():
            if path.stem == name:
                self.load_config_from_path(str(path))
                return
                
        # Check if it's the default config
        default_config = self.settings.get("default_config", "")
        if default_config and os.path.basename(default_config) == name:
            self.load_config_from_path(default_config)
            return
            
        # Create a new config with this name
        self.create_new_config(name)
    
    def load_config_from_path(self, path: str) -> None:
        """Load a configuration from path"""
        try:
            self.current_config = Config.from_path(Path(path))
            self.current_config_path = Path(path)
        except Exception as e:
            raise ValueError(f"Failed to load config: {str(e)}")
    
    def create_new_config(self, name: str) -> None:
        """Create a new configuration"""
        # Create a basic config with a single rule
        self.current_config = Config(rules=[])
        
        # Determine the path
        config_dir = Path(self.settings.settings_file).parent
        self.current_config_path = config_dir / f"{name}.yaml"
        
        # Save the config
        self.save_current_config()
    
    def save_current_config(self) -> None:
        """Save the current configuration"""
        if not self.current_config or not self.current_config_path:
            return
            
        # Convert config to YAML
        import yaml

        # Create the directory if it doesn't exist
        self.current_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the config
        with open(self.current_config_path, "w") as f:
            yaml.dump({"rules": self.current_config.rules}, f, default_flow_style=False)
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the current configuration"""
        if not self.current_config:
            return
            
        self.current_config.rules.append(rule)
    
    def update_rule(self, index: int, rule: Rule) -> None:
        """Update a rule in the current configuration"""
        if not self.current_config or index >= len(self.current_config.rules):
            return
            
        self.current_config.rules[index] = rule
    
    def delete_rule(self, index: int) -> None:
        """Delete a rule from the current configuration"""
        if not self.current_config or index >= len(self.current_config.rules):
            return
            
        del self.current_config.rules[index]