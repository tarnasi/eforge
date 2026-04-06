<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python versions">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/version-0.0.2-blue?style=for-the-badge" alt="Version">
</p>

<h1 align="center">🔐 Environment Forge</h1>

<p align="center">
  <strong>Encrypted environment variable manager for Python.</strong><br>
  Pure Python • No framework dependencies • Works everywhere
</p>

<p align="center">
  <code>pip install environment-forge</code>
</p>

---

## Why Environment Forge?

| Problem | Solution |
|---------|----------|
| `.env` files contain **plaintext secrets** | **Fernet-encrypted vault** (AES-128-CBC + HMAC-SHA256) |
| Secrets leak through git, logs, env dumps | **Single encrypted file** — unreadable without the key |
| Different config for Docker vs local | **Auto-detects** the vault in both environments |
| No validation until runtime crash | **Schema validation** with type casting at startup |
| Tied to one framework | **Pure Python** — works with Django, FastAPI, Flask, or plain scripts |

---

## Quick Start

### 1. Install

```bash
pip install environment-forge

# Optional: install with rich for beautiful CLI tables
pip install environment-forge[rich]
```

### 2. Initialise a vault

```bash
eforge init
```

This creates a `.eforge/` directory in your project:

```
.eforge/
├── secret.key        ← master key (auto-generated, chmod 600)
├── vault.enc         ← encrypted variables
└── schema.json       ← variable declarations (optional)
```

### 3. Store your secrets

```bash
eforge set SECRET_KEY "django-insecure-change-me"
eforge set DATABASE_HOST localhost
eforge set DATABASE_PORT 5432
eforge set DATABASE_PASSWORD supersecret
eforge set DEBUG true
```

### 4. Use in your project

```python
# One line — works in any Python project
import environment_forge
environment_forge.load()

# Now os.environ has all your vault values
import os
print(os.environ["SECRET_KEY"])       # "django-insecure-change-me"
print(os.environ["DATABASE_HOST"])    # "localhost"
```

That's it. No framework-specific setup. Pure Python.

---

## Framework Integration

### Django

```python
# settings.py
import os
import environment_forge

# Load encrypted vault into os.environ BEFORE reading settings
environment_forge.load()

SECRET_KEY = os.environ["SECRET_KEY"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ["DATABASE_HOST"],
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
        "NAME": os.environ["DATABASE_NAME"],
        "USER": os.environ["DATABASE_USER"],
        "PASSWORD": os.environ["DATABASE_PASSWORD"],
    }
}

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
```

### FastAPI

```python
# config.py
import os
import environment_forge

environment_forge.load()

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
```

```python
# main.py
from config import DATABASE_URL, SECRET_KEY

app = FastAPI()
```

### Flask

```python
# app.py
import os
import environment_forge

environment_forge.load()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
```

### Plain Python / Scripts

```python
import os
import environment_forge

environment_forge.load()

api_key = os.environ["API_KEY"]
```

---

## Schema & Validation

Define what variables your project expects, then validate before your app starts.

### Option A: CLI (no Python needed)

```bash
# Declare your schema
eforge schema add SECRET_KEY      --sensitive --desc "Django secret key"
eforge schema add DATABASE_HOST   --desc "Postgres host"
eforge schema add DATABASE_PORT   --desc "Postgres port" --type int
eforge schema add DATABASE_PASSWORD --sensitive --desc "Postgres password"
eforge schema add DEBUG           --optional --default false --type bool

# View it
eforge schema show
```

```
╭───────────────────── Environment Schema ──────────────────────╮
│ #  │ Key               │ Required │ Type │ Default │ 🔒 │ ... │
├────┼───────────────────┼──────────┼──────┼─────────┼────┼─────┤
│ 1  │ SECRET_KEY        │    ✔     │ str  │   —     │ 🔒 │     │
│ 2  │ DATABASE_HOST     │    ✔     │ str  │   —     │ —  │     │
│ 3  │ DATABASE_PORT     │    ✔     │ int  │   —     │ —  │     │
│ 4  │ DATABASE_PASSWORD │    ✔     │ str  │   —     │ 🔒 │     │
│ 5  │ DEBUG             │    —     │ bool │ false   │ —  │     │
╰────┴───────────────────┴──────────┴──────┴─────────┴────┴─────╯
```

```bash
# Validate the vault against the schema
eforge validate
```

```
╭──────────────── Validation Report ─────────────────╮
│ Key               │ Required │ Value      │ Status  │
├───────────────────┼──────────┼────────────┼─────────┤
│ SECRET_KEY        │ required │ dja••••-me │ ✔ set   │
│ DATABASE_HOST     │ required │ localhost  │ ✔ set   │
│ DATABASE_PORT     │ required │ 5432       │ ✔ set   │
│ DATABASE_PASSWORD │ required │ sup••••ret │ ✔ set   │
│ DEBUG             │ optional │ false      │ ↩ dflt  │
╰───────────────────┴──────────┴────────────┴─────────╯

  ✔ All checks passed
```

### Option B: Python code (for programmatic schemas)

```python
from environment_forge import EnvSchema, EnvVar, load_and_validate

# Define schema as a list of EnvVar objects
SCHEMA = EnvSchema([
    EnvVar("SECRET_KEY",        required=True,  sensitive=True,  description="Django secret key"),
    EnvVar("DATABASE_HOST",     required=True,  description="Postgres host"),
    EnvVar("DATABASE_PORT",     required=True,  description="Postgres port",  cast=int),
    EnvVar("DATABASE_PASSWORD", required=True,  sensitive=True,  description="DB password"),
    EnvVar("DEBUG",             required=False, default="false", cast=bool,   description="Debug mode"),
])

# Load vault + inject into os.environ + validate — all in one call
result = load_and_validate(SCHEMA)

# result.resolved contains type-casted values:
# {
#     "SECRET_KEY": "django-insecure-change-me",
#     "DATABASE_HOST": "localhost",
#     "DATABASE_PORT": 5432,            ← int
#     "DATABASE_PASSWORD": "supersecret",
#     "DEBUG": False,                    ← bool
# }
```

If validation fails, you get a clear error and the process exits:

```
environment-forge: validation failed
  Missing: REDIS_URL, API_KEY
  Error: DATABASE_PORT: cannot cast 'abc' to int
```

---

## CLI Reference

### Vault Management

| Command | Description |
|---------|-------------|
| `eforge init` | Create a new encrypted vault |
| `eforge set KEY VALUE [-s section]` | Store or update a value |
| `eforge get KEY [-s section] [--raw]` | Retrieve a value |
| `eforge delete KEY [-s section]` | Remove a key |
| `eforge list [-s section]` | List all keys in a section |
| `eforge status` | Overview of all sections with schema annotations |
| `eforge sections` | List all section names |

### Import / Export

| Command | Description |
|---------|-------------|
| `eforge import .env [-s section]` | Import from a `.env` file into the vault |
| `eforge export [-s section] [-o file]` | Export as `.env` format |
| `eforge inject [-s section]` | Print `export` statements for shell sourcing |

### Schema & Validation

| Command | Description |
|---------|-------------|
| `eforge schema add KEY [options]` | Declare an expected variable |
| `eforge schema remove KEY` | Remove a declaration |
| `eforge schema show` | Display the full schema |
| `eforge validate` | Validate vault against schema |

#### Schema add options

```
--optional       Mark as optional (default: required)
--desc TEXT       Description
--type TYPE      Type: str, int, float, bool
--default VALUE  Default value when not set
--sensitive      Mask value in output (passwords, tokens)
-s SECTION       Section (default: default)
```

### Other

| Command | Description |
|---------|-------------|
| `eforge destroy [-f]` | Delete vault and key from disk |

### Global Options

```bash
eforge --vault /path/to/.eforge set KEY VALUE   # custom vault location
```

---

## Sections

Organise variables into logical groups:

```bash
eforge set HOST pg     -s postgres
eforge set PORT 5432   -s postgres
eforge set URL redis://localhost -s redis

eforge list -s postgres     # list only postgres keys
eforge export -s redis      # export only redis section
eforge inject -s postgres   # inject only postgres vars
```

In Python:

```python
import environment_forge

# Inject only a specific section
environment_forge.load(section="postgres")

# Or inject everything
environment_forge.load()
```

---

## Docker

### Mount the vault as a volume

```bash
# Build your vault locally
eforge init && eforge import .env

# Mount into container
docker run -v $(pwd)/.eforge:/app/.eforge myapp
```

### Pass the secret via environment

```bash
docker run -e EFORGE_SECRET=$(cat .eforge/secret.key) myapp
```

### Docker Compose

```yaml
services:
  app:
    build: .
    volumes:
      - ./.eforge:/app/.eforge:ro
```

### In your Dockerfile

```dockerfile
FROM python:3.12-slim
RUN pip install environment-forge
COPY . /app
WORKDIR /app

# Option 1: Shell injection
CMD ["sh", "-c", "eval $(eforge inject) && python manage.py runserver"]

# Option 2: Python injection (in your entrypoint)
CMD ["python", "manage.py", "runserver"]
# Just add `import environment_forge; environment_forge.load()` to settings.py
```

### Auto-detection

`environment_forge.load()` finds the vault automatically:

1. `EFORGE_VAULT_PATH` env var → explicit path
2. `/run/secrets/eforge` → Docker secrets mount
3. `.eforge/` in current directory → local development

---

## Python API Reference

### `environment_forge.load()`

```python
load(
    section: str = None,        # inject one section, or all if None
    overwrite: bool = False,    # overwrite existing os.environ keys?
    vault_path: str = None,     # explicit vault directory
    validate: bool = False,     # validate against schema.json if it exists
) -> Vault
```

### `environment_forge.load_and_validate()`

```python
load_and_validate(
    schema: EnvSchema,          # your schema object
    section: str = None,
    overwrite: bool = False,
    vault_path: str = None,
) -> ValidationResult
```

### `Vault`

```python
vault = Vault()                         # or Vault(path="/custom/.eforge")

vault.set("KEY", "value")              # store
vault.set("KEY", "value", section="db")  # store in section
vault.get("KEY")                        # retrieve (None if missing)
vault.delete("KEY")                     # remove
vault.all()                             # dict of all keys in default section
vault.flat()                            # dict of all keys across all sections
vault.sections()                        # list of section names

vault.import_env(".env")               # import from .env file
vault.export_env()                      # export as .env text
vault.inject()                          # inject into os.environ
vault.inject_all()                      # inject all sections
```

### `EnvSchema` & `EnvVar`

```python
schema = EnvSchema([
    EnvVar("KEY", required=True, description="...", cast=int, sensitive=True, default="0", section="default"),
])

result = schema.validate(vault)
# result.valid     → bool
# result.resolved  → dict of type-casted values
# result.missing   → list of missing EnvVar objects
# result.errors    → list of error strings

# Save/load schema as JSON (used by CLI validate)
schema.save(".eforge/")
schema = EnvSchema.load(".eforge/")
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `EFORGE_SECRET` | Master secret (alternative to `secret.key` file) |
| `EFORGE_VAULT_PATH` | Path to vault directory (overrides auto-detection) |

---

## Security

- **Encryption**: Fernet (AES-128-CBC + HMAC-SHA256) via `cryptography`
- **Key derivation**: SHA-256 hash → 32-byte Fernet key
- **File permissions**: `secret.key` and `vault.enc` → `chmod 600`
- **Tamper detection**: HMAC validated before decryption
- **No plaintext on disk**: All values in a single encrypted blob
- **Only dependency**: `cryptography` (pure Python otherwise)

### Best Practices

1. Add `.eforge/` to `.gitignore` — **never commit secrets**
2. Back up `secret.key` separately — without it, the vault is unrecoverable
3. Use `EFORGE_SECRET` env var in CI/CD pipelines
4. Use `eforge validate` in your entrypoint to fail fast

---

## Project Structure

```
environment-forge/
├── src/
│   └── environment_forge/
│       ├── __init__.py      # Public API: load(), load_and_validate()
│       ├── cli.py           # eforge CLI (rich optional)
│       ├── crypto.py        # Fernet encryption engine
│       ├── vault.py         # Encrypted key-value store
│       ├── schema.py        # EnvVar / EnvSchema / ValidationResult
│       └── loader.py        # Framework-agnostic loader
├── tests/
├── pyproject.toml           # pip install environment-forge
├── Makefile
├── LICENSE
└── README.md
```

---

## Development

```bash
git clone https://github.com/tarnasi/eforge.git
cd eforge
make dev        # install with dev + rich deps
make test       # run tests
make build      # build for PyPI
make publish    # upload to PyPI
```

---

## License

MIT — see [LICENSE](LICENSE).
