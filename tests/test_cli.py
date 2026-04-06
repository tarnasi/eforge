"""Tests for the CLI (eforge command)."""

import subprocess
import sys


def _run(*args, cwd=None):
    """Run eforge CLI and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "environment_forge.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_cli_init(tmp_path):
    result = _run("init", "--vault", str(tmp_path / ".eforge"), cwd=tmp_path)
    assert result.returncode == 0
    assert "initialised" in result.stdout.lower() or "Vault" in result.stdout


def test_cli_set_and_get(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "MY_KEY", "my_value", "--vault", vault, cwd=tmp_path)
    result = _run("get", "MY_KEY", "--raw", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "my_value"


def test_cli_delete(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "DEL_KEY", "val", "--vault", vault, cwd=tmp_path)
    result = _run("delete", "DEL_KEY", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0


def test_cli_list(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "A", "1", "--vault", vault, cwd=tmp_path)
    _run("set", "B", "2", "--vault", vault, cwd=tmp_path)
    result = _run("list", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0


def test_cli_import_export(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("X=1\nY=2\n")
    vault = str(tmp_path / ".eforge")

    result = _run("import", str(env_file), "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0

    result = _run("export", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "X=1" in result.stdout


def test_cli_inject(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "SHELL_VAR", "hello", "--vault", vault, cwd=tmp_path)
    result = _run("inject", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "export SHELL_VAR='hello'" in result.stdout


def test_cli_destroy(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("init", "--vault", vault, cwd=tmp_path)
    result = _run("destroy", "--force", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0


# ── Schema & Validate CLI ───────────────────────────────────────────────


def test_cli_schema_add_show(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("init", "--vault", vault, cwd=tmp_path)

    result = _run("schema", "add", "DB_HOST", "--desc", "Database host", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "DB_HOST" in result.stdout

    result = _run("schema", "add", "DB_PORT", "--type", "int", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0

    result = _run("schema", "show", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "DB_HOST" in result.stdout
    assert "DB_PORT" in result.stdout


def test_cli_schema_remove(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("init", "--vault", vault, cwd=tmp_path)

    _run("schema", "add", "TEMP", "--vault", vault, cwd=tmp_path)
    result = _run("schema", "remove", "TEMP", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "removed" in result.stdout.lower()

    # Remove non-existent
    result = _run("schema", "remove", "NONEXIST", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 1


def test_cli_validate_pass(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "KEY1", "val1", "--vault", vault, cwd=tmp_path)
    _run("set", "KEY2", "val2", "--vault", vault, cwd=tmp_path)

    _run("schema", "add", "KEY1", "--vault", vault, cwd=tmp_path)
    _run("schema", "add", "KEY2", "--vault", vault, cwd=tmp_path)

    result = _run("validate", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "passed" in result.stdout.lower()


def test_cli_validate_fail(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("init", "--vault", vault, cwd=tmp_path)

    _run("schema", "add", "REQUIRED_KEY", "--vault", vault, cwd=tmp_path)

    result = _run("validate", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 1
    assert "failed" in result.stdout.lower() or "missing" in result.stdout.lower()


def test_cli_schema_add_optional_with_default(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("init", "--vault", vault, cwd=tmp_path)

    result = _run("schema", "add", "DEBUG", "--optional", "--default", "false", "--type", "bool", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    assert "optional" in result.stdout.lower()

    # Validate should pass (optional with default)
    result = _run("validate", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0


def test_cli_status_with_schema(tmp_path):
    vault = str(tmp_path / ".eforge")
    _run("set", "HOST", "localhost", "--vault", vault, cwd=tmp_path)
    _run("schema", "add", "HOST", "--vault", vault, cwd=tmp_path)
    _run("schema", "add", "PORT", "--vault", vault, cwd=tmp_path)

    result = _run("status", "--vault", vault, cwd=tmp_path)
    assert result.returncode == 0
    # Should show HOST as set and PORT as missing
    assert "HOST" in result.stdout
