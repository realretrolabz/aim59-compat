# Windows compatibility development roadmap

Status updated on 2026-09-02. This document turns the Windows handoff into
bounded development stages. The intended working pattern is one fresh Codex
thread per stage, with a written handoff before moving to the next stage.

## Build-target model

This repository will produce two independent programs from partly shared
source code:

```text
Shared acquisition, verification, manifest, and tests
                         |
             +-----------+-----------+
             |                       |
             v                       v
    Linux build target       Windows x86 build target
    `aim59`                   native Windows compatibility tool
    Wine 9.0 backend          (final name follows Stage 5)
```

The Linux program will not prepare or modify the native Windows installation,
and the Windows executable will not configure Wine. Development can happen
primarily on Linux, but the native Windows executable must be built and
integration tested on Windows.

The preferred Windows result is portable. That name is earned only if Stage 5
proves the strict portable definition below. If AIM cannot meet that gate, the
accepted fallback is a Windows compatibility tool for a normal AIM install
performed by the user. The roadmap must not commit the public executable to
the name `AIM59Portable.exe` until that decision has evidence behind it.

Users should not normally have to select a backend. Each release artifact has
one useful platform target. Backend selection may exist internally for tests
and source-tree development, but the normal interfaces should remain:

```text
# Linux
aim59 setup --source oldversion
aim59 launch

# Windows (provisional name until Stage 5)
AIM59Compat.exe setup --source oldversion
AIM59Compat.exe launch
```

This build-target model supersedes the earlier suggestion that ordinary users
would routinely choose `--backend auto|wine|windows`. If an advanced backend
option is retained, it must default safely, reject host/backend mismatches,
and not blur the separation between the two release artifacts.

## Rules for every stage

Before editing in each thread:

1. Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/WINDOWS_HANDOFF.md`, and
   this roadmap completely.
2. Read all findings produced by earlier Windows stages.
3. Inspect `git status --short --branch` and preserve unrelated work.
4. Keep installer downloads, installed AIM files, raw registry exports, and
   Windows probe output outside the repository.
5. Do not carry Wine fixes into native Windows without direct evidence.
6. Do not claim Windows support until the relevant release gate has passed.
7. Do not push, publish, or create a release unless explicitly requested.

At the end of every code or documentation stage:

1. Run `make verify` on Linux.
2. Run any new platform-specific tests applicable to that stage.
3. Review `git status --short`, `git diff --check`, and the complete diff.
4. Confirm that no AOL/AIM binary or private test data entered the repository.
5. Record decisions, unresolved questions, test environment details, and the
   exact next stage in the handoff.

## Stage overview

- [x] Stage 0: establish scope, definitions, and roadmap
- [x] Stage 1: separate shared orchestration from the Wine backend
- [ ] Stage 2: create the Windows discovery kit
- [ ] Stage 3: capture the Windows 11 baseline
- [ ] Stage 4: isolate required native compatibility changes
- [ ] Stage 5: select portable or installed delivery mode
- [ ] Stage 6: implement the evidence-backed Windows backend
- [ ] Stage 7: complete Windows 11 integration and recovery testing
- [ ] Stage 8: build and verify the Windows release artifact
- [ ] Stage 9: validate Windows 10 before claiming support

Stages are gates, not calendar estimates. A stage may require several test
runs, but its scope should remain fixed within its thread.

## Stage 0: scope and roadmap

### Outcome

Agree that the Windows deliverable is a native, 32-bit compatibility tool,
built separately from the Linux/Wine patcher. It should produce a portable AIM
directory if that can meet the strict portability gate. Otherwise it should
modify a normal AIM installation performed by the user.

### Portable definition

For this project, portable means all of the following:

- the user does not run an AIM or compatibility-tool installer;
- setup/preparation and normal use create no AIM- or project-specific entries
  in the host Windows registry, even temporarily, including entries written by
  AIM or its child processes;
- AIM program files, project configuration, and AIM user state live beneath a
  user-selected directory that can be moved as a unit; and
- removal consists of closing AIM and deleting that directory.

An import/use/export/restore registry transaction is not portable under this
definition. Registration-free COM, app-local dependencies, environment
redirection, or registry virtualization may be investigated, but only a
design that keeps AIM/project registry state out of the host registry can pass.

Windows itself may record ordinary execution artifacts such as Prefetch or
security telemetry. The project does not claim forensic zero-trace operation,
but clean-system observation must find no AIM- or project-specific registry
state caused by the portable workflow.

### Accepted fallback

If AIM requires installation or host registry state for the required feature
set, the supported Windows mode may instead be:

1. the user normally installs the pinned AIM 5.9.3861 build;
2. the compatibility tool verifies and discovers that installation;
3. it applies only compatibility changes proven necessary on Windows 11; and
4. every tool-owned change is documented, repeatable, backed up where
   applicable, and reversible.

The fallback must be described as an installed compatibility mode, never as
portable. AIM's own installer/uninstaller remains responsible for AIM-owned
files and registry state.

### Required Windows experience

A Windows 11 release is blocked unless the tested Open OSCAR environment can
provide the core AIM experience:

- sign-in and sign-out;
- buddy-list display and presence updates;
- one-to-one IM send and receive;
- chat-room use;
- buddy-icon display, selection, and persistence;
- notification sounds, including at least 20 repeated events without a hang;
- profiles and away messages; and
- persistence across AIM exit and relaunch.

The Open OSCAR server address must remain configurable. Release testing needs
a server environment known to implement each network-dependent core feature;
otherwise that gate remains untested. A feature is not attributed to the
client when the test server does not implement or expose it.

Stock ticker, AOL mail/news/weather/content panels, advertising, updater, and
other features backed by retired AIM/AOL services are not release blockers.
Direct Connection and file transfer remain network-dependent and are not
client compatibility blockers unless the network is independently known to
support them.

### Decisions already made

- AIM 5.9.3861 remains the only target version.
- The public Windows compatibility archive will not contain AIM.
- The patched Wine `mciwave.dll` is never used on native Windows.
- Portable is the preferred outcome, but installed compatibility mode is an
  acceptable evidence-driven fallback.
- Windows 11 can be developed and tested first. Windows 10 remains unclaimed
  until it receives its own clean-system validation.

### Exit gate

This roadmap and the existing Windows handoff describe the same strict
portable definition, fallback, and required experience. No Windows
compatibility behavior is presented as already proven.

## Stage 1: backend architecture without behavior changes

### Goal

Create a clean platform boundary while preserving every released Wine and
Lutris command and operation.

### Work

- Define a small backend-facing orchestration contract for setup, doctor,
  launch, and rollback.
- Move construction of `WineBackend` out of general command handlers.
- Keep installer acquisition and verification independent of the backend.
- Keep `patch-prefix` as a Wine-specific operation.
- Preserve existing command lines, defaults, Wine checks, dry-run behavior,
  output where practical, and Lutris integration.
- Add tests for host/target selection and for rejected platform mismatches.
- Do not add native Windows registry, COM, AppCompat, AppData, installation,
  or path-patching behavior.
- Avoid an unnecessary manifest migration. The top-level installer identity
  is already shared; Wine metadata can remain in its current shape until the
  Windows backend has real requirements.

The contract should be no larger than the behavior shared by both platforms.
Wine-specific methods may remain on `WineBackend`; they do not all need fake
Windows equivalents.

### Deliverables

- Backend boundary and selection code.
- Regression tests proving the existing Wine CLI still behaves as before.
- Updated architecture documentation.

### Exit gate

- `make verify` passes.
- Existing Linux and Lutris packaging remains unchanged.
- No Windows fix has been implemented or advertised.

### Next-thread prompt

> Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/WINDOWS_HANDOFF.md`, and
> `docs/WINDOWS_ROADMAP.md` completely. Perform only Stage 1 of the roadmap:
> separate shared CLI orchestration from `WineBackend` without changing
> released Wine or Lutris behavior. Keep `patch-prefix` Wine-only, preserve the
> current manifest unless a change is strictly required, add regression tests,
> run `make verify`, and provide a handoff for Stage 2. Do not implement native
> Windows compatibility operations.

## Stage 2: Windows discovery kit

### Goal

Produce safe, repeatable tools and instructions for observing AIM on the
Windows 11 test machine before designing fixes.

### Work

Create a PowerShell discovery tool that works with the Windows components
already available on the test machine. It should accept an explicit output
directory and collect targeted metadata at named checkpoints:

- Windows edition, build, architecture, and elevation state
- AIM-related processes and their executable paths
- relevant AIM, App Paths, AppCompat, and COM registry keys
- both normal and 32-bit registry views where applicable
- candidate installation and AppData paths
- file names, sizes, SHA-256 values, and PE version metadata
- references to absolute paths in `Xpcs Registry.dat`, without copying the
  file into project evidence
- presence and version of relevant system runtimes such as `mfc40`

The kit should support at least these checkpoints:

```text
00-clean
10-after-install
20-after-first-launch
30-after-aim-exit
40-after-uninstall-or-restore
```

It should also produce a focused comparison between checkpoints. Raw output
must remain external because it can contain usernames, screen names, machine
paths, registry preferences, and proprietary file metadata.

Document two test setups:

1. Preferred: disposable Windows 11 VM with checkpoints.
2. Fallback: dedicated local Windows user with explicit backups and careful
   cleanup. Results from the fallback are not equivalent to a clean VM.

### Deliverables

- PowerShell discovery script.
- Windows discovery procedure and checkpoint worksheet.
- Tests or static validation that can be performed on Linux.
- A documented sanitization process for findings that may be committed.

### Exit gate

- The discovery kit makes no compatibility changes unless a separately named
  test explicitly requests one.
- It does not copy AIM binaries or raw state into the repository.
- Its output format is stable enough to compare multiple experiments.

### Next-thread prompt

> Read the project instructions and Stage 2 of
> `docs/WINDOWS_ROADMAP.md`. Create only the Windows discovery kit and its
> operator instructions. The kit must be safe to author on Linux and execute
> on Windows 11, write all captured data to an explicit external directory,
> distinguish 32-bit registry state, and avoid copying AIM binaries into the
> repository. Do not implement Windows compatibility fixes. Validate the
> repository and hand off the exact Windows test procedure for Stage 3.

## Stage 3: Windows 11 baseline discovery

### Goal

Determine what unmodified AIM 5.9.3861 actually does on a clean Windows 11
system.

### Preparation

- Record the exact Windows edition, build, architecture, virtualization
  status, and whether the test account is administrator or standard user.
- Prefer a clean VM checkpoint. If that is unavailable, clearly label the
  evidence as coming from a non-disposable host.
- Place the pinned installer and all probe output outside the repository.
- Verify the installer SHA-256 before execution.

### Test sequence

1. Capture the clean baseline.
2. Run the normal installer without pre-applied compatibility changes.
3. Capture the installed state.
4. Launch AIM normally and observe whether it starts or hangs.
5. If it runs, test every Stage 0 core feature, including buddy-icon selection
   and persistence, profiles, away messages, and sign-out/relaunch.
6. Exercise at least 20 notification sound events and record responsiveness.
7. Exit AIM and confirm whether child or background processes remain.
8. Capture the post-exit state.
9. Inventory uninstall behavior and capture the restored state.

Do not disable `aimapi.dll`, set XP mode, register `sb.dll`, or add a sound
workaround during the initial baseline. A failed baseline is useful evidence.

### Deliverables

- A sanitized `docs/WINDOWS_FINDINGS.md` or equivalent findings update.
- A list of reproducible failures with exact observations.
- A list of inherited assumptions that the baseline disproved or left open.
- References to external raw evidence without committing that evidence.

### Exit gate

The project can state, with evidence, which behaviors work unmodified and
which specific failures require isolation in Stage 4.

### Next-thread prompt

> Read the project instructions, Windows handoff, roadmap through Stage 3, and
> the Windows discovery-kit instructions. Help me execute or analyze only the
> clean Windows 11 baseline. Do not prescribe fixes before the stock behavior
> is recorded. Keep raw output and AIM files outside the repository, produce
> sanitized findings, and end with a bounded experiment list for Stage 4.

## Stage 4: isolate native compatibility requirements

### Goal

Prove which commonly suggested changes are necessary for AIM 5.9.3861 on the
tested Windows 11 build.

### Method

Start each experiment from the same clean pre-install or post-install
checkpoint. Change one variable at a time, then repeat the exact failing test.

Investigate only when the baseline justifies it:

- disable or restore `aimapi.dll`
- add or remove per-user `WINXPSP3` AppCompat state
- register or unregister `sb.dll`
- test registration-free COM, then explicit HKCU 32-bit COM registration,
  then temporary registration; permanent machine registration is last resort
- test whether App Paths registration is needed
- inspect native MCI behavior without introducing the Wine DLL
- determine whether `mfc40` is already present or actually required

For every successful change, record:

- the failure it fixes
- the smallest exact mutation
- required privilege level
- 32-bit versus 64-bit registry view
- whether it survives movement to another path
- how it can be detected, repeated, and reversed
- what happens if AIM or the launcher crashes

### Deliverables

- Updated sanitized findings.
- A required/optional/rejected decision for every candidate compatibility
  change.
- Reproduction and rollback steps for each required change.

### Exit gate

No proposed Windows mutation rests only on a Wine observation or a guide for
AIM 5.9.6089. Remaining unknowns are explicitly moved into the portability
proof rather than silently assumed.

### Next-thread prompt

> Read the project instructions and Windows findings. Perform only Stage 4 of
> `docs/WINDOWS_ROADMAP.md`: design and analyze controlled Windows 11
> experiments that isolate the failures found in Stage 3. Change one variable
> per clean checkpoint. Record the exact reversible mutation and privilege
> requirement. Never use the patched Wine `mciwave.dll`. Finish with the
> evidence-backed operations, if any, that Stage 5 may use.

## Stage 5: delivery-mode feasibility gate

### Goal

Prove or disprove that AIM can satisfy the Stage 0 portable definition. If it
cannot, prove that the installed compatibility fallback is viable.

This is the principal feasibility gate for the Windows deliverable.

### Work areas

#### Application preparation

- Determine whether the pinned installer can be extracted or otherwise used
  to prepare a chosen user directory without running an installation workflow.
- Verify the installed `aim.exe` product/file version as 5.9.3861.
- Do not accept an unknown installer as a supported Windows preparation,
  regardless of any general `--allow-unverified` acquisition escape hatch.

#### `Xpcs Registry.dat`

Determine, in this order:

1. whether AIM or XPCS can regenerate it for the current directory;
2. whether a supported registration process rewrites its paths;
3. whether its format can be understood and safely updated;
4. whether a process-local path-indirection mechanism avoids rewriting it
   without leaving an object or state outside the portable root.

Do not use blind binary search-and-replace. Moving the prepared folder to a
second path must be part of every candidate test.

#### Registry isolation

Use the discovery kit and, where available, focused process tracing to prove
that preparation, launch, core-feature use, exit, and relaunch create no
AIM- or project-specific host registry entries. Check both 32-bit and 64-bit
views and compare against the clean checkpoint.

Test registration-free and app-local mechanisms before considering more
complex isolation. A transaction that temporarily imports and later restores
host registry entries fails the portable gate. Any registry virtualization
prototype must keep the virtualized state beneath the portable root, survive
relocation, and recover safely from a crash without having written that state
to the host registry.

#### AppData

First test process-local environment redirection. If AIM does not honor it,
test a process-local filesystem virtualization or alias mechanism whose data
and configuration remain beneath the portable root. Do not redirect the
user's global shell folders or entire AppData tree. Copying state into the
host AppData tree and restoring it later fails the portable gate, though a
narrowly scoped and reversible strategy may be evaluated for installed mode.

#### COM and AppCompat

Use only the mechanisms proven necessary in Stage 4. For portable mode, COM
and AppCompat must work without AIM/project-specific host registry entries.
Needing such entries is evidence for the installed fallback, not permission to
weaken the portable definition.

#### Installed fallback proof

If the portable proof fails, start from a normal user-installed copy of the
pinned AIM build. Prove discovery, required compatibility changes, core
features, repeat application, rollback of tool-owned changes, and continued
operation after restart. Record exactly which AIM-owned and tool-owned files
and registry entries remain, and which are removed by AIM's uninstaller.

### Deliverables

- A small throwaway prototype or documented manual proof.
- A clear go/no-go decision for strict portable mode, supported by evidence.
- For a portable result: final directory layout, state schema, and chosen
  XPCS, registry-isolation, AppData, COM, and AppCompat strategies.
- For an installed result: installation discovery, mutation, backup, rollback,
  and uninstall ownership model.
- Explicit crash-recovery and concurrent-launch behavior for the chosen mode.

### Exit gate

Exactly one delivery mode is selected for initial implementation:

- **Portable:** preparation and core-feature use meet the strict Stage 0
  definition, AIM launches after movement, state persists, and no stale path
  breaks the required experience; or
- **Installed fallback:** strict portability is recorded as infeasible, a
  normal user install supports the required experience after the smallest
  proven compatibility changes, and tool-owned changes have a tested restore
  path.

If neither mode passes, stop before building a production backend.

### Next-thread prompt

> Read all Windows findings and perform only Stage 5 of
> `docs/WINDOWS_ROADMAP.md`. Prove or disprove strict portability on Windows
> 11, concentrating on extraction, `Xpcs Registry.dat`, relocation, AppData,
> zero AIM/project host-registry entries, COM, and crash recovery. A temporary
> host-registry transaction does not qualify. If portability fails, prove the
> normal-install compatibility fallback instead. Do not build the production
> tool yet. Never commit AIM files or raw host state. End with one selected
> delivery mode and a go/no-go decision for Stage 6.

## Stage 6: Windows backend implementation

### Goal

Implement only the delivery mode and operations proven necessary in Stages 3
through 5.

### Work

- Add the native Windows backend and platform-specific state model.
- Keep one-time preparation separate from per-launch behavior.
- In portable mode, derive every application path from the selected portable
  root and never create AIM/project host-registry entries.
- In installed mode, discover and verify the user-installed location instead
  of extracting or redistributing AIM.
- Use explicit Windows APIs and the correct 32-bit registry view.
- Make setup, repair, doctor, launch, and rollback idempotent.
- Add a single-instance lock and durable change journal when the proven mode
  requires them.
- Recover interrupted tool-owned changes before starting AIM again.
- Validate configurable OSCAR hostname and port without embedding a private
  network address.
- Keep the Wine backend and Linux/Lutris packaging unchanged.
- Add unit tests with mocked filesystem, process, registry, and platform
  boundaries so most logic remains testable on Linux.

Suggested layout if portable mode passes:

```text
AIM59Portable/
|-- AIM59Portable.exe       # added by the later package stage
|-- app/AIM/                # created locally from the verified installer
|-- config/settings.json
|-- data/appdata/
|-- state/journal.json
`-- logs/
```

The public compatibility artifact must ship without `app/AIM` contents.

### Deliverables

- Native Windows backend source.
- Linux-runnable unit tests for platform boundaries.
- Windows-specific doctor and rollback behavior.
- Documentation matching every implemented mutation.

### Exit gate

- Linux `make verify` passes without changing the Wine baseline.
- Windows unit tests pass under a Windows Python environment.
- Every mutation has backup, repeat-apply, detection, and restore coverage.
- Implementation contains no speculative fallback copied from Wine.

### Next-thread prompt

> Read all project instructions, the complete Windows roadmap, and the
> evidence-backed findings. Implement only Stage 6: the smallest native
> Windows backend for the delivery mode selected in Stage 5. Preserve
> Linux/Wine and Lutris behavior, keep setup separate from launch, honor the
> strict no-host-registry rule if portable mode passed, and implement the
> applicable locking, journaling, idempotence, doctor, and rollback behavior.
> Add boundary-mocked tests and run all Linux validation. Do not package or
> claim Windows support yet.

## Stage 7: Windows 11 integration and recovery

### Goal

Validate the source-tree Windows backend end to end on clean Windows 11 before
turning it into a distributable executable.

### Required tests

- fresh portable preparation or discovery of a normal install, according to
  the Stage 5 decision
- first and second setup/repair runs
- standard-user operation and elevation behavior
- every Stage 0 core feature, including buddy-icon selection and persistence
- 20+ notification events without a hang
- logout/login and application restart
- Windows restart
- for portable mode, move the entire directory and launch again
- for portable mode, persistence of settings after movement and confirmation
  that no AIM/project registry entries were created
- for installed mode, repair after an AIM reinstall and preservation of
  unrelated pre-existing AIM registry state
- doctor before setup, after setup, during recoverable damage, and after repair
- normal rollback and repeated rollback
- forced launcher termination during each applicable change/journal phase
- AIM crash or forced termination
- recovery after power-loss-equivalent interrupted state
- for installed mode, preservation and restoration of pre-existing host AIM
  registry state affected by the tool
- rejection or serialization of a concurrent second launcher

Direct Connection and file transfer remain network-dependent and are not basic
compatibility blockers unless the network is independently known to support
them.

### Deliverables

- Sanitized Windows 11 integration report.
- Updated automated tests for every discovered defect.
- Final list of supported behavior and known limitations.

### Exit gate

All Stage 0 core-experience tests and applicable delivery-mode tests pass on a
clean Windows 11 environment. Portable mode leaves no AIM/project-specific
host registry entries. Installed mode leaves no unexplained or unrecoverable
tool-owned change.

### Next-thread prompt

> Read the Windows roadmap and findings, then perform only Stage 7. Guide or
> analyze clean Windows 11 end-to-end testing of the source-tree backend,
> including relocation, repeat application, rollback, concurrency, forced
> termination, and crash recovery. Keep raw evidence external and commit only
> sanitized results and regression tests. Do not build or publish a release
> until every Windows 11 release gate is accounted for.

## Stage 8: Windows build and release verification

### Goal

Produce a Windows-specific compatibility artifact that needs no separately
installed Python and contains no AIM software. Its name and instructions must
accurately identify the Stage 5 delivery mode.

### Work

- Build on Windows with a 32-bit Python toolchain so the launcher is an x86
  Windows PE executable aligned with AIM and its COM component.
- Start with a transparent directory-based bundle rather than optimizing for
  one-file packaging before reliability is established.
- Give the Windows build its own packaging script, checksums, archive name,
  licenses, and verification rules.
- Ensure the Windows archive excludes the AIM installer, installed AIM tree,
  Wine `mciwave.dll`, Wine patches, and Linux/Lutris runtime assets.
- Inventory and license the Python runtime and packaging dependencies included
  in the Windows bundle.
- Add Windows CI for unit tests and reproducible packaging. Clean AIM
  integration testing may remain a documented manual gate because CI must not
  download or redistribute proprietary AIM files outside the established
  user-initiated acquisition policy.
- Update repository and release guards to distinguish the project-built
  launcher/runtime from forbidden AOL/AIM binaries without weakening the
  source-tree prohibition.

Do not cross-build the final Windows executable on Linux and assume that it is
valid. The executable must be built and exercised on Windows.

### Deliverables

- The appropriately named Windows executable and its required runtime files
  inside a Windows archive.
- Windows checksums and release verifier.
- Windows build instructions and CI job.
- Final Windows 11 installation, operation, rollback, and removal docs.

### Exit gate

- A clean Windows 11 user can follow the documented portable-preparation or
  normal-install workflow, launch AIM, use every Stage 0 core feature, and
  remove or roll back the compatibility tool according to the selected mode.
- Only a portable-mode artifact is required to survive directory movement and
  leave no AIM/project-specific host registry entries.
- The pristine public archive contains no AOL/AIM binary.
- Linux release contents and Lutris behavior are unchanged.
- Publishing still requires a separate explicit request.

### Next-thread prompt

> Read all project and Windows release instructions. Perform only Stage 8 of
> `docs/WINDOWS_ROADMAP.md`: create and verify the native x86 Windows build
> target from the already validated backend. Build on Windows, keep the public
> archive free of AIM and Wine runtime files, preserve Linux packaging, add
> checksums and appropriate CI, and run the clean-artifact test. Do not publish
> anything unless I explicitly request it.

## Stage 9: Windows 10 validation

### Goal

Decide whether the already validated Windows artifact can truthfully claim
Windows 10 support.

### Work

- Repeat the complete clean-system Windows integration matrix on a recorded
  Windows 10 build.
- Treat different AppCompat, runtime, COM, MCI, and security behavior as new
  evidence rather than assuming parity with Windows 11.
- Add only narrowly scoped Windows-version handling if a reproducible
  difference requires it.

### Exit gate

Only after the complete matrix passes may documentation and project metadata
change from Windows 11 support to Windows 10/11 support. A Windows 11-only
release is acceptable if Windows 10 remains unavailable or fails validation.

### Next-thread prompt

> Read the Windows roadmap, final Windows 11 findings, and release test matrix.
> Perform only Stage 9: validate the existing artifact on a clean Windows 10
> system. Do not assume Windows 11 results carry over. Record the exact OS
> build, run the full compatibility, relocation, rollback, and recovery matrix,
> and update support claims only if all release gates pass.

## Per-stage handoff template

End each future thread with a handoff containing:

```text
Stage completed:
Repository commit or working-tree state:
Tests run and results:
Windows environment, if used:
External evidence location:
Sanitized findings added:
Decisions made:
Known failures or unanswered questions:
Proprietary/private data check:
Exact next stage:
Recommended prompt for the next thread:
```

If a stage does not meet its exit gate, the handoff must say so explicitly.
The next thread should continue that same stage rather than advancing and
building on an unproven assumption.
