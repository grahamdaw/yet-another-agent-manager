"""Unit tests for agent.profile module."""

import stat
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from yaam.profile import (
    AgentProfile,
    ProfileNotFoundError,
    ProfileValidationError,
    _ensure_example_profile,
    list_profiles,
    load,
    validate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_TOML = """\
[profile]
name = "test"
description = "Test profile"

[repo]
path = "/fake/repo"

[tmux]
setup_script = "/fake/scripts/tmux.sh"

[init]
script = "/fake/scripts/init.sh"
env = { FOO = "bar" }
"""


def _write_profile(directory: Path, name: str, content: str = MINIMAL_TOML) -> Path:
    path = directory / f"{name}.toml"
    path.write_text(content)
    return path


def _make_profile(**kwargs) -> AgentProfile:
    defaults = dict(
        name="test",
        description="desc",
        repo_path=Path("/fake/repo"),
        tmux_setup_script=Path("/fake/scripts/tmux.sh"),
        init_script=Path("/fake/scripts/init.sh"),
        init_env={"FOO": "bar"},
    )
    defaults.update(kwargs)
    return AgentProfile(**defaults)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


def test_load_returns_profile(tmp_path):
    _write_profile(tmp_path, "test")
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        p = load("test")
    assert p.name == "test"
    assert p.description == "Test profile"
    assert p.repo_path == Path("/fake/repo")
    assert p.tmux_setup_script == Path("/fake/scripts/tmux.sh")
    assert p.init_script == Path("/fake/scripts/init.sh")
    assert p.init_env == {"FOO": "bar"}


def test_load_raises_profile_not_found(tmp_path):
    with (
        patch("yaam.profile._profiles_dir", return_value=tmp_path),
        pytest.raises(ProfileNotFoundError, match="missing"),
    ):
        load("missing")


def test_load_expands_home(tmp_path):
    content = MINIMAL_TOML.replace("/fake/repo", "~/projects/api")
    _write_profile(tmp_path, "home", content)
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        p = load("home")
    assert not str(p.repo_path).startswith("~")


def test_load_defaults_empty_env(tmp_path):
    content = MINIMAL_TOML.replace('env = { FOO = "bar" }', "")
    _write_profile(tmp_path, "noenv", content)
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        p = load("noenv")
    assert p.init_env == {}


# ---------------------------------------------------------------------------
# list_profiles()
# ---------------------------------------------------------------------------


def test_list_profiles_returns_all(tmp_path):
    _write_profile(tmp_path, "alpha")
    content_b = MINIMAL_TOML.replace('name = "test"', 'name = "beta"')
    _write_profile(tmp_path, "beta", content_b)
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        profiles = list_profiles()
    assert len(profiles) == 2
    names = {p.name for p in profiles}
    assert "test" in names
    assert "beta" in names


def test_list_profiles_empty_dir(tmp_path):
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        assert list_profiles() == []


def test_list_profiles_missing_dir(tmp_path):
    missing = tmp_path / "no_such_dir"
    with patch("yaam.profile._profiles_dir", return_value=missing):
        assert list_profiles() == []


def test_list_profiles_skips_invalid(tmp_path):
    _write_profile(tmp_path, "good")
    (tmp_path / "bad.toml").write_text("this is not valid toml = = =")
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        profiles = list_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "test"


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_missing_repo(tmp_path):
    p = _make_profile(repo_path=tmp_path / "no_repo")
    issues = validate(p)
    assert any("repo path" in i for i in issues)


def test_validate_missing_tmux_script(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    p = _make_profile(repo_path=repo, tmux_setup_script=tmp_path / "no_tmux.sh")
    issues = validate(p)
    assert any("tmux setup script" in i for i in issues)


def test_validate_missing_init_script(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmux_sh = tmp_path / "tmux.sh"
    tmux_sh.touch()
    tmux_sh.chmod(tmux_sh.stat().st_mode | stat.S_IEXEC)
    no_init = tmp_path / "no_init.sh"
    p = _make_profile(repo_path=repo, tmux_setup_script=tmux_sh, init_script=no_init)
    issues = validate(p)
    assert any("init script" in i for i in issues)


def test_validate_non_executable_tmux_script_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmux_sh = tmp_path / "tmux.sh"
    tmux_sh.touch()
    tmux_sh.chmod(0o644)  # not executable
    init_sh = tmp_path / "init.sh"
    init_sh.touch()
    p = _make_profile(repo_path=repo, tmux_setup_script=tmux_sh, init_script=init_sh)
    with pytest.raises(ProfileValidationError, match="not executable"):
        validate(p)


def test_validate_non_executable_init_script_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmux_sh = tmp_path / "tmux.sh"
    tmux_sh.touch()
    tmux_sh.chmod(tmux_sh.stat().st_mode | stat.S_IEXEC)
    init_sh = tmp_path / "init.sh"
    init_sh.touch()
    init_sh.chmod(0o644)  # not executable
    p = _make_profile(repo_path=repo, tmux_setup_script=tmux_sh, init_script=init_sh)
    with pytest.raises(ProfileValidationError, match="not executable"):
        validate(p)


def test_validate_passes_for_valid_profile(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tmux_sh = tmp_path / "tmux.sh"
    tmux_sh.touch()
    tmux_sh.chmod(tmux_sh.stat().st_mode | stat.S_IEXEC)
    init_sh = tmp_path / "init.sh"
    init_sh.touch()
    init_sh.chmod(init_sh.stat().st_mode | stat.S_IEXEC)
    p = _make_profile(repo_path=repo, tmux_setup_script=tmux_sh, init_script=init_sh)
    assert validate(p) == []


# ---------------------------------------------------------------------------
# _ensure_example_profile()
# ---------------------------------------------------------------------------


def test_ensure_example_creates_file(tmp_path):
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        _ensure_example_profile()
    files = list(tmp_path.glob("*.toml"))
    assert len(files) == 1
    assert files[0].name == "example.toml"
    data = tomllib.loads(files[0].read_text())
    assert data["profile"]["name"] == "example"


def test_ensure_example_skips_if_profiles_exist(tmp_path):
    _write_profile(tmp_path, "existing")
    with patch("yaam.profile._profiles_dir", return_value=tmp_path):
        _ensure_example_profile()
    # should not overwrite — only the existing profile remains
    files = list(tmp_path.glob("*.toml"))
    assert len(files) == 1
    assert files[0].name == "existing.toml"
