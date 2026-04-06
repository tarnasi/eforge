"""
Loader & framework integration — pure Python, zero framework dependencies.

Works with Django, FastAPI, Flask, or any Python project.

Quick start (one line in your settings / config)::

    import environment_forge
    environment_forge.load()           # inject all vault values into os.environ

Django::

    # settings.py
    import environment_forge
    environment_forge.load()
    SECRET_KEY = os.environ["SECRET_KEY"]

FastAPI::

    # config.py
    import environment_forge
    environment_forge.load()
    DATABASE_URL = os.environ["DATABASE_URL"]

Flask::

    # app.py or config.py
    import environment_forge
    environment_forge.load()
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]

Docker entrypoint::

    # entrypoint.sh — shell injection
    eval $(eforge inject)
    python manage.py runserver

    # OR — Python injection
    import environment_forge
    environment_forge.load()
"""

from __future__ import annotations

import os
from pathlib import Path

from environment_forge.vault import Vault
from environment_forge.schema import EnvSchema, ValidationResult


def _find_vault_dir() -> Path:
    """
    Locate the vault directory by checking (in order):

    1. ``EFORGE_VAULT_PATH`` environment variable
    2. ``/eforge`` (Docker named volume)
    3. ``/run/secrets/eforge`` (Docker secrets mount)
    4. ``<cwd>/.eforge``
    """
    env_path = os.environ.get("EFORGE_VAULT_PATH", "").strip()
    if env_path:
        return Path(env_path)

    docker_volume = Path(Vault.DOCKER_VOLUME_DIR)
    if docker_volume.is_dir():
        return docker_volume

    docker_secrets = Path("/run/secrets/eforge")
    if docker_secrets.is_dir():
        return docker_secrets

    return Path.cwd() / ".eforge"


def load(
    section: str | None = None,
    overwrite: bool = False,
    vault_path: str | Path | None = None,
    validate: bool = False,
) -> Vault:
    """
    Load the vault and inject its values into ``os.environ``.

    Call this once at startup — before any framework reads ``os.environ``.

    Parameters
    ----------
    section : str, optional
        Inject only this section.  ``None`` → inject all sections.
    overwrite : bool
        If True, overwrite existing env vars (default: skip existing).
    vault_path : str | Path, optional
        Explicit vault directory.  Overrides auto-detection.
    validate : bool
        If True and a ``schema.json`` exists alongside the vault,
        validate after injection.  Raises ``SystemExit(1)`` on failure.

    Returns
    -------
    Vault
        The loaded vault instance for further programmatic use.

    Examples
    --------
    Minimal (works everywhere)::

        import environment_forge
        environment_forge.load()

    With validation::

        import environment_forge
        environment_forge.load(validate=True)

    Specific section::

        environment_forge.load(section="postgres")
    """
    path = Path(vault_path) if vault_path else _find_vault_dir()
    vault = Vault(path=path)

    if section:
        vault.inject(section=section, overwrite=overwrite)
    else:
        vault.inject_all(overwrite=overwrite)

    if validate:
        schema = EnvSchema.load(path)
        if schema.variables:
            result = schema.validate(vault)
            if not result.valid:
                import sys
                lines = ["environment-forge: validation failed"]
                if result.missing:
                    lines.append(f"  Missing: {', '.join(result.missing_keys)}")
                for e in result.errors:
                    lines.append(f"  Error: {e}")
                print("\n".join(lines), file=sys.stderr)
                raise SystemExit(1)

    return vault


def load_and_validate(
    schema: EnvSchema,
    section: str | None = None,
    overwrite: bool = False,
    vault_path: str | Path | None = None,
) -> ValidationResult:
    """
    Load vault, inject into ``os.environ``, and validate against a schema
    defined in Python code.

    Parameters
    ----------
    schema : EnvSchema
        The schema to validate against (defined in your project code).
    section, overwrite, vault_path
        Same as ``load()``.

    Returns
    -------
    ValidationResult
        Contains ``.valid``, ``.resolved``, ``.missing``, ``.errors``.

    Raises
    ------
    SystemExit
        If validation fails.

    Example
    -------
    ::

        from environment_forge import EnvSchema, EnvVar, load_and_validate

        SCHEMA = EnvSchema([
            EnvVar("SECRET_KEY",      required=True, sensitive=True),
            EnvVar("DATABASE_HOST",   required=True, description="Postgres host"),
            EnvVar("DATABASE_PORT",   required=True, cast=int),
            EnvVar("DEBUG",           required=False, default="false", cast=bool),
        ])

        config = load_and_validate(SCHEMA)
        # config.resolved == {"SECRET_KEY": "...", "DATABASE_HOST": "pg", ...}
    """
    path = Path(vault_path) if vault_path else _find_vault_dir()
    vault = Vault(path=path)

    if section:
        vault.inject(section=section, overwrite=overwrite)
    else:
        vault.inject_all(overwrite=overwrite)

    result = schema.validate(vault)

    if not result.valid:
        import sys
        lines = ["environment-forge: validation failed"]
        if result.missing:
            lines.append(f"  Missing: {', '.join(result.missing_keys)}")
        for e in result.errors:
            lines.append(f"  Error: {e}")
        print("\n".join(lines), file=sys.stderr)
        raise SystemExit(1)

    return result
