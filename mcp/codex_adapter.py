#!/usr/bin/env python3
"""Install and remove iCode MCP servers through the Codex CLI only."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class ServerConfig:
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    local_dir: Optional[Path] = None


NPM_PACKAGES = {
    "context7": "@upstash/context7-mcp",
    "memory": "@modelcontextprotocol/server-memory",
    "playwright": "@playwright/mcp",
    "sequential-thinking": "@modelcontextprotocol/server-sequential-thinking",
}
LOCAL_SERVERS = {
    "cheap-research": "CHEAP_RESEARCH_CONFIG",
    "vision-bridge": "VISION_BRIDGE_CONFIG",
}


def _venv_python(server_dir: Path) -> Path:
    if os.name == "nt":
        return server_dir / ".venv" / "Scripts" / "python.exe"
    return server_dir / ".venv" / "bin" / "python"


def build_catalog(root: Path) -> Dict[str, ServerConfig]:
    npx = os.environ.get("ICODEX_NPX_BIN") or shutil.which("npx") or "npx"
    catalog = {
        name: ServerConfig(name=name, command=npx, args=["-y", package])
        for name, package in NPM_PACKAGES.items()
    }
    for name, config_variable in LOCAL_SERVERS.items():
        server_dir = root / name
        catalog[name] = ServerConfig(
            name=name,
            command=str(_venv_python(server_dir)),
            args=[str(server_dir / "server.py")],
            env={config_variable: str(server_dir / "config.json")},
            local_dir=server_dir,
        )
    return catalog


def _run_codex(codex: str, arguments: Sequence[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [codex, "mcp", *arguments],
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _list_names(codex: str) -> List[str]:
    result = _run_codex(codex, ["list", "--json"], capture=True)
    if result.returncode != 0:
        raise RuntimeError(f"codex mcp list failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, list):
            raise TypeError
        return [str(item["name"]) for item in value if isinstance(item, dict) and "name" in item]
    except (json.JSONDecodeError, TypeError, KeyError) as error:
        raise RuntimeError("codex mcp list returned invalid JSON") from error


def _get_config(codex: str, name: str) -> Mapping[str, object]:
    result = _run_codex(codex, ["get", name, "--json"], capture=True)
    if result.returncode != 0:
        raise RuntimeError(f"codex mcp get {name} failed: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError(f"codex mcp get {name} returned invalid JSON") from error


def _canonical_command(command: object) -> object:
    if not isinstance(command, str) or not command:
        return command
    expanded = Path(command).expanduser()
    if expanded.is_absolute() or len(expanded.parts) > 1:
        return str(expanded.resolve())
    resolved = shutil.which(command)
    return str(Path(resolved).resolve()) if resolved else command


def _normalized_transport(config: Mapping[str, object]) -> Dict[str, object]:
    transport = config.get("transport")
    if not isinstance(transport, dict):
        return {"type": None, "command": None, "args": None, "cwd": None, "env": None}
    cwd = transport.get("cwd") or None
    if isinstance(cwd, str):
        cwd = str(Path(cwd).expanduser().resolve())
    return {
        "type": transport.get("type"),
        "command": _canonical_command(transport.get("command")),
        "args": transport.get("args"),
        "cwd": cwd,
        "env": transport.get("env") or None,
    }


def _desired_transport(desired: ServerConfig) -> Dict[str, object]:
    return {
        "type": "stdio",
        "command": _canonical_command(desired.command),
        "args": desired.args,
        "cwd": None,
        "env": desired.env or None,
    }


def _redact_transport(config: Mapping[str, object]) -> Dict[str, object]:
    redacted = dict(config)
    env = redacted.get("env")
    if isinstance(env, dict):
        redacted["env"] = {str(key): "<redacted>" for key in sorted(env)}
    return redacted


def _same_config(existing: Mapping[str, object], desired: ServerConfig) -> bool:
    return _normalized_transport(existing) == _desired_transport(desired)


def _prepare_local_server(config: ServerConfig) -> None:
    assert config.local_dir is not None
    server_dir = config.local_dir
    if not (server_dir / "server.py").is_file() or not (server_dir / "requirements.txt").is_file():
        raise RuntimeError(f"local MCP source is incomplete: {server_dir}")
    python = os.environ.get("ICODEX_PYTHON_BIN") or sys.executable
    venv_python = Path(config.command)
    if not venv_python.is_file():
        subprocess.run([python, "-m", "venv", str(server_dir / ".venv")], check=True)
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(server_dir / "requirements.txt")],
        check=True,
    )
    config_path = server_dir / "config.json"
    example = server_dir / "config.example.json"
    if not config_path.exists() and example.is_file():
        shutil.copyfile(example, config_path)


def install(root: Path, names: Sequence[str], dry_run: bool, auto_install: bool) -> int:
    codex = os.environ.get("ICODEX_CODEX_BIN") or "codex"
    catalog = build_catalog(root)
    selected = list(names) if names else list(catalog)
    unknown = [name for name in selected if name not in catalog]
    if unknown:
        print("Unknown MCP server(s): " + ", ".join(unknown), file=sys.stderr)
        return 1

    existing_names = set(_list_names(codex))
    identical = set()
    conflicts: Dict[str, Dict[str, object]] = {}
    for name in selected:
        if name not in existing_names:
            continue
        existing = _get_config(codex, name)
        if _same_config(existing, catalog[name]):
            identical.add(name)
        else:
            conflicts[name] = {
                "existing": _redact_transport(_normalized_transport(existing)),
                "candidate": _redact_transport(_desired_transport(catalog[name])),
            }
    if conflicts:
        print("Refusing to replace different Codex MCP configuration(s):", file=sys.stderr)
        print(json.dumps(conflicts, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2

    failures = []
    for name in selected:
        config = catalog[name]
        if name in identical:
            print(f"SKIP {name}: identical Codex configuration")
            continue
        if dry_run:
            print(f"DRY-RUN add {name}: {config.command} {' '.join(config.args)}")
            continue
        try:
            if config.local_dir is not None:
                if auto_install:
                    _prepare_local_server(config)
                elif not Path(config.command).is_file():
                    raise RuntimeError(f"{name} dependencies are absent; rerun without --no-auto-install")
            arguments = ["add", name]
            for key, value in sorted((config.env or {}).items()):
                arguments.extend(["--env", f"{key}={value}"])
            arguments.extend(["--", config.command, *config.args])
            result = _run_codex(codex, arguments)
            if result.returncode != 0:
                raise RuntimeError(f"codex mcp add exited {result.returncode}")
            print(f"ADDED {name}")
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            failures.append(name)
            print(f"FAILED {name}: {error}", file=sys.stderr)
    return 1 if failures else 0


def uninstall(root: Path, names: Sequence[str], dry_run: bool, assume_yes: bool) -> int:
    codex = os.environ.get("ICODEX_CODEX_BIN") or "codex"
    catalog = build_catalog(root)
    selected = list(names) if names else list(catalog)
    unknown = [name for name in selected if name not in catalog]
    if unknown:
        print("Unknown MCP server(s): " + ", ".join(unknown), file=sys.stderr)
        return 1
    existing = set(_list_names(codex))
    selected = [name for name in selected if name in existing]
    if not selected:
        print("No selected iCode MCP servers are registered")
        return 0
    if not dry_run and not assume_yes:
        if not sys.stdin.isatty():
            print("Refusing non-interactive removal without --yes", file=sys.stderr)
            return 1
        answer = input("Remove " + ", ".join(selected) + " from Codex? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            return 1
    failures = []
    for name in selected:
        if dry_run:
            print(f"DRY-RUN remove {name}")
            continue
        result = _run_codex(codex, ["remove", name])
        if result.returncode != 0:
            failures.append(name)
            print(f"FAILED {name}: codex mcp remove exited {result.returncode}", file=sys.stderr)
        else:
            print(f"REMOVED {name}")
    return 1 if failures else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-auto-install", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("names", nargs="*")
    parse = getattr(parser, "parse_intermixed_args", parser.parse_args)
    args = parse(argv)
    root = Path(__file__).resolve().parent
    if args.action == "install":
        return install(root, args.names, args.dry_run, not args.no_auto_install)
    return uninstall(root, args.names, args.dry_run, args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
