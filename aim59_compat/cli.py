from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .backends.wine import BackendError, WineBackend
from .download import (
    DownloadError,
    download_direct,
    download_oldversion,
    sha256_file,
    terminal_progress,
)
from .manifest import ManifestError, load_manifest, repository_root


class PatcherError(RuntimeError):
    pass


def default_prefix() -> Path:
    return Path.home() / ".local/share/aim59-compat/prefix"


def default_cache() -> Path:
    return Path.home() / ".cache/aim59-compat/installers"


def default_dll() -> Path:
    adjacent = (
        Path(sys.argv[0]).expanduser().resolve().parent
        / "mciwave-wine9-x86-aim.dll"
    )
    if adjacent.is_file():
        return adjacent
    return repository_root() / "binaries/mciwave-wine9-x86-aim.dll"


def path_value(value: str) -> Path:
    return Path(value).expanduser().resolve()


def print_banner(manifest: dict[str, Any]) -> None:
    print()
    print("AIM 5.9 Compatibility Patcher")
    print(f"Target: {manifest['name']} {manifest['version']} / Wine 9.0")
    print()


def choose_installer_source(manifest: dict[str, Any]) -> tuple[str, str]:
    source = manifest["installer"]["sources"]["oldversion"]
    print("Installer source:")
    print(f"  1. Download from {source['name']} (third-party archive)")
    print("  2. Select a local installer")
    print("  3. Enter a direct download URL")
    choice = input("Choice [1]: ").strip() or "1"
    if choice == "1":
        return "source", "oldversion"
    if choice == "2":
        value = input("Path to aim593861.exe: ").strip()
        if not value:
            raise PatcherError("No installer path supplied")
        return "path", value
    if choice == "3":
        value = input("Installer URL: ").strip()
        if not value:
            raise PatcherError("No installer URL supplied")
        return "url", value
    raise PatcherError(f"Unknown choice: {choice}")


def verify_installer(
    path: Path,
    manifest: dict[str, Any],
    *,
    allow_unverified: bool,
) -> str:
    if not path.is_file():
        raise PatcherError(f"Installer not found: {path}")
    digest = sha256_file(path)
    accepted = set(manifest["installer"]["sha256"])
    if digest not in accepted and not allow_unverified:
        raise PatcherError(
            "Installer checksum is not recognized.\n"
            f"Expected one of: {', '.join(sorted(accepted))}\n"
            f"Received:        {digest}\n"
            "Use --allow-unverified only after independently confirming the file."
        )
    expected_size = manifest["installer"].get("size")
    if digest in accepted and expected_size and path.stat().st_size != expected_size:
        raise PatcherError("Installer size does not match its manifest")
    return digest


def acquire_installer(args: argparse.Namespace, manifest: dict[str, Any]) -> Path:
    mode: str | None = None
    value: str | None = None
    if args.installer:
        mode, value = "path", args.installer
    elif args.installer_url:
        mode, value = "url", args.installer_url
    elif args.source:
        mode, value = "source", args.source
    elif args.non_interactive:
        raise PatcherError(
            "Noninteractive setup requires --installer, --installer-url, or --source"
        )
    else:
        mode, value = choose_installer_source(manifest)

    if mode == "path":
        installer = path_value(value or "")
        digest = verify_installer(
            installer, manifest, allow_unverified=args.allow_unverified
        )
        print(f"✓ Installer verified: {digest}")
        return installer

    cache = path_value(args.cache_dir) if args.cache_dir else default_cache()
    installer = cache / manifest["installer"]["filename"]
    if installer.is_file():
        try:
            digest = verify_installer(installer, manifest, allow_unverified=False)
            print(f"✓ Using verified cached installer: {installer}")
            return installer
        except PatcherError:
            if not args.dry_run:
                installer.unlink()

    if args.dry_run:
        print(f"→ Would download installer to {installer}")
        return installer

    if mode == "url":
        print(f"→ Downloading user-supplied URL to {installer}")
        download_direct(value or "", installer, terminal_progress)
    else:
        source = manifest["installer"]["sources"].get(value or "")
        if not source:
            raise PatcherError(f"Unknown installer source: {value}")
        if source["kind"] != "oldversion-form":
            raise PatcherError(f"Unsupported source resolver: {source['kind']}")
        print(f"→ Downloading from {source['name']} (unaffiliated third party)")
        download_oldversion(source["page_url"], installer, terminal_progress)
    if sys.stderr.isatty():
        print(file=sys.stderr)
    digest = verify_installer(installer, manifest, allow_unverified=args.allow_unverified)
    print(f"✓ Installer verified: {digest}")
    return installer


def backend_from_args(args: argparse.Namespace, manifest: dict[str, Any]) -> WineBackend:
    prefix = path_value(args.prefix) if args.prefix else default_prefix()
    patched_dll = path_value(args.patched_dll) if args.patched_dll else default_dll()
    return WineBackend(
        manifest,
        prefix,
        patched_dll,
        wine=args.wine,
        wineboot=args.wineboot,
        wineserver=args.wineserver,
        winetricks=args.winetricks,
        dry_run=args.dry_run,
    )


def confirm_setup(backend: WineBackend, *, assume_yes: bool, non_interactive: bool) -> None:
    print(f"Wine prefix: {backend.prefix}")
    print(f"Patched DLL: {backend.patched_dll}")
    if assume_yes or non_interactive:
        return
    answer = input("Continue with setup? [Y/n]: ").strip().lower()
    if answer not in ("", "y", "yes"):
        raise PatcherError("Setup cancelled")


def command_setup(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    print_banner(manifest)
    backend = backend_from_args(args, manifest)
    backend.check_tools(require_winetricks=True, require_wineboot=True)
    backend.verify_patched_dll()
    installer = acquire_installer(args, manifest)
    confirm_setup(backend, assume_yes=args.yes, non_interactive=args.non_interactive)
    backend.create_prefix()
    backend.install_prerequisites()
    backend.install_aim(installer)
    backend.apply()
    print()
    print("✓ AIM compatibility setup completed")
    print(f"  Run: aim59 launch --prefix {backend.prefix}")
    return 0


def command_patch_prefix(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    print_banner(manifest)
    backend = backend_from_args(args, manifest)
    backend.check_tools(require_winetricks=False)
    backend.apply()
    print("✓ Existing AIM prefix patched")
    return 0


def command_doctor(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    print_banner(manifest)
    backend = backend_from_args(args, manifest)
    failed = False
    for passed, message in backend.doctor():
        print(("✓" if passed else "✗") + " " + message)
        failed = failed or not passed
    return 1 if failed else 0


def command_launch(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    backend = backend_from_args(args, manifest)
    backend.check_tools(require_winetricks=False)
    backend.launch()
    return 0


def command_rollback(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    backend = backend_from_args(args, manifest)
    backend.check_tools(require_winetricks=False, enforce_version=False)
    backend.rollback()
    print("✓ Compatibility rollback completed")
    return 0


def command_sources(_: argparse.Namespace, manifest: dict[str, Any]) -> int:
    print(f"Known sources for AIM {manifest['version']}:")
    for source_id, source in manifest["installer"]["sources"].items():
        print(f"  {source_id:12} {source['name']}")
        print(f"               {source['page_url']}")
    print("Sources are unaffiliated third parties; downloaded bytes are hash-verified.")
    return 0


def command_fetch(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    print_banner(manifest)
    installer = acquire_installer(args, manifest)
    print(f"✓ Installer ready: {installer}")
    return 0


def command_verify_installer(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    installer = path_value(args.installer)
    digest = verify_installer(
        installer, manifest, allow_unverified=args.allow_unverified
    )
    print(f"✓ AIM {manifest['version']} installer: {digest}")
    return 0


def add_backend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prefix", help=f"Wine prefix (default: {default_prefix()})")
    parser.add_argument("--patched-dll", help="Path to patched Wine 9.0 mciwave DLL")
    parser.add_argument("--wine", default="wine", help="Wine command")
    parser.add_argument("--wineboot", default="wineboot", help="wineboot command")
    parser.add_argument("--wineserver", default="wineserver", help="wineserver command")
    parser.add_argument("--winetricks", default="winetricks", help="Winetricks command")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing the prefix")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aim59",
        description="Install and patch AIM 5.9.3861 for Wine 9.0",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--manifest", type=path_value, help="Alternate version manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="Create a prefix, install AIM, and apply fixes")
    source = setup.add_mutually_exclusive_group()
    source.add_argument("--installer", help="Path to a local AIM installer")
    source.add_argument("--installer-url", help="Direct AIM installer URL")
    source.add_argument("--source", choices=("oldversion",), help="Known installer source")
    setup.add_argument("--cache-dir", help="Downloaded-installer cache directory")
    setup.add_argument("--allow-unverified", action="store_true", help="Allow an unknown installer checksum")
    setup.add_argument("--yes", action="store_true", help="Accept the setup confirmation")
    setup.add_argument("--non-interactive", action="store_true", help="Disable prompts")
    add_backend_arguments(setup)
    setup.set_defaults(handler=command_setup)

    fetch = subparsers.add_parser("fetch", help="Acquire and verify the AIM installer")
    fetch_source = fetch.add_mutually_exclusive_group(required=True)
    fetch_source.add_argument("--installer", help="Path to a local AIM installer")
    fetch_source.add_argument("--installer-url", help="Direct AIM installer URL")
    fetch_source.add_argument("--source", choices=("oldversion",), help="Known installer source")
    fetch.add_argument("--cache-dir", help="Downloaded-installer cache directory")
    fetch.add_argument("--allow-unverified", action="store_true")
    fetch.add_argument("--non-interactive", action="store_true", default=True, help=argparse.SUPPRESS)
    fetch.add_argument("--dry-run", action="store_true")
    fetch.set_defaults(handler=command_fetch)

    patch_prefix = subparsers.add_parser(
        "patch-prefix", help="Apply fixes to an existing AIM Wine prefix"
    )
    patch_prefix.add_argument("--non-interactive", action="store_true", help=argparse.SUPPRESS)
    add_backend_arguments(patch_prefix)
    patch_prefix.set_defaults(handler=command_patch_prefix)

    doctor = subparsers.add_parser("doctor", help="Check an AIM Wine prefix")
    add_backend_arguments(doctor)
    doctor.set_defaults(handler=command_doctor)

    launch = subparsers.add_parser("launch", help="Launch AIM")
    add_backend_arguments(launch)
    launch.set_defaults(handler=command_launch)

    rollback = subparsers.add_parser("rollback", help="Restore prefix-local compatibility changes")
    add_backend_arguments(rollback)
    rollback.set_defaults(handler=command_rollback)

    sources = subparsers.add_parser("sources", help="List known third-party installer sources")
    sources.set_defaults(handler=command_sources)

    verify = subparsers.add_parser("verify-installer", help="Verify an AIM installer")
    verify.add_argument("installer")
    verify.add_argument("--allow-unverified", action="store_true")
    verify.set_defaults(handler=command_verify_installer)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        return int(args.handler(args, manifest))
    except (BackendError, DownloadError, ManifestError, PatcherError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
