"""Tests for the Vault class."""

import os

from environment_forge.vault import Vault


def test_vault_init_creates_dir(tmp_path):
    vault_dir = tmp_path / ".eforge"
    vault = Vault(path=vault_dir)
    assert vault_dir.is_dir()
    assert (vault_dir / "secret.key").is_file()


def test_set_and_get(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("DB_HOST", "localhost")
    assert vault.get("DB_HOST") == "localhost"


def test_get_missing_returns_none(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    assert vault.get("NOPE") is None


def test_set_overwrites(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("KEY", "old")
    vault.set("KEY", "new")
    assert vault.get("KEY") == "new"


def test_delete(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("KEY", "val")
    assert vault.delete("KEY") is True
    assert vault.get("KEY") is None
    assert vault.delete("KEY") is False


def test_sections(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1", section="alpha")
    vault.set("B", "2", section="beta")
    assert sorted(vault.sections()) == ["alpha", "beta"]


def test_get_section(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("X", "1", section="s1")
    vault.set("Y", "2", section="s1")
    assert vault.get_section("s1") == {"X": "1", "Y": "2"}


def test_set_section(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set_section("db", {"HOST": "pg", "PORT": "5432"})
    assert vault.get("HOST", section="db") == "pg"


def test_delete_section(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set_section("temp", {"A": "1"})
    assert vault.delete_section("temp") is True
    assert vault.delete_section("temp") is False


def test_all(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1")
    vault.set("B", "2")
    assert vault.all() == {"A": "1", "B": "2"}


def test_flat(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1", section="s1")
    vault.set("B", "2", section="s2")
    assert vault.flat() == {"A": "1", "B": "2"}


def test_import_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('DB_HOST=localhost\nDB_PORT=5432\n# comment\nDB_PASS="secret"\n')
    vault = Vault(path=tmp_path / ".eforge")
    count = vault.import_env(env_file)
    assert count == 3
    assert vault.get("DB_HOST") == "localhost"
    assert vault.get("DB_PASS") == "secret"


def test_export_env(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1")
    vault.set("B", "hello world")
    output = vault.export_env()
    assert 'A=1' in output
    assert 'B="hello world"' in output


def test_inject(tmp_path, monkeypatch):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("EFORGE_TEST_VAR", "injected")
    monkeypatch.delenv("EFORGE_TEST_VAR", raising=False)
    count = vault.inject()
    assert count == 1
    assert os.environ["EFORGE_TEST_VAR"] == "injected"


def test_inject_no_overwrite(tmp_path, monkeypatch):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("EXISTING", "vault-value")
    monkeypatch.setenv("EXISTING", "env-value")
    vault.inject(overwrite=False)
    assert os.environ["EXISTING"] == "env-value"


def test_inject_overwrite(tmp_path, monkeypatch):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("EXISTING", "vault-value")
    monkeypatch.setenv("EXISTING", "env-value")
    vault.inject(overwrite=True)
    assert os.environ["EXISTING"] == "vault-value"


def test_clear(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1")
    vault.clear()
    assert vault.all() == {}


def test_destroy(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("A", "1")
    assert vault.vault_path.is_file()
    vault.destroy()
    assert not vault.vault_path.is_file()


def test_explicit_secret(tmp_path):
    """Vault with an explicit secret doesn't create a secret.key file."""
    vault_dir = tmp_path / ".eforge"
    vault = Vault(path=vault_dir, secret="my-explicit-secret")
    vault.set("X", "42")
    assert vault.get("X") == "42"
