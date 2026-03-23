"""User configuration model."""

import tomllib
from pathlib import Path

from pydantic import BaseModel

CONFIG_FILE = Path("~/.config/yaam/config.toml")


class AgentConfig(BaseModel):
    """Global configuration loaded from ~/.config/yaam/config.toml."""

    default_profile: str = ""
    tmux_session_name: str = "agent"
    state_file_path: Path = Path("~/.config/yaam/sessions.json")


def load_config(path: Path | None = None) -> AgentConfig:
    """Load AgentConfig from *path* (defaults to ~/.config/yaam/config.toml).

    Returns an AgentConfig with sensible defaults if the file does not exist.
    """
    config_path = (path or CONFIG_FILE).expanduser()
    if not config_path.exists():
        return AgentConfig()
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)
    return AgentConfig(
        default_profile=data.get("default_profile", ""),
        tmux_session_name=data.get("tmux_session_name", "agent"),
        state_file_path=Path(
            data.get("state_file_path", "~/.config/yaam/sessions.json")
        ).expanduser(),
    )
