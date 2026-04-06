"""Tests for the schema validation module."""

import json

from environment_forge.schema import EnvSchema, EnvVar
from environment_forge.vault import Vault


def test_validate_all_present(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("HOST", "localhost")
    vault.set("PORT", "5432")

    schema = EnvSchema([
        EnvVar("HOST", required=True),
        EnvVar("PORT", required=True, cast=int),
    ])

    result = schema.validate(vault)
    assert result.valid is True
    assert result.resolved["HOST"] == "localhost"
    assert result.resolved["PORT"] == 5432
    assert result.missing == []


def test_validate_missing_required(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")

    schema = EnvSchema([
        EnvVar("HOST", required=True, description="DB host"),
    ])

    result = schema.validate(vault)
    assert result.valid is False
    assert result.missing_keys == ["HOST"]


def test_validate_default_used(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")

    schema = EnvSchema([
        EnvVar("DEBUG", required=False, default="false", cast=bool),
    ])

    result = schema.validate(vault)
    assert result.valid is True
    assert result.resolved["DEBUG"] is False


def test_validate_bool_cast(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("FLAG", "true")

    schema = EnvSchema([
        EnvVar("FLAG", cast=bool),
    ])

    result = schema.validate(vault)
    assert result.resolved["FLAG"] is True


def test_validate_cast_error(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("PORT", "not-a-number")

    schema = EnvSchema([
        EnvVar("PORT", cast=int),
    ])

    result = schema.validate(vault)
    assert result.valid is False
    assert len(result.errors) == 1


def test_mask_sensitive():
    var = EnvVar("SECRET", sensitive=True)
    assert var.mask("supersecretvalue123") == "sup••••123"

    var2 = EnvVar("NAME", sensitive=False)
    assert var2.mask("hello") == "hello"


# ── JSON persistence ────────────────────────────────────────────────────


def test_envvar_to_dict_and_back():
    var = EnvVar("DB_PORT", required=True, cast=int, description="port", default="5432", sensitive=False, section="db")
    d = var.to_dict()
    assert d["name"] == "DB_PORT"
    assert d["type"] == "int"
    assert d["section"] == "db"

    restored = EnvVar.from_dict(d)
    assert restored.name == "DB_PORT"
    assert restored.cast is int
    assert restored.required is True
    assert restored.section == "db"


def test_schema_save_and_load(tmp_path):
    d = tmp_path / ".eforge"
    d.mkdir()

    schema = EnvSchema([
        EnvVar("X", required=True, description="var x", cast=int),
        EnvVar("Y", required=False, default="hello"),
    ])
    schema.save(d)

    loaded = EnvSchema.load(d)
    assert len(loaded) == 2
    assert loaded.get("X").cast is int
    assert loaded.get("Y").default == "hello"


def test_schema_from_file(tmp_path):
    schema_file = tmp_path / "custom_schema.json"
    schema_file.write_text(json.dumps([
        {"name": "A", "required": True},
        {"name": "B", "required": False, "default": "42", "cast": "int"},
    ]))

    schema = EnvSchema.from_file(schema_file)
    assert len(schema) == 2
    assert schema.get("B").cast is int


def test_schema_add_and_remove():
    schema = EnvSchema()
    schema.add(EnvVar("K1", required=True))
    schema.add(EnvVar("K2", required=False))
    assert len(schema) == 2

    assert schema.remove("K1") is True
    assert len(schema) == 1
    assert schema.get("K1") is None

    assert schema.remove("NONEXIST") is False


def test_schema_required_and_optional():
    schema = EnvSchema([
        EnvVar("A", required=True),
        EnvVar("B", required=False),
        EnvVar("C", required=True),
    ])
    assert len(schema.required) == 2
    assert len(schema.optional) == 1


def test_validate_with_sections(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("HOST", "pg", section="db")
    vault.set("API", "key123")

    schema = EnvSchema([
        EnvVar("HOST", required=True, section="db"),
        EnvVar("API", required=True, section="default"),
        EnvVar("MISSING", required=True, section="db"),
    ])

    result = schema.validate(vault)
    assert result.valid is False
    assert result.missing_keys == ["MISSING"]
    assert result.resolved["HOST"] == "pg"
    assert result.resolved["API"] == "key123"


def test_schema_sections(tmp_path):
    vault = Vault(path=tmp_path / ".eforge")
    vault.set("DB_HOST", "pg", section="postgres")

    schema = EnvSchema([
        EnvVar("DB_HOST", section="postgres"),
    ])

    result = schema.validate(vault)
    assert result.valid is True
    assert result.resolved["DB_HOST"] == "pg"
