"""
``eforge`` — CLI for Environment Forge.

Pure-Python encrypted environment manager.  Works with any framework
(Django, FastAPI, Flask, plain Python) or inside Docker containers.

Commands::

    eforge init                           # initialise vault
    eforge set KEY VALUE [-s section]     # store a value
    eforge get KEY [-s section] [--raw]   # retrieve a value
    eforge delete KEY [-s section]        # remove a key
    eforge list [-s section]              # list keys in a section
    eforge status                         # overview of all sections
    eforge sections                       # list section names
    eforge import .env [-s section]       # import from .env file
    eforge export [-s section] [-o file]  # export as .env text
    eforge inject [-s section]            # print shell export statements
    eforge schema add KEY [opts]          # declare an expected variable
    eforge schema remove KEY              # remove a declaration
    eforge schema show                    # show the full schema
    eforge validate                       # check vault against schema
    eforge docker-init [--path /eforge]   # init vault for Docker volume
    eforge destroy [-f]                   # delete vault from disk
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from environment_forge.vault import Vault
from environment_forge.schema import EnvSchema, EnvVar, _CAST_MAP

# ── Rich soft-dependency ────────────────────────────────────────────────
# If rich is installed we get pretty tables; otherwise plain text works.

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    _RICH = True
    console = Console()
    err_console = Console(stderr=True)
except ImportError:  # pragma: no cover
    _RICH = False

    class _PlainConsole:
        """Minimal fallback that strips Rich markup."""
        def __init__(self, stderr: bool = False):
            import re
            self._file = sys.stderr if stderr else sys.stdout
            self._tag_re = re.compile(r"\[/?[a-z_ ]+\]", re.IGNORECASE)

        def print(self, *args, **kwargs):
            parts = []
            for a in args:
                parts.append(self._tag_re.sub("", str(a)))
            print(" ".join(parts), file=self._file)

    console = _PlainConsole()
    err_console = _PlainConsole(stderr=True)


# ── Helpers ──────────────────────────────────────────────────────────────

_SENSITIVE_WORDS = ("password", "secret", "token", "api_key", "apikey", "private")


def _resolve_vault(args) -> Vault:
    path = None
    if hasattr(args, "vault") and args.vault:
        path = Path(args.vault)
    return Vault(path=path)


def _vault_dir(args) -> Path:
    if hasattr(args, "vault") and args.vault:
        return Path(args.vault)
    return Path.cwd() / Vault.DEFAULT_DIR


def _is_sensitive(key: str) -> bool:
    lower = key.lower()
    return any(w in lower for w in _SENSITIVE_WORDS)


def _mask(key: str, value: str) -> str:
    if not _is_sensitive(key):
        return value
    s = str(value)
    if len(s) <= 6:
        return "••••••"
    return s[:3] + "••••" + s[-3:]


# ── Commands ─────────────────────────────────────────────────────────────


def cmd_init(args):
    vault = _resolve_vault(args)
    if vault.is_initialized:
        console.print("[yellow]Vault already exists at[/yellow] " + str(vault.vault_path))
        return
    vault.set("__init__", "true")
    vault.delete("__init__")

    if _RICH:
        console.print(Panel.fit(
            f"[bold green]✔ Vault initialised[/bold green]\n\n"
            f"  [dim]Vault:[/dim]  {vault.vault_path}\n"
            f"  [dim]Key:[/dim]    {vault._key_path}",
            title="[bold]Environment Forge[/bold]",
            border_style="green",
        ))
    else:
        console.print(f"✔ Vault initialised\n  Vault: {vault.vault_path}\n  Key:   {vault._key_path}")

    console.print("")
    console.print("[dim]Next steps:[/dim]")
    console.print("  eforge set DATABASE_HOST localhost")
    console.print("  eforge import .env")
    console.print("  eforge status")


def cmd_set(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    old = vault.get(args.key, section=section)
    vault.set(args.key, args.value, section=section)

    sec_hint = f"  [dim](section: {section})[/dim]" if section != "default" else ""
    if old is not None:
        console.print(f"[green]Updated[/green] [cyan]{args.key}[/cyan]: [dim]{old}[/dim] → {args.value}" + sec_hint)
    else:
        console.print(f"[green]Set[/green] [cyan]{args.key}[/cyan] = {args.value}" + sec_hint)


def cmd_get(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    value = vault.get(args.key, section=section)

    if value is None:
        err_console.print(f"[red]Key '{args.key}' not found[/red]")
        sys.exit(1)

    if args.raw:
        print(value)
    else:
        console.print(f"[cyan]{args.key}[/cyan] = {value}")


def cmd_delete(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    if vault.delete(args.key, section=section):
        console.print(f"[green]Deleted[/green] [cyan]{args.key}[/cyan]")
    else:
        err_console.print(f"[red]Key '{args.key}' not found[/red]")
        sys.exit(1)


def cmd_list(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    data = vault.all(section=section)

    if not data:
        console.print(f"[dim]No entries in section '{section}'.[/dim]")
        return

    if _RICH:
        table = Table(title=f"Section: {section}", box=box.ROUNDED, title_style="bold cyan", header_style="bold")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value")
        for key in sorted(data):
            display = _mask(key, str(data[key]))
            if _is_sensitive(key):
                table.add_row(key, f"[dim]{display}[/dim]")
            else:
                table.add_row(key, display)
        console.print("")
        console.print(table)
    else:
        console.print(f"\n  Section: {section}")
        console.print(f"  {'─' * 50}")
        for key in sorted(data):
            console.print(f"  {key} = {_mask(key, str(data[key]))}")

    console.print(f"\n  [bold]{len(data)}[/bold] key(s)\n")


def cmd_status(args):
    vault = _resolve_vault(args)
    schema = EnvSchema.load(_vault_dir(args))
    sections = vault.sections()

    if not sections and not schema.variables:
        console.print("[dim]Vault is empty.[/dim]")
        return

    # Build a lookup of schema vars for annotation
    schema_lookup: dict[tuple[str, str], EnvVar] = {}
    for v in schema.variables:
        schema_lookup[(v.name, v.section)] = v

    total_keys = 0
    for sec_name in sections:
        data = vault.get_section(sec_name)
        if not data:
            continue

        if _RICH:
            table = Table(title=f"Section: {sec_name}", box=box.ROUNDED, title_style="bold cyan", header_style="bold")
            table.add_column("Key", style="cyan", no_wrap=True)
            table.add_column("Value")
            table.add_column("Status", justify="center")

            for key in sorted(data):
                value = str(data[key])
                sv = schema_lookup.get((key, sec_name))
                if sv and sv.sensitive:
                    display = f"[dim]{sv.mask(value)}[/dim]"
                elif _is_sensitive(key):
                    display = f"[dim]{_mask(key, value)}[/dim]"
                else:
                    display = value
                status = "[green]●[/green]" if value else "[red]○[/red]"
                table.add_row(key, display, status)
                total_keys += 1
            console.print("")
            console.print(table)
        else:
            console.print(f"\n  Section: {sec_name}")
            console.print(f"  {'─' * 60}")
            for key in sorted(data):
                value = str(data[key])
                marker = "●" if value else "○"
                console.print(f"  {marker} {key} = {_mask(key, value)}")
                total_keys += 1

    # Show schema vars that are missing from the vault
    missing_from_vault = []
    for v in schema.variables:
        if vault.get(v.name, section=v.section) is None and v.default is None:
            missing_from_vault.append(v)

    if missing_from_vault:
        console.print("")
        console.print(f"  [red][bold]{len(missing_from_vault)} required key(s) missing:[/bold][/red]")
        for v in missing_from_vault:
            desc = f"  — {v.description}" if v.description else ""
            console.print(f"    [red]○[/red] {v.name}{desc}")

    console.print(f"\n  [bold]{total_keys}[/bold] key(s) across [bold]{len(sections)}[/bold] section(s)\n")


def cmd_sections(args):
    vault = _resolve_vault(args)
    sections = vault.sections()

    if not sections:
        console.print("[dim]No sections in vault.[/dim]")
        return

    for name in sections:
        count = len(vault.get_section(name))
        console.print(f"  [cyan]{name}[/cyan] [dim]({count} keys)[/dim]")
    console.print("")


def cmd_import(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    env_file = Path(args.file)

    if not env_file.is_file():
        err_console.print(f"[red]File not found: {env_file}[/red]")
        sys.exit(1)

    count = vault.import_env(env_file, section=section)
    console.print(f"[green]Imported[/green] [bold]{count}[/bold] key(s) from [cyan]{env_file}[/cyan] → section [cyan]{section}[/cyan]")


def cmd_export(args):
    vault = _resolve_vault(args)
    section = args.section or "default"
    output = vault.export_env(section=section)

    if not output:
        err_console.print(f"[red]Section '{section}' is empty[/red]")
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        console.print(f"[green]Exported[/green] to [cyan]{args.output}[/cyan]")
    else:
        print(output, end="")


def cmd_inject(args):
    vault = _resolve_vault(args)
    section = args.section

    data = vault.all(section=section) if section else vault.flat()

    if not data:
        err_console.print("[red]Nothing to inject[/red]")
        sys.exit(1)

    for key, value in sorted(data.items()):
        safe = str(value).replace("'", "'\\''")
        print(f"export {key}='{safe}'")


# ── Schema commands ──────────────────────────────────────────────────────


def cmd_schema(args):
    vault_dir = _vault_dir(args)
    schema = EnvSchema.load(vault_dir)

    action = args.schema_action

    if action == "add":
        cast = _CAST_MAP.get(args.type) if args.type else None
        var = EnvVar(
            name=args.key,
            required=not args.optional,
            description=args.desc or "",
            default=args.default,
            sensitive=args.sensitive,
            cast=cast,
            section=args.section or "default",
        )
        schema.add(var)
        schema.save(vault_dir)
        console.print(f"[green]Schema[/green] added [cyan]{args.key}[/cyan]"
                       + (" [dim](optional)[/dim]" if args.optional else " [bold](required)[/bold]"))
        return

    if action == "remove":
        section = args.section or "default"
        if schema.remove(args.key, section=section):
            schema.save(vault_dir)
            console.print(f"[green]Schema[/green] removed [cyan]{args.key}[/cyan]")
        else:
            err_console.print(f"[red]'{args.key}' not in schema[/red]")
            sys.exit(1)
        return

    if action == "show":
        if not schema.variables:
            console.print("[dim]No schema defined. Use:[/dim]  eforge schema add KEY --required")
            return

        if _RICH:
            table = Table(title="Environment Schema", box=box.ROUNDED, title_style="bold cyan", header_style="bold")
            table.add_column("#", style="dim", justify="right")
            table.add_column("Key", style="cyan", no_wrap=True)
            table.add_column("Required", justify="center")
            table.add_column("Type")
            table.add_column("Default")
            table.add_column("Sensitive", justify="center")
            table.add_column("Section", style="dim")
            table.add_column("Description")

            for i, v in enumerate(schema.variables, 1):
                req = "[green]✔[/green]" if v.required else "[dim]—[/dim]"
                tp = v.cast.__name__ if v.cast else "str"
                dflt = v.default or "[dim]—[/dim]"
                sens = "[yellow]🔒[/yellow]" if v.sensitive else "[dim]—[/dim]"
                sec = v.section if v.section != "default" else "[dim]default[/dim]"
                table.add_row(str(i), v.name, req, tp, dflt, sens, sec, v.description or "")
            console.print("")
            console.print(table)
        else:
            console.print("\n  Environment Schema")
            console.print(f"  {'─' * 70}")
            for i, v in enumerate(schema.variables, 1):
                req = "required" if v.required else "optional"
                tp = v.cast.__name__ if v.cast else "str"
                sens = " 🔒" if v.sensitive else ""
                console.print(f"  {i}. {v.name} ({req}, {tp}){sens}  {v.description}")

        console.print(f"\n  [bold]{len(schema)}[/bold] variable(s) defined "
                       f"([green]{len(schema.required)}[/green] required, "
                       f"[dim]{len(schema.optional)}[/dim] optional)\n")
        return

    # No sub-action given — default to show
    args.schema_action = "show"
    cmd_schema(args)


# ── Validate command ─────────────────────────────────────────────────────


def cmd_validate(args):
    vault_dir = _vault_dir(args)
    vault = _resolve_vault(args)
    schema = EnvSchema.load(vault_dir)

    if not schema.variables:
        console.print("[dim]No schema defined. Use:[/dim]  eforge schema add KEY --required")
        console.print("[dim]Or define schema in Python and call schema.save()[/dim]")
        return

    result = schema.validate(vault)

    if _RICH:
        table = Table(
            title="Validation Report",
            box=box.ROUNDED,
            title_style="bold cyan",
            header_style="bold",
        )
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Section", style="dim")
        table.add_column("Required", justify="center")
        table.add_column("Value")
        table.add_column("Status", justify="center")

        for var in schema.variables:
            raw = vault.get(var.name, section=var.section)
            req = "[bold]required[/bold]" if var.required else "[dim]optional[/dim]"
            sec = var.section if var.section != "default" else "[dim]default[/dim]"

            if raw is not None:
                display = var.mask(str(raw)) if var.sensitive else _mask(var.name, str(raw))
                if var.sensitive or _is_sensitive(var.name):
                    display = f"[dim]{display}[/dim]"
                status = "[green]✔ set[/green]"
            elif var.default is not None:
                display = f"[dim]{var.default} (default)[/dim]"
                status = "[yellow]↩ default[/yellow]"
            else:
                display = "[dim]—[/dim]"
                status = "[red]✘ missing[/red]" if var.required else "[dim]— skipped[/dim]"

            table.add_row(var.name, sec, req, display, status)

        console.print("")
        console.print(table)
    else:
        console.print("\n  Validation Report")
        console.print(f"  {'─' * 60}")
        for var in schema.variables:
            raw = vault.get(var.name, section=var.section)
            if raw is not None:
                status = "✔"
            elif var.default is not None:
                status = "↩"
            elif var.required:
                status = "✘"
            else:
                status = "—"
            console.print(f"  {status} {var.name}")

    # Errors
    if result.errors:
        console.print("")
        for e in result.errors:
            console.print(f"  [red]Error:[/red] {e}")

    # Summary
    console.print("")
    if result.valid:
        console.print("  [bold green]✔ All checks passed[/bold green]")
    else:
        n_missing = len(result.missing)
        n_errors = len(result.errors)
        parts = []
        if n_missing:
            parts.append(f"{n_missing} missing")
        if n_errors:
            parts.append(f"{n_errors} error(s)")
        console.print(f"  [bold red]✘ Validation failed:[/bold red] {', '.join(parts)}")
        console.print("")
        if result.missing:
            console.print("  [dim]Fix with:[/dim]")
            for v in result.missing:
                console.print(f"    eforge set {v.name} <value>"
                               + (f" -s {v.section}" if v.section != "default" else ""))
        sys.exit(1)
    console.print("")


def cmd_destroy(args):
    vault = _resolve_vault(args)

    if not vault.is_initialized:
        console.print("[dim]No vault found.[/dim]")
        return

    if not args.force:
        confirm = input("  Delete vault and secret key? This cannot be undone. [y/N] ").strip().lower()
        if confirm != "y":
            console.print("  Aborted.")
            return

    vault.destroy()
    console.print("[green]Vault destroyed.[/green]")


# ── Docker commands ──────────────────────────────────────────────────────


def cmd_docker_init(args):
    """Initialise a vault at the Docker volume path (/eforge)."""
    target = Path(args.path or Vault.DOCKER_VOLUME_DIR)

    if not target.exists():
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            err_console.print(f"[red]Permission denied: {target}[/red]")
            err_console.print("[dim]Make sure the Docker volume is mounted and writable.[/dim]")
            sys.exit(1)

    vault = Vault(path=target)

    if vault.is_initialized and not args.force:
        console.print(f"[yellow]Vault already exists at {target}[/yellow]")
        console.print("[dim]Use --force to reinitialise.[/dim]")
        return

    # If importing from local .eforge
    local_eforge = Path.cwd() / Vault.DEFAULT_DIR
    if args.copy_from:
        source = Path(args.copy_from)
    elif local_eforge.is_dir() and (local_eforge / Vault.VAULT_FILE).is_file():
        source = local_eforge
    else:
        source = None

    if source and source.is_dir():
        # Copy vault.enc and schema.json from source, use same or new secret
        src_vault_file = source / Vault.VAULT_FILE
        src_schema_file = source / Vault.SCHEMA_FILE
        src_key_file = source / Vault.KEY_FILE

        if src_vault_file.is_file():
            import shutil
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_vault_file, target / Vault.VAULT_FILE)
            (target / Vault.VAULT_FILE).chmod(0o600)

        if src_schema_file.is_file():
            import shutil
            shutil.copy2(src_schema_file, target / Vault.SCHEMA_FILE)

        if src_key_file.is_file():
            import shutil
            shutil.copy2(src_key_file, target / Vault.KEY_FILE)
            (target / Vault.KEY_FILE).chmod(0o600)

        if _RICH:
            console.print(Panel.fit(
                f"[bold green]✔ Docker vault initialised[/bold green]\n\n"
                f"  [dim]Source:[/dim]  {source}\n"
                f"  [dim]Target:[/dim]  {target}\n"
                f"  [dim]Files:[/dim]   vault.enc, secret.key"
                + (", schema.json" if src_schema_file.is_file() else ""),
                title="[bold]Environment Forge — Docker[/bold]",
                border_style="green",
            ))
        else:
            console.print(f"✔ Docker vault initialised\n  Source: {source}\n  Target: {target}")
    else:
        # Fresh init at target path
        vault.set("__init__", "true")
        vault.delete("__init__")

        if _RICH:
            console.print(Panel.fit(
                f"[bold green]✔ Docker vault initialised[/bold green]\n\n"
                f"  [dim]Vault:[/dim]  {vault.vault_path}\n"
                f"  [dim]Key:[/dim]    {vault._key_path}",
                title="[bold]Environment Forge — Docker[/bold]",
                border_style="green",
            ))
        else:
            console.print(f"✔ Docker vault initialised\n  Vault: {vault.vault_path}\n  Key:   {vault._key_path}")

    console.print("")
    console.print("[dim]Docker Compose example:[/dim]")
    console.print("  volumes:")
    console.print(f"    - eforge_data:{target}")
    console.print("  environment:")
    console.print("    - EFORGE_VAULT_PATH=" + str(target))
    console.print("")
    console.print("[dim]Your app loads it automatically:[/dim]")
    console.print("  import environment_forge")
    console.print("  environment_forge.load()")
    console.print("")


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--vault", "-V", help="Path to vault directory (default: .eforge in cwd)")

    parser = argparse.ArgumentParser(
        prog="eforge",
        description="Environment Forge — encrypted environment variable manager.",
        parents=[parent],
    )
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Initialise a new vault", parents=[parent])

    # set
    p_set = sub.add_parser("set", help="Set a key-value pair", parents=[parent])
    p_set.add_argument("key", help="Variable name")
    p_set.add_argument("value", help="Value to store")
    p_set.add_argument("-s", "--section", default=None, help="Section (default: default)")

    # get
    p_get = sub.add_parser("get", help="Get a value by key", parents=[parent])
    p_get.add_argument("key", help="Variable name")
    p_get.add_argument("-s", "--section", default=None, help="Section")
    p_get.add_argument("--raw", action="store_true", help="Raw value only (pipe-friendly)")

    # delete
    p_del = sub.add_parser("delete", help="Delete a key", parents=[parent])
    p_del.add_argument("key", help="Key to delete")
    p_del.add_argument("-s", "--section", default=None, help="Section")

    # list
    p_list = sub.add_parser("list", help="List all keys in a section", parents=[parent])
    p_list.add_argument("-s", "--section", default=None, help="Section")

    # status
    sub.add_parser("status", help="Show all sections and keys", parents=[parent])

    # sections
    sub.add_parser("sections", help="List section names", parents=[parent])

    # import
    p_import = sub.add_parser("import", help="Import from a .env file", parents=[parent])
    p_import.add_argument("file", help="Path to .env file")
    p_import.add_argument("-s", "--section", default=None, help="Target section")

    # export
    p_export = sub.add_parser("export", help="Export as .env format", parents=[parent])
    p_export.add_argument("-s", "--section", default=None, help="Section to export")
    p_export.add_argument("-o", "--output", help="Output file (default: stdout)")

    # inject
    p_inject = sub.add_parser("inject", help="Print shell export statements", parents=[parent])
    p_inject.add_argument("-s", "--section", default=None, help="Section (default: all)")

    # schema
    p_schema = sub.add_parser("schema", help="Manage environment schema", parents=[parent])
    schema_sub = p_schema.add_subparsers(dest="schema_action")

    p_sa = schema_sub.add_parser("add", help="Add a variable to the schema", parents=[parent])
    p_sa.add_argument("key", help="Variable name")
    p_sa.add_argument("--optional", action="store_true", help="Mark as optional (default: required)")
    p_sa.add_argument("--desc", help="Description")
    p_sa.add_argument("--type", choices=list(_CAST_MAP.keys()), help="Value type for validation")
    p_sa.add_argument("--default", help="Default value when not set")
    p_sa.add_argument("--sensitive", action="store_true", help="Mask in output (passwords, tokens)")
    p_sa.add_argument("-s", "--section", default=None, help="Section")

    p_sr = schema_sub.add_parser("remove", help="Remove a variable from the schema", parents=[parent])
    p_sr.add_argument("key", help="Variable name")
    p_sr.add_argument("-s", "--section", default=None, help="Section")

    schema_sub.add_parser("show", help="Show the full schema", parents=[parent])

    # validate
    sub.add_parser("validate", help="Validate vault against schema", parents=[parent])

    # destroy
    p_destroy = sub.add_parser("destroy", help="Delete vault and secret key", parents=[parent])
    p_destroy.add_argument("-f", "--force", action="store_true", help="Skip confirmation")

    # docker-init
    p_docker = sub.add_parser("docker-init", help="Initialise vault for Docker volume", parents=[parent])
    p_docker.add_argument("--path", default=None, help=f"Target path (default: {Vault.DOCKER_VOLUME_DIR})")
    p_docker.add_argument("--copy-from", default=None, help="Copy vault from this directory (default: auto-detect .eforge)")
    p_docker.add_argument("-f", "--force", action="store_true", help="Overwrite existing vault")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "set": cmd_set,
        "get": cmd_get,
        "delete": cmd_delete,
        "list": cmd_list,
        "status": cmd_status,
        "sections": cmd_sections,
        "import": cmd_import,
        "export": cmd_export,
        "inject": cmd_inject,
        "schema": cmd_schema,
        "validate": cmd_validate,
        "destroy": cmd_destroy,
        "docker-init": cmd_docker_init,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
