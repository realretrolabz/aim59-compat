# Native Windows backend handoff

Status updated on 2026-09-02. The released Linux/Wine implementation is
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

- `aim59_compat/download.py` resolves local files, direct HTTP(S) URLs, and
  the OldVersion form download.
- `aim59_compat/cli.py` owns source selection, verification, and every command,
  but currently constructs `WineBackend` directly.
- `aim59_compat/backends/wine.py` owns all prefix creation, Wine checks,
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
before `aim59_compat/backends/windows.py` is added. A temporary registry
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

## Suggested prompt for the next thread

> Read the project instructions and Stage 2 of
> `docs/WINDOWS_ROADMAP.md`. First present a concrete Stage 2 proposal covering
> files, behavior, safety boundaries, tests, and deliverables, then stop and
> wait for explicit approval before editing anything. After approval, create
> only the Windows discovery kit and its operator instructions. The kit must
> be safe to author on Linux and execute on Windows 11, write all captured data
> to an explicit external directory, distinguish 32-bit registry state, and
> avoid copying AIM binaries into the repository. Do not implement Windows
> compatibility fixes. Validate the repository and hand off the exact Windows
> test procedure for Stage 3.
