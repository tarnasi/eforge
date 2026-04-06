"""
Environment Forge — Encrypted environment variable manager.

Pure Python.  Works with Django, FastAPI, Flask, or any Python project.

Quick start::

    pip install environment-forge
    eforge init
    eforge set SECRET_KEY "my-secret"
    eforge set DATABASE_HOST localhost

In your Python project::

    import environment_forge
    environment_forge.load()           # injects vault into os.environ
"""

__version__ = "0.1.0"

from environment_forge.vault import Vault
from environment_forge.schema import EnvSchema, EnvVar, ValidationResult
from environment_forge.loader import load, load_and_validate

__all__ = [
    "Vault",
    "EnvSchema",
    "EnvVar",
    "ValidationResult",
    "load",
    "load_and_validate",
    "__version__",
]
