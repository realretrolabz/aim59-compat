# Changelog

## 0.1.1 - Unreleased

- Add a first-class terminal release archive runnable as `./aim59 setup`.
- Discover the release-bundled patched DLL beside the terminal launcher.
- Package licenses, documentation, checksums, and Wine corresponding-source
  materials with the terminal distribution.
- Keep Lutris as a separate frontend using the same canonical patcher engine.

## 0.1.0 - 2026-08-31

Initial project scaffold.

- Target AIM 5.9.3861 on Wine 9.0 in a 32-bit prefix.
- Include validated AIM notification-sound fix for Wine 9.0 `mciwave`.
- Include a GitHub Release-backed Lutris installer.
- Include build, verification, rollback, and repository-safety scripts.
- Add a manifest-driven terminal setup, diagnostic, launch, and rollback CLI.
- Add verified local, direct-URL, and OldVersion installer acquisition.
- Make Lutris and legacy shell entry points delegate to the canonical CLI.
- Do not distribute AOL/AIM binaries.
