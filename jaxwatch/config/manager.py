#!/usr/bin/env python3
"""
JaxWatch Configuration Manager
Centralized configuration management for all JaxWatch components.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM services"""
    model: str
    api_url: str
    api_key: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'LLMConfig':
        return cls(
            model=data.get('model', 'llama3.1:8b'),
            api_url=data.get('api_url', 'http://localhost:11434/api/chat'),
            api_key=data.get('api_key')
        )


@dataclass
class PathConfig:
    """Configuration for file paths"""
    projects_index: Path
    outputs_dir: Path
    raw_dir: Path
    files_dir: Path
    enhanced_projects: Path
    state_dir: Path
    logs_dir: Path

    @classmethod
    def from_dict(cls, data: dict, base_path: Path) -> 'PathConfig':
        outputs_dir = base_path / data.get('outputs_dir', 'outputs')
        return cls(
            projects_index=outputs_dir / data.get('projects_index_path', 'projects/projects_index.json'),
            outputs_dir=outputs_dir,
            raw_dir=outputs_dir / 'raw',
            files_dir=outputs_dir / 'files',
            enhanced_projects=outputs_dir / data.get('enhanced_projects_path', 'projects/enhanced_projects.json'),
            state_dir=outputs_dir / 'state',
            logs_dir=outputs_dir / 'logs',
        )


@dataclass
class SlackConfig:
    """Configuration for Slack integration"""
    bot_token: str
    app_token: str
    channel_id: str

    @classmethod
    def from_dict(cls, data: dict) -> 'SlackConfig':
        return cls(
            bot_token=data.get('bot_token', ''),
            app_token=data.get('app_token', ''),
            channel_id=data.get('channel_id', '')
        )


class JaxWatchConfig:
    """Centralized configuration manager for JaxWatch"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_default_config()
        # Always use project root as base path
        self.base_path = self._find_project_root()
        self._data = self._load_config()

        # Initialize sub-configurations
        self._llm_config = None
        self._path_config = None
        self._slack_config = None

    def _find_default_config(self) -> Path:
        """Find default configuration file"""
        # Always prioritize the project root location
        project_root = self._find_project_root()

        candidates = [
            project_root / 'config.yaml',
            project_root / 'document_verifier/config.yaml',
            Path.cwd() / 'config.yaml',
            Path(__file__).parent.parent.parent / 'config.yaml',
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Return project root location even if it doesn't exist yet
        return project_root / 'config.yaml'

    def _find_project_root(self) -> Path:
        """Find the JaxWatch project root directory"""
        # Start from current working directory
        current = Path.cwd()

        # Look for JaxWatch project markers
        markers = ['outputs/projects', 'dashboard', 'slack_bridge', 'backend/tools']

        # Check current directory and parents
        for path in [current] + list(current.parents):
            if any((path / marker).exists() for marker in markers):
                return path

        # Fallback to current directory
        return current

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_path.exists():
            # Return default configuration
            return self._get_default_config()

        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load config from {self.config_path}: {e}")
            data = self._get_default_config()

        # Merge with defaults to ensure all keys exist
        default_config = self._get_default_config()
        self._merge_dicts(default_config, data)
        return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            'llm': {
                'model': 'llama3.1:8b',
                'api_url': 'http://localhost:11434/api/chat',
                'api_key': None
            },
            'paths': {
                'outputs_dir': 'outputs',
                'projects_index_path': 'projects/projects_index.json',
                'enhanced_projects_path': 'projects/enhanced_projects.json'
            },
            'slack': {
                'bot_token': os.getenv('SLACK_BOT_TOKEN', ''),
                'app_token': os.getenv('SLACK_APP_TOKEN', ''),
                'channel_id': os.getenv('SLACK_CHANNEL_ID', '')
            },
            'features': {
                'enable_debug_logging': True,
                'max_concurrent_jobs': 3,
                'auto_backup_interval_hours': 24
            }
        }

    def _merge_dicts(self, base: dict, overlay: dict):
        """Recursively merge overlay into base dictionary"""
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    @property
    def llm(self) -> LLMConfig:
        """Get LLM configuration"""
        if self._llm_config is None:
            self._llm_config = LLMConfig.from_dict(self._data.get('llm', {}))
        return self._llm_config

    @property
    def paths(self) -> PathConfig:
        """Get paths configuration"""
        if self._path_config is None:
            self._path_config = PathConfig.from_dict(self._data.get('paths', {}), self.base_path)
        return self._path_config

    @property
    def slack(self) -> SlackConfig:
        """Get Slack configuration"""
        if self._slack_config is None:
            self._slack_config = SlackConfig.from_dict(self._data.get('slack', {}))
        return self._slack_config

    def get_feature(self, feature_name: str, default: Any = None) -> Any:
        """Get feature flag value"""
        return self._data.get('features', {}).get(feature_name, default)

    def update_config(self, section: str, updates: dict):
        """Update configuration section"""
        if section not in self._data:
            self._data[section] = {}
        self._data[section].update(updates)

        # Clear cached configs to force reload
        self._llm_config = None
        self._path_config = None
        self._slack_config = None

    def save_config(self):
        """Save current configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(self._data, f, default_flow_style=False, indent=2)


# Global config instance - can be overridden for testing
_global_config = None


def get_config() -> JaxWatchConfig:
    """Get global configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = JaxWatchConfig()
    return _global_config


def set_config(config: JaxWatchConfig):
    """Set global configuration instance (for testing)"""
    global _global_config
    _global_config = config