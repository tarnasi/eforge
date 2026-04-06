"""Tests for Docker volume support — loader detection and docker-init CLI."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from environment_forge.loader import _find_vault_dir
from environment_forge.vault import Vault


# ── Loader auto-detection ────────────────────────────────────────────────


def test_find_vault_env_var_takes_priority(tmp_path):
    """EFORGE_VAULT_PATH env var always wins."""
    custom = tmp_path / "custom"
    custom.mkdir()
    with patch.dict(os.environ, {"EFORGE_VAULT_PATH": str(custom)}):
        assert _find_vault_dir() == custom


def test_find_vault_docker_volume(tmp_path, monkeypatch):
    """When /eforge exists (simulated), the loader picks it up."""
    fake_eforge = tmp_path / "eforge"
    fake_eforge.mkdir()

    # Patch the constant so we don't need actual /eforge
    monkeypatch.setattr(Vault, "DOCKER_VOLUME_DIR", str(fake_eforge))

    with patch.dict(os.environ, {}, clear=True):
        # Remove EFORGE_VAULT_PATH if set
        os.environ.pop("EFORGE_VAULT_PATH", None)
        result = _find_vault_dir()
        assert result == fake_eforge


def test_find_vault_falls_back_to_cwd(tmp_path, monkeypatch):
    """Without env var or Docker paths, falls back to .eforge in cwd."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Vault, "DOCKER_VOLUME_DIR", "/nonexistent_eforge_test_path")

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("EFORGE_VAULT_PATH", None)
        result = _find_vault_dir()
        assert result == tmp_path / ".eforge"


def test_docker_volume_dir_constant():
    """DOCKER_VOLUME_DIR is defined on Vault."""
    assert Vault.DOCKER_VOLUME_DIR == "/eforge"


# ── docker-init CLI ─────────────────────────────────────────────────────


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "environment_forge.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_docker_init_fresh(tmp_path):
    """docker-init creates a vault at the given path."""
    target = tmp_path / "eforge"
    target.mkdir()
    result = _run("docker-init", "--path", str(target), cwd=tmp_path)
    assert result.returncode == 0
    assert "initialised" in result.stdout.lower()
    assert (target / "vault.enc").is_file() or (target / "secret.key").is_file()


def test_docker_init_copy_from(tmp_path):
    """docker-init --copy-from copies vault files to target."""
    # Create a source vault
    source = tmp_path / "source"
    vault = Vault(path=source)
    vault.set("DB_HOST", "localhost")

    # Target
    target = tmp_path / "eforge"
    target.mkdir()

    result = _run("docker-init", "--path", str(target), "--copy-from", str(source), cwd=tmp_path)
    assert result.returncode == 0
    assert (target / "vault.enc").is_file()
    assert (target / "secret.key").is_file()

    # Verify the copied vault is readable
    copied_vault = Vault(path=target)
    assert copied_vault.get("DB_HOST") == "localhost"


def test_docker_init_auto_detects_local_eforge(tmp_path):
    """docker-init auto-detects .eforge in cwd when no --copy-from given."""
    # Create a local .eforge
    local = tmp_path / ".eforge"
    vault = Vault(path=local)
    vault.set("KEY", "value")

    target = tmp_path / "eforge"
    target.mkdir()

    result = _run("docker-init", "--path", str(target), cwd=tmp_path)
    assert result.returncode == 0
    assert (target / "vault.enc").is_file()

    copied = Vault(path=target)
    assert copied.get("KEY") == "value"


def test_docker_init_refuses_overwrite(tmp_path):
    """docker-init refuses to overwrite an existing vault without --force."""
    target = tmp_path / "eforge"
    vault = Vault(path=target)
    vault.set("X", "1")

    result = _run("docker-init", "--path", str(target), cwd=tmp_path)
    assert result.returncode == 0
    assert "already exists" in result.stdout.lower()


def test_docker_init_force_overwrite(tmp_path):
    """docker-init --force reinitialises an existing vault."""
    target = tmp_path / "eforge"
    vault = Vault(path=target)
    vault.set("X", "1")

    # Create a source with different data
    source = tmp_path / "source"
    vault2 = Vault(path=source)
    vault2.set("Y", "2")

    result = _run("docker-init", "--path", str(target), "--copy-from", str(source), "--force", cwd=tmp_path)
    assert result.returncode == 0
    assert "initialised" in result.stdout.lower()

    copied = Vault(path=target)
    assert copied.get("Y") == "2"


def test_docker_init_copies_schema(tmp_path):
    """docker-init copies schema.json when present."""
    from environment_forge.schema import EnvSchema, EnvVar

    source = tmp_path / "source"
    vault = Vault(path=source)
    vault.set("HOST", "localhost")

    schema = EnvSchema()
    schema.add(EnvVar(name="HOST", required=True))
    schema.save(source)

    target = tmp_path / "eforge"
    target.mkdir()

    result = _run("docker-init", "--path", str(target), "--copy-from", str(source), cwd=tmp_path)
    assert result.returncode == 0
    assert (target / "schema.json").is_file()
