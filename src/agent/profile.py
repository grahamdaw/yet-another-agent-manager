"""AgentProfile model and loader."""

import contextlib
import importlib.resources
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class ProfileNotFoundError(FileNotFoundError):
    """Raised when a named profile file does not exist."""


class ProfileValidationError(RuntimeError):
    """Raised when a profile fails validation (e.g. non-executable script)."""


PROFILES_DIR = Path("~/.config/agent/profiles")


def _profiles_dir() -> Path:
    return PROFILES_DIR.expanduser()


def _ensure_example_profile() -> None:
    """Write the bundled example.toml to the profiles dir if it is empty."""
    d = _profiles_dir()
    d.mkdir(parents=True, exist_ok=True)
    if any(d.glob("*.toml")):
        return
    example_dest = d / "example.toml"
    ref = importlib.resources.files("agent.profiles").joinpath("example.toml")
    example_dest.write_text(ref.read_text(encoding="utf-8"), encoding="utf-8")


class AgentProfile(BaseModel):
    """Named configuration for an agent role."""

    name: str
    description: str = ""
    repo_path: Path
    default_branch_prefix: str = "agent/"
    tmux_setup_script: Path
    init_script: Path
    init_env: dict[str, str] = Field(default_factory=dict)


def _parse_toml(path: Path) -> AgentProfile:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return AgentProfile(
        name=data["profile"]["name"],
        description=data["profile"].get("description", ""),
        repo_path=Path(data["repo"]["path"]).expanduser(),
        default_branch_prefix=data["repo"].get("default_branch_prefix", "agent/"),
        tmux_setup_script=Path(data["tmux"]["setup_script"]).expanduser(),
        init_script=Path(data["init"]["script"]).expanduser(),
        init_env=data["init"].get("env", {}),
    )


def load(name: str) -> AgentProfile:
    """Load and return the profile named *name*.

    Reads ``~/.config/agent/profiles/<name>.toml``.
    Raises ProfileNotFoundError if the file does not exist.
    Raises pydantic.ValidationError if required fields are missing.
    """
    path = _profiles_dir() / f"{name}.toml"
    if not path.exists():
        raise ProfileNotFoundError(f"Profile '{name}' not found at {path}")
    return _parse_toml(path)


def list_profiles() -> list[AgentProfile]:
    """Return all valid profiles from the profiles directory.

    Silently skips files that fail to parse.
    """
    d = _profiles_dir()
    if not d.exists():
        return []
    profiles = []
    for path in sorted(d.glob("*.toml")):
        with contextlib.suppress(Exception):
            profiles.append(_parse_toml(path))
    return profiles


def validate(profile: AgentProfile) -> list[str]:
    """Check that a profile's referenced paths exist and are executable.

    Returns a list of human-readable issue strings.  An empty list means
    the profile is valid.  Raises ProfileValidationError if any script
    path exists but is not executable.
    """
    issues: list[str] = []

    if not profile.repo_path.exists():
        issues.append(f"repo path does not exist: {profile.repo_path}")

    for label, script in [
        ("tmux setup script", profile.tmux_setup_script),
        ("init script", profile.init_script),
    ]:
        if not script.exists():
            issues.append(f"{label} not found: {script}")
        elif not os.access(script, os.X_OK):
            raise ProfileValidationError(f"{label} is not executable: {script}")

    return issues
