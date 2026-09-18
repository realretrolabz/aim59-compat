# Changelog

## 0.1.4 - 2026-09-18

- Rename the project to **realretrolabz AIM Manager** and remove the Lutris
  frontend, its release assets, and its validation path. The terminal manager
  is the sole supported Linux workflow.
- Rename the Linux command to `rrlzAIMlinux` and add its centered DOS-style
  terminal manager with the supplied rrlzAIM header.
- Add catalog-only management of successful guided installations. The manager
  selects an AIM data directory whose Wine prefix is always its `prefix` child;
  it never scans for or adopts existing Wine prefixes.
- Add guided XDG-launcher choice and shortcut management, per-prefix XDG
  entries, managed-location selection, diagnostics, and confirmed uninstall.
- Lead the native Windows instructions with the verified GitHub Release EXE,
  while retaining source builds as an optional contributor workflow.
- Add guided Wine-prefix server selection and an explicit `set-server` terminal
  action for realretrolabz or a custom AIM OSCAR endpoint.
- Add a default-off Wine-prefix cleanup for the exact optional `Free AOL &
  Unlimited Internet.lnk` user/Public desktop shortcut.
- Add an explicitly confirmed Wine-prefix `uninstall` command that runs AIM's
  local uninstaller, removes the project XDG entry, and deletes the prefix only
  after AIM has actually been removed.
- Stop terminal setup before downloading an installer when the selected prefix
  already contains AIM, directing users to launch, patch, or uninstall instead.
- Revise the README with separate Linux/Wine and native Windows support,
  requirements, installation, and implementation guidance; add the project
  disclaimer and Open OSCAR Server acknowledgment.
- Confirm Wine 10.0 as runtime validated for the maintained Linux/Wine setup.

## 0.1.3 - 2026-09-15

- Add a source-only, self-contained Windows Forms setup utility.
  Its compiled EXE is intentionally not tracked or packaged.
- Port the observed Windows installer workflow into the native C# EXE:
  OldVersion/local installer acquisition and identity verification, stable-file
  completion detection, reversible `aimapi.dll` handling, and selected server
  configuration.
- Preserve `install-aim59.ps1` as archived proof-of-concept source; it is no
  longer an EXE dependency.
- Add an optional Mono cross-build command for producing the ignored EXE from a
  Linux host before transferring it to a Windows test VM.
- Add installer-free server reapplication and registered-uninstaller launch
  actions to the Windows EXE, and document AIM's observed Server-dialog
  overwrite behavior.
- Add a supplied black-and-green terminal-style banner and an explicit
  close-workflow confirmation to the Windows EXE.
- Embed the supplied multi-resolution AIM59 setup icon in the Windows EXE
  and use it for the setup window.
- Name the Windows utility **realretrolabz AIM Manager** and its
  ignored build output `rrlzAIM.exe`.
- Let **Uninstall AIM...** recognize versioned AIM registry names, unquoted
  executable paths with spaces, and a registered uninstaller in an AIM
  subdirectory.
- Restore the tool-owned `aimapi.dll` rename before **Uninstall AIM...** starts
  AIM's normal uninstaller.
- Add an unchecked opt-in cleanup for the exact `Free AOL & Unlimited
  Internet.lnk` shortcut on the current-user and Public Desktop after install.
- Prepare the self-contained Windows EXE for separate release distribution with
  a published SHA-256, while keeping all AIM files and the EXE itself out of
  Git and the Linux archive.

## 0.1.2 - 2026-09-05

- Add a Wine 10.0 source patch and build-verified PE32 `mciwave.dll` candidate.
- Select the matching Wine 9.0 or 10.0 DLL automatically in terminal bundles.
- Install a standard XDG application-menu entry and extract its icon from the
  user's installed `aim.exe` without distributing AOL artwork.
- Update the Lutris installer to consume the complete release bundle and let
  the canonical patcher select the Wine 9.0 or Wine 10.0 DLL.
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
