# Windows 11 baseline findings

Status: Stage 3 baseline completed on 2026-09-10. These are sanitized findings
from the private checkpoint evidence; raw snapshots, comparisons, notes, and
AIM files remain outside this repository.

## Test environment and method

- Dedicated, disposable Windows 11 Pro VM, build 26200, x64, with the test
  account running the collector elevated.
- A powered-off `Pre-AIM` disk-only snapshot was restored before the
  authoritative run. The separate evidence disk was outside the system-disk
  snapshot chain.
- The exact five checkpoints were captured successfully with the Stage 2
  collector: clean, post-install, post-first-launch, post-exit, and
  post-uninstall. Each valid collection reported zero collection errors.
- AIM 5.9.3861 was installed normally. No project compatibility setting, Wine
  file, DLL registration command, AppCompat layer, or other workaround was
  applied.
- The first collector attempt is not used for this finding: it exposed a
  collector false positive that treated a Windows `Usb.dll` as AIM `sb.dll`.
  The collector was corrected and the complete authoritative run was repeated
  from `Pre-AIM`.

## Observed stock behavior

### Baseline

No AIM process, targeted AIM registry key, App Paths entry, uninstall entry,
or AIM COM server was detected at the clean checkpoint.

The 32-bit/WOW64 system directory already contained `mfc40.dll` (file version
4.1.6140). This establishes presence only: it does not show that AIM requires
that runtime or that it is sufficient for a successful launch. Both normal and
WOW64 `regsvr32.exe` files were present.

### Normal installation

The installer placed AIM under the normal 32-bit Program Files location. The
post-install checkpoint observed:

- App Paths entries for `aim.exe`;
- a 32-bit uninstall entry;
- AIM protocol/file-association classes;
- 32-bit COM registrations pointing at AIM `sb.dll`, `aimapi.dll`, `RTvideo.dll`,
  `aimauto.exe`, and `aim.exe`; and
- an `Xpcs Registry.dat` in the installation tree, with absolute-path
  references captured only in the private evidence.

The user's Compatibility Assistant Store recorded the installer after normal
installation. The collector records its binary values only by size, so this
finding does not infer their meaning.

### First launch

On the first normal launch, `aim.exe` remained running in the background but
never displayed a GUI. The process path was the installed AIM executable. No
core AIM feature could therefore be reached: sign-in, buddy list, IMs, chat,
icons, profiles, away messages, and notification sounds are all **not
reached**, not passed or failed separately.

The first-launch checkpoint added a Compatibility Assistant Store record for
the AIM executable. It did not show a user-configured AppCompat Layer value.
Because no GUI appeared, normal application exit was impossible; the process
was ended through Task Manager and the post-exit checkpoint then confirmed that
no AIM process remained. This is a forced-termination observation, not a clean
AIM exit result.

### Normal uninstall

The normal uninstaller's full user-data-removal choice was selected. At the
post-uninstall checkpoint:

- the App Paths and uninstall entries were no longer detected;
- the installed AIM directory still existed with `msvcr71.dll` remaining;
- the AIM roaming-data directory still existed, though its contents were not
  inspected for this sanitized report;
- AIM protocol/file-association classes and 32-bit COM registrations remained,
  including registrations that pointed at removed AIM `sb.dll`, `aimapi.dll`,
  and `RTvideo.dll`; and
- Compatibility Assistant Store records for the installer, AIM executable, and
  uninstaller remained.

The post-uninstall scan did not detect `Xpcs Registry.dat`.

## Reproducible failure

On this Windows 11 build, AIM 5.9.3861's stock first launch leaves `aim.exe`
running without a visible GUI. It is therefore not usable in the required core
experience. This result is directly observed from the clean snapshot run.

## What this does and does not establish

The baseline supports investigating the stock first-launch failure in Stage 4.
It does **not** establish any native Windows fix:

- The installer-created `sb.dll` and `aimapi.dll` registrations are observations,
  not evidence that registration, unregistration, or disabling either DLL fixes
  the invisible-GUI failure.
- The Compatibility Assistant Store is an automatic Windows observation, not a
  tested compatibility-layer fix.
- `mfc40.dll` being present does not prove whether it is required.
- Native MCI and repeated sounds were not reached. The patched Wine
  `mciwave.dll` must never be used on Windows.
- A normal installation writes host registry and user-data state. This does not
  decide the later strict-portable feasibility gate, which requires separate
  extraction, relocation, and registry-isolation evidence.

## Stage 4 initial result

On the same Windows 11 VM, a normal AIM 5.9.3861 installation became visibly
usable after `aimapi.dll` was disabled. No Windows XP compatibility layer,
`sb.dll` registration change, native MCI change, or Wine file was applied in
that successful launch. This establishes `aimapi.dll` disabling as the smallest
observed launch workaround for that VM; it does not establish broader feature,
sound, recovery, or Windows-version support.

## Stage 4 gate

Before any Stage 4 VM action, a new thread must present a concrete,
one-variable-at-a-time experiment proposal and wait for explicit approval. Each
approved experiment must restore `Pre-AIM`, name the exact reversible mutation,
state its registry view and required privilege, repeat the visible-GUI launch
test, and capture the same checkpoint evidence. No production backend or
compatibility claim is authorized at this stage.
