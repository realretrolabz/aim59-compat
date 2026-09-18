# Historical native Windows investigation handoff

> Historical record. This document preserves the staged discovery and
> PowerShell-prototype history through Stage 4. The active native Windows
> implementation is the self-contained C# `rrlzAIM.exe` source described in
> [WINDOWS_EXE_HANDOFF.md](WINDOWS_EXE_HANDOFF.md) and
> [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md). It does not use the archived
> PowerShell script at runtime.

Status updated on 2026-09-13. The released Linux/Wine implementation is
`v0.1.1` at commit `29a8e03`; its Lutris installer has been submitted for
review. Native Windows support remains planned and must not be advertised as
working until it has passed the applicable clean-system gates. Windows 11 is
the initial target; Windows 10 remains a separate later validation target.

## Goal

Add a native Windows compatibility backend for AIM 5.9.3861 while keeping one
terminal-first patcher. Prefer a truly portable Windows 11 workflow: no AIM or
tool installation and no AIM/project-specific entries written to the host
registry, including temporary entries. If testing proves that impossible, an
accepted fallback is to modify a normal AIM installation performed by the
user. The fallback must not be called portable.

The existing installer acquisition and identity verification should be
shared. Native Windows must not receive Wine-only files, registry values, or
support assumptions.

The repository and release assets must continue to exclude all AOL/AIM
binaries. Downloads must go to a user cache and the known installer must match
the SHA-256 pinned in `manifests/aim-5.9.3861.json` before execution.

## What exists now

- `rrlzAIM/download.py` resolves local files, direct HTTP(S) URLs, and
  the OldVersion form download.
- `rrlzAIM/cli.py` owns source selection, verification, and every command,
  but currently constructs `WineBackend` directly.
- `rrlzAIM/backends/wine.py` owns all prefix creation, Wine checks,
  installation, patching, diagnostics, launch, and rollback behavior.
- The version manifest mixes shared installer identity with a `wine` section
  and the Wine-only patched `mciwave.dll` identity.
- The zip application and Linux tarball are Linux-oriented distributions. The
  `.pyz` may run under a suitable Windows Python, but it is not yet a supported
  Windows package or a friendly Windows installer.

## Reuse boundary

Share these parts across platforms:

- AIM version and installer filename, size, and accepted SHA-256
- source selection and third-party download resolution
- external cache policy
- installer verification and error reporting
- high-level setup, doctor, launch, and rollback concepts
- dry-run/noninteractive behavior where each platform can implement it safely

Keep these Wine-only:

- Wine 9.0 validation and `WINEPREFIX`/`WINEARCH`
- Winetricks `winxp mfc40`
- the patched Wine `mciwave.dll`, its marker, and DLL override
- Wine MCI/MCI32 registry mappings and prefix `system.ini`
- Wine prefix paths, `wineserver`, and Wine launch commands

Do not assume that registering `sb.dll`, disabling `aimapi.dll`, installing a
legacy runtime, or applying an audio fix is required on native Windows. Each
operation must be confirmed on a Windows version before support for that
version is claimed. In particular, never copy the patched Wine `mciwave.dll`
into native Windows.

## Required user experience

The Windows 11 release gate requires sign-in/sign-out against the configured
Open OSCAR environment, buddy list and presence, IM send/receive, chat rooms,
buddy icons, repeated notification sounds, profiles and away messages, and
state persistence across exit/relaunch. At least 20 notification events must
complete without hanging AIM. Release testing requires an Open OSCAR server
known to provide the network-dependent core features; missing server support
leaves the corresponding gate untested rather than turning it into a pass.

Stock ticker and other panels backed by retired AIM/AOL services are not
blockers. Direct Connection and file transfer remain network-dependent. Test
reports must distinguish client failures from features absent on the selected
Open OSCAR server.

## Recommended implementation sequence

### 1. Refactor without changing Wine behavior

Introduce a small backend interface or protocol for setup, doctor, launch, and
rollback. Select the backend safely from the build target and host. An
explicit backend override may exist for tests or source-tree development, but
ordinary release users should not need to choose one. Move Wine-specific
arguments and defaults behind the Wine choice.

Keep the existing Wine command behavior and tests passing exactly. Split the
manifest only as far as needed to make shared installer metadata independent
of platform-specific requirements.

### 2. Perform Windows discovery before writing patches

Use a clean, disposable 64-bit Windows 11 VM first. Windows 10 validation is a
later independent gate. For the exact pinned AIM installer, record:

- whether installation and launch require elevation
- the actual install directory and relevant registry entries
- whether `mfc40` is installed or already available
- whether `sb.dll` registration is needed and which 32-bit `regsvr32` is used
- whether `aimapi.dll` causes a real failure
- whether repeated notification sounds work with native Windows MCI
- process shutdown/relaunch behavior
- behavior of every required experience listed above
- uninstall behavior and every file/registry mutation the patcher may need to
  reverse
- whether extraction and launch can avoid all AIM/project-specific host
  registry entries, and whether the resulting directory remains relocatable

Do not treat Wine observations as evidence for native Windows.

### 3. Implement the smallest evidence-backed Windows backend

Stage 5 must explicitly choose strict portable mode or installed fallback
before `rrlzAIM/backends/windows.py` is added. A temporary registry
import/export transaction does not qualify as portable. Implement only the
selected mode and operations supported by discovery. Make every tool-owned
mutation idempotent, back it up before changing it, record platform-specific
state, and implement rollback alongside apply. Use Windows-native APIs and,
for installed mode, the correct 32-bit registry view; do not model the
installation as a Wine prefix.

Add unit tests with mocked filesystem/process/registry boundaries. Run final
integration tests on clean Windows 11, including a second apply, doctor,
rollback, and the relocation or reinstall tests applicable to the selected
mode. Validate Windows 10 separately before claiming it.

### 4. Package Windows separately

Produce a Windows-specific release artifact that does not require users to
install Python. Name it `AIM59Portable` only if strict portability passed;
otherwise use an installed-compatibility name. Keep the Linux tarball and
Lutris assets unchanged. The Windows artifact should contain the patcher code,
licenses, documentation, and checksums, but no AIM installer and no patched
Wine DLL. Add a Windows CI job to build and test it reproducibly; code signing
can remain a documented future improvement if no certificate is available.

## First-thread milestone

Stage 0 established the strict portable definition, its installed fallback,
the Windows 11-first target, and the core-experience release gate. The next
milestone is an architecture-only change that introduces backend selection
and preserves all v0.1.1 Wine behavior, followed by a read-only Windows
discovery/probe plan. Do not implement speculative native Windows fixes in
that milestone.

The staged execution plan, release-target clarification, exit gates, and
copy-ready prompts for future threads are in
[`WINDOWS_ROADMAP.md`](WINDOWS_ROADMAP.md). Where the earlier backend-selection
wording is ambiguous, the roadmap's separate Linux and Windows build-target
model controls.

Before any commit, follow `AGENTS.md`: run `make verify`, inspect the complete
diff, and confirm that no installer, installed AIM file, cache file, or other
proprietary binary entered the repository or Git history.

## Stage 0 handoff

```text
Stage completed: Stage 0 - scope, definitions, and roadmap
Approval status: Approved by the project owner on 2026-09-02
Repository commit or working-tree state: Committed with the Stage 1 change set
  in ba86ede
Tests run and results: make verify passed on 2026-09-02
Windows environment, if used: None
External evidence location: None
Sanitized findings added: None; no Windows behavior has been tested yet
Decisions made: Windows 11 first; strict no-install/no-AIM-registry portable
  mode preferred; normal user install accepted as a non-portable fallback;
  Stage 0 core experience is release-blocking
Known failures or unanswered questions: Portable feasibility, stock Windows
  behavior, necessary native fixes, and Open OSCAR test-server capabilities
  remain untested
Proprietary/private data check: Repository guard passed; no AIM binaries or
  private Windows evidence added
Exact next stage: Stage 1 - backend architecture without behavior changes
Recommended prompt for the next thread: See below
```

## Stage 1 handoff

```text
Stage completed: Stage 1 - backend architecture without behavior changes
Approval status: Approved by the project owner on 2026-09-02
Repository commit or working-tree state: Implementation committed in ba86ede;
  this approval record is a documentation-only follow-up
Tests run and results: make verify passed on 2026-09-02; 20 Python tests
  passed, including build-target selection, mismatch rejection, shared setup
  sequencing, Wine-specific patch-prefix dispatch, and acquisition isolation
Windows environment, if used: None
External evidence location: None
Sanitized findings added: None; Stage 1 made no Windows behavior claims
Decisions made: Release artifacts select their target internally; the current
  target remains Wine; no public backend selector was added; patch-prefix
  remains Wine-only; the existing manifest was not migrated
Known failures or unanswered questions: The native Windows backend remains
  unimplemented; stock Windows 11 behavior, portable feasibility, necessary
  fixes, and Open OSCAR test-server capabilities remain untested
Proprietary/private data check: Repository guard passed; no AIM binaries or
  private Windows evidence added
Exact next stage: Stage 2 - Windows discovery kit
Recommended prompt for the next thread: Use the Stage 2 next-thread prompt in
  docs/WINDOWS_ROADMAP.md
```

## Stage 2 handoff

```text
Stage completed: Stage 2 implementation - Windows discovery kit
Approval status: Approved by the project owner on 2026-09-09
Repository commit or working-tree state: Discovery collector, operator guide,
  static tests, and inventory updates are present in the working tree; no
  Windows compatibility backend or fix was added
Tests run and results: 36 Linux Python tests passed, including eight collector
  safety/static checks. make verify reached the release-package check but did
  not pass: the current source-built 0.1.2 archive checksum differs from the
  checksum pinned for the already-published Lutris asset. A clean HEAD archive
  reproduces the same pre-existing mismatch; this Stage 2 change did not alter
  the published release or its checksum declaration.
Windows environment, if used: Dedicated clean Windows 11 Pro build 26200 VM,
  x64 and elevated. An initial 00-clean collection was partial because the
  collector mistook Windows Usb.dll for AIM's sb.dll; the filter was corrected
  and must be rerun to obtain the valid baseline.
External evidence location: Private external evidence volume; it remains
  outside Git
Sanitized findings added: None; no Windows behavior has been observed
Decisions made: The collector requires an explicit, empty output directory;
  records Registry64 and Registry32 views explicitly; captures targeted
  metadata only; and supplies stable checkpoint comparisons. Stage 3 uses the
  clean VM sequence in docs/WINDOWS_DISCOVERY.md without compatibility changes.
Known failures or unanswered questions: A valid 00-clean snapshot is pending
  after the collector correction. Clean Windows 11 installation and launch
  behavior, required native changes, portable feasibility, and Open OSCAR
  test-server capabilities remain untested
Proprietary/private data check: The focused repository artifact check found no
  AIM binary, installer, raw Windows evidence, or private test data. The full
  verifier's later guard was not reached because its release-package check
  stops first.
Exact next stage: Resolve the pre-existing release-package verification policy
  or metadata mismatch, then begin Stage 3 - Windows 11 baseline discovery
Recommended prompt for the next thread: See below, after the validation issue
  is resolved or explicitly accepted
```

## Stage 3 handoff

```text
Stage completed: Stage 3 - Windows 11 baseline discovery
Approval status: The project owner approved private clean-VM execution on
  2026-09-10 after accepting the separate release-reproducibility follow-up
Repository commit or working-tree state: Sanitized findings, the Stage 3
  handoff, and the Stage 4 proposal gate are present in the working tree. No
  native Windows backend or compatibility fix was added.
Tests run and results: 37 Linux Python tests passed, including the discovery
  kit's safety and sanitized-findings checks. make verify remains blocked at
  its known release-package checksum comparison: rebuilding source does not
  reproduce the frozen v0.1.2 release asset checksum. The published Lutris
  checksum was intentionally left unchanged.
Windows environment, if used: Dedicated clean Windows 11 Pro build 26200 VM,
  x64 and elevated; the powered-off Pre-AIM disk-only snapshot was restored
  before the authoritative baseline. The separate evidence disk was outside
  the system-disk snapshot chain.
External evidence location: Private evidence volume outside Git, containing
  the five authoritative checkpoints, four comparisons, and private operator
  notes. Earlier partial/misordered runs are retained separately and were not
  used for conclusions.
Sanitized findings added: docs/WINDOWS_FINDINGS.md
Decisions made: Stock first launch leaves aim.exe running without a visible
  GUI. No required core feature was reachable. The forced process termination
  is recorded as such. Installer-created COM and AppCompat state are
  observations only, not proven fixes. Stage 4 is gated on an explicit
  one-variable proposal.
Known failures or unanswered questions: The cause of the invisible GUI;
  whether any candidate compatibility operation is required; normal AIM exit;
  all core online/sound features; strict portability; and the release-build
  reproducibility follow-up remain unresolved.
Proprietary/private data check: No AIM binary, installer, raw Windows output,
  user path, screen name, server address, or private notes were added to Git.
Exact next stage: Stage 4 - gated proposal for controlled native compatibility
  experiments
Recommended prompt for the next thread: See below
```

## Stage 4 prototype handoff

```text
Stage completed: Stage 4 initial launch-workaround isolation
Approval status: The project owner approved the one-variable aimapi.dll test
  and then selected an installed Windows workflow for the current prototype
Repository commit or working-tree state: Windows installed backend script,
  PowerShell Forms prototype, documentation, and static tests are present in
  the working tree; no AIM file or compiled Windows executable is present
Tests run and results: 40 Linux tests passed. make verify reaches the existing
  frozen Lutris release-package checksum mismatch after shell/YAML/Python
  validation; that mismatch predates this Windows work.
Windows environment, if used: Dedicated Windows 11 VM. Normal installation
  followed by disabling aimapi.dll produced a visible usable AIM window.
External evidence location: Private VM/evidence storage outside Git.
Sanitized findings added: docs/WINDOWS_FINDINGS.md and docs/WINDOWS_INSTALL.md
Decisions made: aimapi.dll disabling is the smallest observed launch workaround
  for this VM. No XP compatibility, sb.dll, native MCI, or Wine change is in
  the installed script. The tool supports an OldVersion download or a verified
  local installer and configurable AIM server settings. The source GUI delegates
  entirely to the script backend.
Known failures or unanswered questions: Windows runtime validation of the
  scripts, full AIM core-feature/recovery tests, Windows 10, compiled EXE
  packaging, and release-build reproducibility remain open.
Proprietary/private data check: No AIM binary, installer, raw evidence,
  screen name, or personal path was added to Git.
Exact next stage: Implement and validate an EXE front end that delegates to the
  canonical PowerShell backend; see docs/WINDOWS_EXE_HANDOFF.md.
```

## Suggested prompt for the next thread

The Stage 4 record above is historical. The current C# follow-up replaced the
PowerShell Forms prototype and the thin-EXE design with source-only,
self-contained `rrlzAIM.exe` build inputs. The archived script remains
historical evidence, not an EXE dependency. See
[`WINDOWS_EXE_HANDOFF.md`](WINDOWS_EXE_HANDOFF.md) for current implementation
status and [`WINDOWS_INSTALL.md`](WINDOWS_INSTALL.md) for the pending Pre-AIM
native-EXE test plan.
