# Windows 11 discovery kit

This is the Stage 2 collection kit for the planned native Windows backend. It
observes AIM 5.9.3861 on Windows 11 before any compatibility change is
designed. It does **not** make AIM work on Windows or make a Windows support
claim.

The collector is
[scripts/windows/collect-aim59-discovery.ps1](../scripts/windows/collect-aim59-discovery.ps1).
It uses inbox Windows PowerShell components on Windows 11: no module,
installer, script signing, upload service, or project installation is needed.

## Safety contract

The collector has two parameter sets:

~~~
Collection: collect-aim59-discovery.ps1 -OutputDirectory PATH -Checkpoint NAME
Comparison: collect-aim59-discovery.ps1 -OutputDirectory PATH -BaselineDirectory PATH -ComparisonDirectory PATH
~~~

OutputDirectory is mandatory in both cases. It must be a new or empty directory
outside the collector's directory. The collector writes only the named JSON and
text artifacts beneath that output directory; it has no default output
location and never writes to the repository or script directory.

It is observational only. In particular, it does not:

- install, launch, exit, or uninstall AIM;
- modify, export, import, or otherwise write a registry value;
- register or unregister a DLL;
- set AppCompat, compatibility-mode, COM, environment, or sound settings;
- copy AIM executables, DLLs, Xpcs Registry.dat, installer payloads, or AppData
  files; or
- upload data, use a remote share, collect USB inventory, or transmit
  telemetry.

The only write is creating the explicitly named output directory and its own
artifacts. A PowerShell process launched with -ExecutionPolicy Bypass below
uses that setting for that one process only; it does not persist an execution
policy change.

Raw output is private evidence. It can contain account paths, screen-name or
preference-adjacent AIM registry data, proprietary file metadata, and machine
details. Keep it on F: (or an equivalent external evidence volume), not in a
Git checkout, release asset, fixture, or issue attachment.

## What a snapshot contains

Every collection writes these two files directly under its output directory:

| File | Contents |
| --- | --- |
| discovery.json | Versioned (aim59.windows.discovery/v1) targeted snapshot. |
| collection-summary.txt | Checkpoint name, output location, and partial-collection error count. |

The snapshot records:

- Windows edition, version, build, architecture, elevation state, and minimal
  virtualization context;
- running aim.exe process IDs, parent IDs, and executable paths, without
  command lines or account names;
- the relevant AIM product, App Paths, uninstall, AppCompat, class/ProgID, and
  COM server registry surfaces;
- LocalMachine and CurrentUser separately through explicit Registry64 and
  Registry32 (32-bit/WOW64) views. It does not use implicit registry
  redirection or merged HKCR access;
- common and discovered installation candidates, plus candidate roaming and
  local AppData directories (existence only for AppData);
- names, sizes, SHA-256 values, and PE version fields for exe, dll, and ocm
  files beneath an existing candidate AIM installation. The files themselves
  are never copied;
- the presence and version metadata of mfc40.dll and regsvr32.exe in the normal
  and WOW64 system directories; and
- only absolute-path strings found in an existing Xpcs Registry.dat, with its
  size and SHA-256. The collector reads that file in place and never writes a
  copy of it.

Registry collection is deliberately narrow. It captures AIM-labelled values
from relevant install surfaces and reports COM InprocServer32 or LocalServer32
entries only when the server path is AIM/AOL-related. It does not make a broad
registry export.

The file inventory and Xpcs Registry.dat reference list observe installation
ownership and stale absolute paths; neither is evidence that a portable
workflow is feasible.

## Collector commands

Use a unique, empty subdirectory for each snapshot. These examples assume the
script was copied from USB to E:\AIM59-Toolkit; output is deliberately a sibling
on the evidence volume.

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\00-clean' -Checkpoint '00-clean'
~~~

The checkpoint names are fixed:

~~~text
00-clean
10-after-install
20-after-first-launch
30-after-aim-exit
40-after-uninstall-or-restore
~~~

For example, collect post-install state with:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\10-after-install' -Checkpoint '10-after-install'
~~~

After two snapshots exist, create a focused comparison in a third, new
directory. It reads the existing JSON but does not copy it.

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\compare-00-to-10' -BaselineDirectory 'E:\AIM59-Evidence\00-clean' -ComparisonDirectory 'E:\AIM59-Evidence\10-after-install'
~~~

That directory receives comparison.json and comparison-summary.txt.
comparison.json compares targeted processes, registry views, candidate paths,
installation file metadata, Xpcs Registry.dat path references, and the system
runtime inventory. It excludes timestamps and Windows identity so checkpoint changes
remain focused.

Exit status 0 means the requested snapshot or comparison completed. Exit status
2 means a collection section was inaccessible or failed; the partial
discovery.json is still written with an errors entry. Resolve or record that
error before treating a comparison as complete. Failure to create an approved
output directory or to find a comparison input is a hard PowerShell error.

## Test environments

Preferred: use the dedicated, disposable Windows 11 VM and its external,
powered-off/disk-only pre-AIM snapshot. The F: evidence disk must remain outside
the system-disk snapshot chain. Only this setup can make a clean-baseline claim.

Fallback: use a dedicated local Windows account, make explicit backups, and
remove AIM with its normal uninstaller afterwards. Label every result from this
route as **non-disposable host evidence**. It can identify an observation worth
retesting but cannot settle clean-baseline or portable-registry claims.

## Stage 3: exact clean-VM sequence

Stage 3 is the first Windows execution. It remains observation-only: do not
disable aimapi.dll, register sb.dll, set an XP/AppCompat layer, add App Paths or
COM entries, install mfc40, copy Wine files, or use the patched Wine
mciwave.dll. A stock failure is useful evidence.

### 1. Confirm the host and evidence volume

With the VM powered off, run these read-only commands on the Debian host:

~~~bash
sudo virsh snapshot-list win11
sudo virsh domblklist win11 --details
~~~

Record the clean pre-AIM snapshot name and confirm that the active system-disk
overlay is not altered. Confirm that separate vdb is the evidence qcow2 image,
not part of the snapshot chain. Do not rename, move, merge, or delete any image
or overlay.

Inside Windows, confirm that the separate volume is really F: and writable. In
an elevated PowerShell window, record the chosen decrypted, protection-off
state before calling the VM baseline:

~~~powershell
Get-Volume -DriveLetter F | Format-List DriveLetter,FileSystemLabel,HealthStatus,SizeRemaining,Size
manage-bde -status F:
New-Item -ItemType Directory -Force -Path 'E:\AIM59-Evidence'
~~~

Keep aim593861.exe, the collector, its documentation, and every raw output
directory beneath F:. The known installer is already the pinned 5.9.3861
installer identified by the project; this stage does not require another manual
script or installer hash check. The USB drive is transport only.

### 2. Capture the stock baseline

Before installing or launching AIM:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\00-clean' -Checkpoint '00-clean'
~~~

Check collection-summary.txt only to confirm its output location and error
count. Do not move raw JSON into the repository.

### 3. Install and observe stock AIM

Run the normal F:\...\aim593861.exe installer without pre-applying a
compatibility change. Record whether elevation was requested, the selected
installation path, success or failure, and any visible error. Do not attempt a
workaround if installation fails.

Immediately collect:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\10-after-install' -Checkpoint '10-after-install'
~~~

Launch AIM normally from the shortcut or normal installation location found by
the installer. Do not alter its properties or Windows compatibility settings.
Record whether it starts, hangs, requests elevation, or leaves a process behind.

If the selected Open OSCAR test environment is available, keep its address in
private evidence and run the worksheet below. A server feature missing from
that environment is **untested**, not a client pass or failure.

Capture first-launch state while AIM is open, or immediately after a
reproducible launch failure:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\20-after-first-launch' -Checkpoint '20-after-first-launch'
~~~

### 4. Exit, uninstall, and compare

Use AIM's normal UI to sign out and exit; do not terminate it for the baseline.
Record whether an AIM process remains after a reasonable observation period,
then collect:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\30-after-aim-exit' -Checkpoint '30-after-aim-exit'
~~~

Use AIM's normal uninstaller, without manually deleting leftovers first.
Record its result and then collect:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1' -OutputDirectory 'E:\AIM59-Evidence\40-after-uninstall-or-restore' -Checkpoint '40-after-uninstall-or-restore'
~~~

Create the focused comparisons:

~~~powershell
$collector = 'E:\AIM59-Toolkit\collect-aim59-discovery.ps1'
$evidence = 'E:\AIM59-Evidence'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $collector -OutputDirectory "$evidence\compare-00-to-10" -BaselineDirectory "$evidence\00-clean" -ComparisonDirectory "$evidence\10-after-install"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $collector -OutputDirectory "$evidence\compare-10-to-20" -BaselineDirectory "$evidence\10-after-install" -ComparisonDirectory "$evidence\20-after-first-launch"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $collector -OutputDirectory "$evidence\compare-20-to-30" -BaselineDirectory "$evidence\20-after-first-launch" -ComparisonDirectory "$evidence\30-after-aim-exit"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $collector -OutputDirectory "$evidence\compare-00-to-40" -BaselineDirectory "$evidence\00-clean" -ComparisonDirectory "$evidence\40-after-uninstall-or-restore"
~~~

The final comparison observes normal uninstall/restoration; it does not prove a
forensic zero-trace state.

## Stage 3 worksheet

Keep this worksheet with private evidence. A future sanitized finding should
state only the observation and comparison that supports it.

| Observation | Record at checkpoint(s) |
| --- | --- |
| Windows edition/build/architecture, VM context, account elevation | 00-clean |
| F: identity and encryption state | Before 00-clean |
| Installer elevation, selected directory, result | Install notes, 10-after-install |
| AIM product/App Paths/uninstall/AppCompat/COM changes in both views | 00→10, 10→20, 00→40 |
| aim.exe path, launch result, child/remaining process behavior | 20-after-first-launch, 30-after-aim-exit |
| mfc40 and both regsvr32.exe versions; sb.dll/aimapi.dll observations | Snapshots and private notes; do not alter DLLs |
| Xpcs Registry.dat absolute-path references | 10-after-install and later |
| Sign-in/sign-out, buddy list/presence, IM send/receive, chat rooms | While AIM is running; identify server capability separately |
| Buddy icon selection/display/persistence; profile and away messages | While running and after relaunch |
| Twenty separate notification events and responsiveness | Count each event; record sound, hang, and recovery |
| State persistence across exit/relaunch | 20, 30, next-launch notes |
| Normal uninstall behavior and AIM-specific state | 40 and 00→40 comparison |

If AIM never reaches a test, write **not reached because ...**. If the server
does not provide a network feature, write **untested: server capability**. Do
not turn either result into a presumed compatibility fix.

## Sanitizing a finding for Git

Raw evidence stays private. When Stage 3 is complete, create a short,
deliberate sanitized finding:

1. State the Windows edition/build, checkpoint pair, and observation.
2. Replace account names, screen names, hostnames, serials, and user-specific
   path components with placeholders such as <USER> or <PRIVATE-SERVER>.
3. Include only relevant key names, value names, file basenames, SHA-256
   values, and path shapes needed for an implementation decision. Do not paste
   raw registry blocks, full AppData paths, command lines, or Xpcs Registry.dat
   content.
4. Say whether a conclusion is observed, unknown, or blocked by server
   capability. Never infer a native Windows fix from Wine behavior.
5. Before committing a sanitized finding, run make verify, inspect the full
   diff, and confirm that no raw evidence or AOL/AIM file entered Git.

Stage 3 may add a reviewed docs/WINDOWS_FINDINGS.md only after that process. It
must reference the private evidence location generically, not copy it.
