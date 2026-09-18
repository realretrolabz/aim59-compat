from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .backends import (
    DEFAULT_BUILD_TARGET,
    BackendTarget,
    WineBackendOptions,
    create_backend,
    create_wine_backend,
    select_backend_target,
)
from .backends.base import (
    DEFAULT_AIM_SERVER_HOST,
    DEFAULT_AIM_SERVER_PORT,
    AimServerSettings,
    BackendError,
    CompatibilityBackend,
    SetupConfiguration,
    SetupPresentation,
    WinePrefixBackend,
)
from .download import (
    DownloadError,
    download_direct,
    download_oldversion,
    sha256_file,
    terminal_progress,
)
from .manifest import ManifestError, load_manifest, repository_root
from .managed_prefixes import ManagedPrefix, ManagedPrefixCatalog
from .manager import InstallerChoice, ManagerOperations, TerminalManager
from .orchestration import run_doctor, run_launch, run_rollback, run_setup


class PatcherError(RuntimeError):
    pass


def default_aim_prefix_root() -> Path:
    """Return the selected AIM data directory, not the Wine child directory."""
    configured = os.environ.get("AIMwineprefix")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".local/share/rrlzAIM"


def default_prefix() -> Path:
    return default_aim_prefix_root() / "prefix"


def default_cache() -> Path:
    return Path.home() / ".cache/rrlzAIM/installers"


def default_dll() -> Path:
    adjacent_dir = Path(sys.argv[0]).expanduser().resolve().parent
    for filename in (
        "mciwave-wine9-x86-aim.dll",
        "mciwave-wine10-x86-aim.dll",
    ):
        adjacent = adjacent_dir / filename
        if adjacent.is_file():
            return adjacent
    return repository_root() / "binaries/mciwave-wine9-x86-aim.dll"


def path_value(value: str) -> Path:
    return Path(value).expanduser().resolve()


def print_banner(manifest: dict[str, Any]) -> None:
    versions = [
        value.removeprefix("wine-")
        for value in manifest["wine"]["version_prefixes"]
    ]
    print()
    print("rrlzAIMlinux")
    print(f"Target: {manifest['name']} {manifest['version']} / Wine {' or '.join(versions)}")
    print()


def _server_settings(host: str, port: int) -> AimServerSettings:
    try:
        return AimServerSettings(host, port)
    except (AttributeError, ValueError) as exc:
        raise PatcherError(str(exc)) from exc


def _prompt_server_port() -> int:
    value = input(f"Server port [{DEFAULT_AIM_SERVER_PORT}]: ").strip()
    if not value:
        return DEFAULT_AIM_SERVER_PORT
    try:
        return int(value)
    except ValueError as exc:
        raise PatcherError("Server port must be a whole number from 1 through 65535") from exc


def choose_server_settings(*, allow_keep: bool = True) -> AimServerSettings | None:
    print("AIM server:")
    print(f"  1. Use {DEFAULT_AIM_SERVER_HOST}:{DEFAULT_AIM_SERVER_PORT}")
    if allow_keep:
        print("  2. Keep AIM's existing server setting")
        print("  3. Use another server")
    else:
        print("  2. Use another server")
    choice = input("Choice [1]: ").strip() or "1"
    if choice == "1":
        return _server_settings(DEFAULT_AIM_SERVER_HOST, DEFAULT_AIM_SERVER_PORT)
    if allow_keep and choice == "2":
        return None
    if choice == ("3" if allow_keep else "2"):
        host = input("Server host: ").strip()
        return _server_settings(host, _prompt_server_port())
    raise PatcherError(f"Unknown choice: {choice}")


def resolve_server_settings(
    args: argparse.Namespace,
    *,
    prompt_if_unspecified: bool,
    allow_keep: bool = True,
) -> AimServerSettings | None:
    mode = args.server
    host = args.server_host
    port = args.server_port

    if mode is None:
        if host is not None or port is not None:
            raise PatcherError("--server-host and --server-port require --server custom")
        return (
            choose_server_settings(allow_keep=allow_keep)
            if prompt_if_unspecified
            else None
        )

    if mode == "keep":
        if host is not None or port is not None:
            raise PatcherError("--server keep cannot be combined with --server-host or --server-port")
        return None

    if mode == "realretrolabz":
        if host is not None or port is not None:
            raise PatcherError(
                "--server realretrolabz cannot be combined with --server-host or --server-port"
            )
        return _server_settings(DEFAULT_AIM_SERVER_HOST, DEFAULT_AIM_SERVER_PORT)

    if mode != "custom":
        raise PatcherError(f"Unknown AIM server mode: {mode}")
    if host is None:
        if not prompt_if_unspecified:
            raise PatcherError("--server custom requires --server-host")
        host = input("Server host: ").strip()
    if port is None:
        port = _prompt_server_port() if prompt_if_unspecified else DEFAULT_AIM_SERVER_PORT
    return _server_settings(host, port)


def resolve_setup_configuration(args: argparse.Namespace) -> SetupConfiguration:
    interactive = not args.non_interactive and not args.yes
    server = resolve_server_settings(args, prompt_if_unspecified=interactive)
    remove_aol_desktop_shortcut = args.remove_aol_desktop_shortcut
    if interactive and not remove_aol_desktop_shortcut:
        answer = input(
            "Remove 'Free AOL & Unlimited Internet' desktop shortcut after installation? [y/N]: "
        ).strip().lower()
        if answer in ("y", "yes"):
            remove_aol_desktop_shortcut = True
        elif answer not in ("", "n", "no"):
            raise PatcherError("Please answer yes or no for AOL desktop shortcut cleanup")
    return SetupConfiguration(
        server=server,
        remove_aol_desktop_shortcut=remove_aol_desktop_shortcut,
        create_xdg_launcher=not args.no_xdg_launcher,
    )


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


def wine_options_from_args(
    args: argparse.Namespace,
    *,
    prefix: Path | None = None,
) -> WineBackendOptions:
    if prefix is not None:
        resolved_prefix = prefix
    elif args.prefix and args.aim_prefix:
        raise PatcherError("--prefix cannot be combined with --aim-prefix")
    elif args.aim_prefix:
        resolved_prefix = path_value(args.aim_prefix) / "prefix"
    else:
        resolved_prefix = path_value(args.prefix) if args.prefix else default_prefix()
    patched_dll = path_value(args.patched_dll) if args.patched_dll else default_dll()
    return WineBackendOptions(
        resolved_prefix,
        patched_dll,
        auto_select_patched_dll=not bool(args.patched_dll),
        wine=args.wine,
        wineboot=args.wineboot,
        wineserver=args.wineserver,
        winetricks=args.winetricks,
        dry_run=args.dry_run,
    )


def confirm_setup(
    presentation: SetupPresentation,
    *,
    assume_yes: bool,
    non_interactive: bool,
) -> None:
    for line in presentation.confirmation_lines:
        print(line)
    if assume_yes or non_interactive:
        return
    answer = input("Continue with setup? [Y/n]: ").strip().lower()
    if answer not in ("", "y", "yes"):
        raise PatcherError("Setup cancelled")


def command_setup(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: CompatibilityBackend,
) -> int:
    print_banner(manifest)
    run_setup(
        backend,
        acquire_installer=lambda: acquire_installer(args, manifest),
        configure=lambda: backend.configure_setup(resolve_setup_configuration(args)),
        confirm=lambda presentation: confirm_setup(
            presentation,
            assume_yes=args.yes,
            non_interactive=args.non_interactive,
        ),
    )
    return 0


def command_manage(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise PatcherError(
            "The rrlzAIMlinux manager needs an interactive terminal. Use a direct subcommand instead."
        )
    if args.prefix or args.aim_prefix:
        raise PatcherError(
            "The manager selects only recorded locations. Use --prefix or --aim-prefix "
            "with a direct subcommand instead."
        )

    def backend_for(entry: ManagedPrefix) -> WinePrefixBackend:
        return create_wine_backend(
            manifest,
            wine_options_from_args(args, prefix=entry.prefix),
        )

    def install(
        root: Path,
        configuration: SetupConfiguration,
        installer_choice: InstallerChoice,
    ) -> None:
        backend = create_wine_backend(
            manifest,
            wine_options_from_args(args, prefix=root / "prefix"),
        )
        installer_args = argparse.Namespace(
            installer=installer_choice.value if installer_choice.mode == "installer" else None,
            installer_url=(
                installer_choice.value if installer_choice.mode == "installer_url" else None
            ),
            source=installer_choice.value if installer_choice.mode == "source" else None,
            non_interactive=False,
            cache_dir=args.cache_dir,
            allow_unverified=False,
            dry_run=args.dry_run,
        )
        run_setup(
            backend,
            acquire_installer=lambda: acquire_installer(installer_args, manifest),
            configure=lambda: backend.configure_setup(configuration),
            confirm=lambda _: None,
        )

    operations = ManagerOperations(
        default_root=default_aim_prefix_root,
        normalize_root=ManagedPrefixCatalog.normalize_root,
        install=install,
        backend=backend_for,
    )
    return TerminalManager(operations).run()


def command_patch_prefix(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: WinePrefixBackend,
) -> int:
    print_banner(manifest)
    backend.check_tools(require_winetricks=False)
    backend.apply()
    print("✓ Existing AIM prefix patched")
    return 0


def command_set_server(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: WinePrefixBackend,
) -> int:
    print_banner(manifest)
    backend.check_tools(require_winetricks=False)
    settings = resolve_server_settings(
        args,
        prompt_if_unspecified=not args.non_interactive,
        allow_keep=False,
    )
    if settings is None:
        raise PatcherError(
            "set-server needs realretrolabz or a custom server; 'keep' makes no change"
        )
    print("Close AIM before applying this setting.")
    backend.set_server(settings)
    print(
        "✓ AIM server setting applied. Saving AIM's own Server settings dialog can overwrite it."
    )
    return 0


def command_uninstall(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: WinePrefixBackend,
) -> int:
    print_banner(manifest)
    backend.check_tools(require_winetricks=False, enforce_version=False)
    if args.non_interactive and not (args.yes or args.dry_run):
        raise PatcherError("Noninteractive uninstall requires --yes")
    if not (args.yes or args.dry_run):
        answer = input(
            "Run AIM's uninstaller, then permanently remove this Wine prefix and "
            "the project-owned application-menu entry? [y/N]: "
        ).strip().lower()
        if answer not in ("y", "yes"):
            raise PatcherError("Uninstall cancelled")
    backend.uninstall()
    if args.dry_run:
        print("✓ AIM uninstall plan displayed")
    else:
        print("✓ AIM was uninstalled and its Wine prefix was removed")
    return 0


def command_doctor(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: CompatibilityBackend,
) -> int:
    print_banner(manifest)
    return run_doctor(backend)


def command_launch(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: CompatibilityBackend,
) -> int:
    run_launch(backend)
    return 0


def command_rollback(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    backend: CompatibilityBackend,
) -> int:
    run_rollback(backend)
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
    parser.add_argument(
        "--aim-prefix",
        help=(
            "AIM data directory; its Wine prefix is the fixed 'prefix' child "
            f"(default: {default_aim_prefix_root()})"
        ),
    )
    parser.add_argument(
        "--patched-dll",
        help="Path to the patched mciwave DLL matching the detected Wine version",
    )
    parser.add_argument("--wine", default="wine", help="Wine command")
    parser.add_argument("--wineboot", default="wineboot", help="wineboot command")
    parser.add_argument("--wineserver", default="wineserver", help="wineserver command")
    parser.add_argument("--winetricks", default="winetricks", help="Winetricks command")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing the prefix")


def add_server_arguments(
    parser: argparse.ArgumentParser,
    *,
    allow_keep: bool = True,
) -> None:
    modes = ("realretrolabz", "keep", "custom") if allow_keep else (
        "realretrolabz",
        "custom",
    )
    parser.add_argument(
        "--server",
        choices=modes,
        help=(
            "AIM server choice: realretrolabz, keep, or custom"
            if allow_keep
            else "AIM server choice: realretrolabz or custom"
        ),
    )
    parser.add_argument("--server-host", help="Custom AIM server host")
    parser.add_argument(
        "--server-port",
        type=int,
        help=f"Custom AIM server port (default: {DEFAULT_AIM_SERVER_PORT})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rrlzAIMlinux",
        description="Install and patch AIM 5.9.3861 for Wine 9.0 or 10.0",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--manifest", type=path_value, help="Alternate version manifest")
    subparsers = parser.add_subparsers(dest="command")

    manage = subparsers.add_parser("manage", help="Open the guided terminal manager")
    manage.add_argument("--cache-dir", help="Downloaded-installer cache directory")
    add_backend_arguments(manage)
    manage.set_defaults(handler=command_manage, backend_scope="manager")

    setup = subparsers.add_parser("setup", help="Create a prefix, install AIM, and apply fixes")
    source = setup.add_mutually_exclusive_group()
    source.add_argument("--installer", help="Path to a local AIM installer")
    source.add_argument("--installer-url", help="Direct AIM installer URL")
    source.add_argument("--source", choices=("oldversion",), help="Known installer source")
    setup.add_argument("--cache-dir", help="Downloaded-installer cache directory")
    setup.add_argument("--allow-unverified", action="store_true", help="Allow an unknown installer checksum")
    setup.add_argument("--yes", action="store_true", help="Accept the setup confirmation")
    setup.add_argument("--non-interactive", action="store_true", help="Disable prompts")
    setup.add_argument(
        "--no-xdg-launcher",
        action="store_true",
        help="Do not create the project-owned XDG AIM launcher",
    )
    add_server_arguments(setup)
    setup.add_argument(
        "--remove-aol-desktop-shortcut",
        action="store_true",
        help="Remove the exact optional AOL desktop shortcut after installation",
    )
    add_backend_arguments(setup)
    setup.set_defaults(handler=command_setup, backend_scope="shared")

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
    patch_prefix.set_defaults(handler=command_patch_prefix, backend_scope="wine")

    set_server = subparsers.add_parser(
        "set-server", help="Set AIM's server preference in an existing Wine prefix"
    )
    add_server_arguments(set_server, allow_keep=False)
    set_server.add_argument(
        "--non-interactive",
        action="store_true",
        help="Require --server instead of prompting",
    )
    add_backend_arguments(set_server)
    set_server.set_defaults(handler=command_set_server, backend_scope="wine")

    uninstall = subparsers.add_parser(
        "uninstall",
        help="Run AIM's uninstaller, then remove its Wine prefix",
    )
    uninstall.add_argument(
        "--yes",
        action="store_true",
        help="Confirm removal of the Wine prefix without prompting",
    )
    uninstall.add_argument(
        "--non-interactive",
        action="store_true",
        help="Require --yes unless only previewing with --dry-run",
    )
    add_backend_arguments(uninstall)
    uninstall.set_defaults(handler=command_uninstall, backend_scope="wine")

    doctor = subparsers.add_parser("doctor", help="Check an AIM Wine prefix")
    add_backend_arguments(doctor)
    doctor.set_defaults(handler=command_doctor, backend_scope="shared")

    launch = subparsers.add_parser("launch", help="Launch AIM")
    add_backend_arguments(launch)
    launch.set_defaults(handler=command_launch, backend_scope="shared")

    rollback = subparsers.add_parser("rollback", help="Restore prefix-local compatibility changes")
    add_backend_arguments(rollback)
    rollback.set_defaults(handler=command_rollback, backend_scope="shared")

    sources = subparsers.add_parser("sources", help="List known third-party installer sources")
    sources.set_defaults(handler=command_sources)

    verify = subparsers.add_parser("verify-installer", help="Verify an AIM installer")
    verify.add_argument("installer")
    verify.add_argument("--allow-unverified", action="store_true")
    verify.set_defaults(handler=command_verify_installer)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    build_target: BackendTarget | str = DEFAULT_BUILD_TARGET,
    host_platform: str | None = None,
) -> int:
    parser = build_parser()
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if not raw_arguments:
        raw_arguments = ["manage"]
    args = parser.parse_args(raw_arguments)
    try:
        manifest = load_manifest(args.manifest)
        backend_scope = getattr(args, "backend_scope", None)
        if backend_scope == "manager":
            target = select_backend_target(build_target, host_platform=host_platform)
            if target is not BackendTarget.WINE:
                raise BackendError("The rrlzAIMlinux manager is available only in the Wine build")
            return int(args.handler(args, manifest))
        if backend_scope == "shared":
            target = select_backend_target(
                build_target,
                host_platform=host_platform,
            )
            backend = create_backend(
                manifest,
                target,
                wine_options=(
                    wine_options_from_args(args)
                    if target is BackendTarget.WINE
                    else None
                ),
            )
            return int(args.handler(args, manifest, backend))
        if backend_scope == "wine":
            target = select_backend_target(
                build_target,
                host_platform=host_platform,
            )
            if target is not BackendTarget.WINE:
                raise BackendError(
                    f"{args.command} is available only in the Wine build"
                )
            backend = create_wine_backend(manifest, wine_options_from_args(args))
            return int(args.handler(args, manifest, backend))
        if getattr(args, "handler", None) is None:
            parser.print_help()
            return 2
        return int(args.handler(args, manifest))
    except (BackendError, DownloadError, ManifestError, PatcherError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
