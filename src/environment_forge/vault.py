"""
Encrypted vault — the core storage engine.

Stores environment variables as an encrypted JSON blob on disk.
Supports namespaced sections (e.g. ``system``, ``postgres``, ``redis``).

File layout::

    <project>/
        .eforge/
            secret.key        ← master secret (auto-generated, 0600)
            vault.enc         ← encrypted JSON blob
"""

import json
import os
from pathlib import Path

from environment_forge.crypto import decrypt, encrypt, get_or_create_secret


class Vault:
    """
    Encrypted key-value store backed by a single ``.enc`` file.

    Parameters
    ----------
    path : str | Path, optional
        Directory that holds ``secret.key`` and ``vault.enc``.
        Defaults to ``<cwd>/.eforge``.
    secret : str, optional
        Explicit master secret. When supplied, ``secret.key`` is not read/created.
    """

    DEFAULT_DIR = ".eforge"
    VAULT_FILE = "vault.enc"
    KEY_FILE = "secret.key"

    def __init__(self, path: str | Path | None = None, secret: str | None = None):
        if path is None:
            path = Path.cwd() / self.DEFAULT_DIR
        self._dir = Path(path)
        self._vault_path = self._dir / self.VAULT_FILE
        self._key_path = self._dir / self.KEY_FILE

        if secret:
            self._secret = secret
        else:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._secret = get_or_create_secret(self._key_path)

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    @property
    def is_initialized(self) -> bool:
        return self._vault_path.is_file()

    # ── Load / Save ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        """Load and decrypt the full vault. Returns {} if missing or invalid."""
        if not self._vault_path.is_file():
            return {}
        ciphertext = self._vault_path.read_text(encoding="utf-8")
        if not ciphertext.strip():
            return {}
        plaintext = decrypt(ciphertext, self._secret)
        return json.loads(plaintext)

    def _save(self, data: dict) -> None:
        """Encrypt and persist the vault dict."""
        self._dir.mkdir(parents=True, exist_ok=True)
        plaintext = json.dumps(data, indent=2)
        ciphertext = encrypt(plaintext, self._secret)
        self._vault_path.write_text(ciphertext, encoding="utf-8")
        # Restrict permissions (owner-only)
        self._vault_path.chmod(0o600)

    # ── Section-level API ────────────────────────────────────────────────

    def sections(self) -> list[str]:
        """List all section names in the vault."""
        return list(self._load().keys())

    def get_section(self, section: str) -> dict:
        """Return a full section dict. Returns {} if missing."""
        return self._load().get(section, {})

    def set_section(self, section: str, data: dict) -> None:
        """Replace (or create) an entire section, preserving others."""
        vault = self._load()
        vault[section] = data
        self._save(vault)

    def delete_section(self, section: str) -> bool:
        """Delete a section. Returns True if it existed."""
        vault = self._load()
        if section not in vault:
            return False
        del vault[section]
        self._save(vault)
        return True

    # ── Key-level API ────────────────────────────────────────────────────

    def get(self, key: str, section: str = "default") -> str | None:
        """Get a single value. Returns None if missing."""
        return self._load().get(section, {}).get(key)

    def set(self, key: str, value: str, section: str = "default") -> None:
        """Set a single key-value pair in a section."""
        vault = self._load()
        vault.setdefault(section, {})[key] = value
        self._save(vault)

    def delete(self, key: str, section: str = "default") -> bool:
        """Delete a key from a section. Returns True if it existed."""
        vault = self._load()
        sec = vault.get(section, {})
        if key not in sec:
            return False
        del sec[key]
        if not sec:
            del vault[section]
        self._save(vault)
        return True

    def all(self, section: str = "default") -> dict:
        """Return all key-value pairs in a section."""
        return dict(self._load().get(section, {}))

    def flat(self) -> dict:
        """Return all key-value pairs across all sections (flat dict)."""
        result = {}
        for sec_data in self._load().values():
            if isinstance(sec_data, dict):
                result.update(sec_data)
        return result

    # ── Bulk Operations ──────────────────────────────────────────────────

    def import_env(self, env_file: str | Path, section: str = "default") -> int:
        """
        Import key-value pairs from a ``.env`` file into a section.

        Returns the number of keys imported.
        """
        env_path = Path(env_file)
        if not env_path.is_file():
            raise FileNotFoundError(f"File not found: {env_path}")

        vault = self._load()
        sec = vault.setdefault(section, {})
        count = 0

        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            sec[key] = value
            count += 1

        self._save(vault)
        return count

    def export_env(self, section: str = "default") -> str:
        """Export a section as ``.env`` formatted text."""
        lines = []
        for key, value in sorted(self.all(section).items()):
            # Quote values containing spaces
            if " " in str(value):
                lines.append(f'{key}="{value}"')
            else:
                lines.append(f"{key}={value}")
        return "\n".join(lines) + "\n" if lines else ""

    def inject(self, section: str = "default", overwrite: bool = False) -> int:
        """
        Inject vault values into ``os.environ``.

        Parameters
        ----------
        section : str
            Section to inject from.
        overwrite : bool
            If False (default), skip keys that already exist in os.environ.

        Returns the number of keys injected.
        """
        count = 0
        for key, value in self.all(section).items():
            if not overwrite and key in os.environ:
                continue
            os.environ[key] = str(value)
            count += 1
        return count

    def inject_all(self, overwrite: bool = False) -> int:
        """Inject all sections into ``os.environ``."""
        count = 0
        for sec_data in self._load().values():
            if isinstance(sec_data, dict):
                for key, value in sec_data.items():
                    if not overwrite and key in os.environ:
                        continue
                    os.environ[key] = str(value)
                    count += 1
        return count

    # ── Utilities ────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Remove all data from the vault."""
        self._save({})

    def destroy(self) -> None:
        """Delete the vault file and secret key from disk."""
        if self._vault_path.is_file():
            self._vault_path.unlink()
        if self._key_path.is_file():
            self._key_path.unlink()
        # Remove dir if empty
        try:
            self._dir.rmdir()
        except OSError:
            pass

    def __repr__(self) -> str:
        status = "initialized" if self.is_initialized else "empty"
        return f"<Vault path={self._dir} {status}>"
