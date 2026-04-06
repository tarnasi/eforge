"""
Environment schema — declare required and optional variables with validation.

Define your schema as a list of ``EnvVar`` objects, then validate against a
``Vault``.  Schemas can also be saved to / loaded from a JSON file so the CLI
``eforge validate`` command works without writing Python.

Python API::

    from environment_forge import EnvSchema, EnvVar

    schema = EnvSchema([
        EnvVar("DATABASE_HOST",     required=True,  description="Postgres host"),
        EnvVar("DATABASE_PORT",     required=True,  description="Postgres port",  cast=int),
        EnvVar("DATABASE_PASSWORD", required=True,  description="DB password",     sensitive=True),
        EnvVar("DEBUG",             required=False, description="Debug mode",      default="false", cast=bool),
    ])

    result = schema.validate(vault)

CLI (no Python needed)::

    eforge schema add DATABASE_HOST  --required --desc "Postgres host"
    eforge schema add DATABASE_PORT  --required --desc "Postgres port"  --type int
    eforge schema add SECRET_KEY     --required --sensitive
    eforge validate
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Maps type names (used in JSON / CLI) to Python built-ins
_CAST_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}
_CAST_REVERSE: dict[type, str] = {v: k for k, v in _CAST_MAP.items()}


@dataclass
class EnvVar:
    """Declaration of a single environment variable."""

    name: str
    required: bool = True
    description: str = ""
    default: str | None = None
    sensitive: bool = False
    cast: type | None = None
    section: str = "default"

    def mask(self, value: str) -> str:
        """Return a display-safe version of the value."""
        if not self.sensitive or not value:
            return value
        s = str(value)
        if len(s) <= 6:
            return "••••••"
        return s[:3] + "••••" + s[-3:]

    # ── Serialisation ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to a JSON-safe dict."""
        d: dict = {"name": self.name, "required": self.required}
        if self.description:
            d["description"] = self.description
        if self.default is not None:
            d["default"] = self.default
        if self.sensitive:
            d["sensitive"] = True
        if self.cast is not None:
            d["type"] = _CAST_REVERSE.get(self.cast, "str")
        if self.section != "default":
            d["section"] = self.section
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EnvVar":
        """Create from a JSON dict."""
        cast = _CAST_MAP.get(d.get("type") or d.get("cast", ""), None)
        return cls(
            name=d["name"],
            required=d.get("required", True),
            description=d.get("description", ""),
            default=d.get("default"),
            sensitive=d.get("sensitive", False),
            cast=cast,
            section=d.get("section", "default"),
        )


@dataclass
class ValidationResult:
    """Result of validating a schema against a vault."""

    valid: bool = True
    resolved: dict = field(default_factory=dict)
    missing: list[EnvVar] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def missing_keys(self) -> list[str]:
        return [v.name for v in self.missing]


class EnvSchema:
    """
    A collection of ``EnvVar`` declarations for validation.

    Parameters
    ----------
    variables : list[EnvVar]
        List of environment variable definitions.
    """

    SCHEMA_FILE = "schema.json"

    def __init__(self, variables: list[EnvVar] | None = None):
        self._vars: list[EnvVar] = list(variables or [])

    # ── Collection helpers ───────────────────────────────────────────────

    def add(self, var: EnvVar) -> None:
        # Replace existing entry with the same name+section
        self._vars = [v for v in self._vars if not (v.name == var.name and v.section == var.section)]
        self._vars.append(var)

    def remove(self, name: str, section: str = "default") -> bool:
        before = len(self._vars)
        self._vars = [v for v in self._vars if not (v.name == name and v.section == section)]
        return len(self._vars) < before

    def get(self, name: str, section: str = "default") -> EnvVar | None:
        for v in self._vars:
            if v.name == name and v.section == section:
                return v
        return None

    @property
    def variables(self) -> list[EnvVar]:
        return list(self._vars)

    @property
    def required(self) -> list[EnvVar]:
        return [v for v in self._vars if v.required]

    @property
    def optional(self) -> list[EnvVar]:
        return [v for v in self._vars if not v.required]

    # ── Validation ───────────────────────────────────────────────────────

    def validate(self, vault) -> ValidationResult:
        """
        Validate a ``Vault`` instance against this schema.

        Returns a ``ValidationResult`` with resolved values, missing keys,
        and cast errors.
        """
        result = ValidationResult()

        for var in self._vars:
            raw = vault.get(var.name, section=var.section)

            # Fall back to default
            if raw is None and var.default is not None:
                raw = var.default

            if raw is None:
                if var.required:
                    result.valid = False
                    result.missing.append(var)
                continue

            # Type casting
            if var.cast is not None:
                try:
                    if var.cast is bool:
                        casted = str(raw).lower() in ("true", "1", "yes", "on")
                    else:
                        casted = var.cast(raw)
                    result.resolved[var.name] = casted
                except (ValueError, TypeError) as exc:
                    result.valid = False
                    result.errors.append(
                        f"{var.name}: cannot cast {raw!r} to {var.cast.__name__}: {exc}"
                    )
            else:
                result.resolved[var.name] = raw

        return result

    # ── File I/O ─────────────────────────────────────────────────────────

    def save(self, directory: str | Path) -> Path:
        """Save schema to ``<directory>/schema.json``."""
        out = Path(directory) / self.SCHEMA_FILE
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [v.to_dict() for v in self._vars]
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return out

    @classmethod
    def load(cls, directory: str | Path) -> "EnvSchema":
        """Load schema from ``<directory>/schema.json``."""
        path = Path(directory) / cls.SCHEMA_FILE
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([EnvVar.from_dict(d) for d in data])

    @classmethod
    def from_file(cls, path: str | Path) -> "EnvSchema":
        """Load schema from an explicit JSON file path."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Schema file not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls([EnvVar.from_dict(d) for d in data])

    def __len__(self) -> int:
        return len(self._vars)

    def __iter__(self):
        return iter(self._vars)
