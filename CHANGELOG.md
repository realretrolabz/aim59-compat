# Changelog

## Unreleased

- Add a Wine 10.0 source patch and build-verified PE32 `mciwave.dll` candidate.
- Select the matching Wine 9.0 or 10.0 DLL automatically in terminal bundles.
- Install a standard XDG application-menu entry and extract its icon from the
  user's installed `aim.exe` without distributing AOL artwork.
- Keep the published v0.1.1 Lutris installer pinned to its Wine 9.0 DLL until
  a version containing both DLLs is released and Wine 10 runtime testing is
  complete.
- Separate shared setup, doctor, launch, and rollback orchestration from the
  Wine backend without changing the Linux or Lutris command surface.
- Add internal build-target/host validation and reject platform mismatches.

## 0.1.1 - 2026-08-31

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
