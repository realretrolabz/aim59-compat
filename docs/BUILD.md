# Building the patched Wine 9.0 and 10.0 mciwave DLLs

## Purpose

The project modifies Wine 9.0 and 10.0's `dlls/mciwave/mciwave.c` so AIM
5.9.3861 can open notification WAV files when it includes
`MCI_OPEN_SHAREABLE`.

## Ubuntu / Linux Mint prerequisites

The exact set of Wine build dependencies varies by distribution. The
AIM-specific requirement that mattered in the validated build is the 32-bit
MinGW compiler:

```bash
sudo apt install gcc-mingw-w64-i686
```

Also ensure the normal build tools are available:

```bash
sudo apt install build-essential curl patch python3 flex bison
```

Wine's `configure` may report other missing optional/recommended development
packages. Install those appropriate for your distribution if required.

## Build

```bash
scripts/build-mciwave.sh
```

`make build` builds both versions. To build only one:

```bash
make build-wine9
make build-wine10
```

The versioned build:

1. downloads the selected Wine source from WineHQ
2. applies the matching patch from `patches/`
3. configures an i386 PE build
4. builds only `dlls/mciwave`
5. copies the PE32 DLL to `dist/`
6. changes the embedded `Wine builtin DLL` marker to `Wine patched DLL`
7. runs structural verification

Expected result:

```text
dist/mciwave-wine9-x86-aim.dll
dist/mciwave-wine10-x86-aim.dll
```

## Verify

```bash
scripts/verify-mciwave.sh dist/mciwave-wine9-x86-aim.dll
scripts/verify-mciwave.sh dist/mciwave-wine10-x86-aim.dll
```

The published starter binary has a fixed checksum recorded in
`checksums/SHA256SUMS`. A local rebuild may have a different byte-for-byte
hash depending on toolchain/build metadata; structural checks are therefore
separate from the published-binary checksum check.

## Build the native Windows setup

The Windows Forms source and native workflow are in `windows/AIM59Setup/`. It
targets .NET Framework 4.8, which is compatible with the .NET Framework
4.8/4.8.1 line included with Windows 11. Build it on Windows from the
repository root:

```powershell
.\scripts\windows\build-aim59-setup.ps1
```

The command uses the installed .NET Framework C# compiler and writes the only
compiled output here:

```text
.build\windows-exe\rrlzAIM.exe
```

`.build/` is ignored. Do not copy the EXE into the repository, `dist/`, or a
test fixture. A Windows release may distribute it as a standalone asset with a
SHA-256 file; see [RELEASE.md](RELEASE.md#windows-utility-asset). The build
script fails clearly if the C# compiler is absent. The launcher has been
guest-tested on Windows 11; building it on another machine does not by itself
test that machine's Windows setup.

The EXE is a self-contained Windows installer/patcher. It embeds
the repository's multi-resolution setup icon and needs no adjacent PowerShell
script. Its historical PowerShell proof-of-concept is retained in source but
is not an EXE dependency; see
[WINDOWS_INSTALL.md](WINDOWS_INSTALL.md).

### Optional Linux cross-build

On a Debian/Ubuntu Linux host, install Mono once:

```bash
sudo apt install mono-devel
```

Then build the same managed PE32 EXE with:

```bash
./scripts/build-aim59-setup-mono.sh
```

It writes the same ignored `.build/windows-exe/rrlzAIM.exe` output. This is
useful when Windows runs only in a VM: copy the EXE to the guest or thumb drive
for use or testing. Mono compilation does not run the EXE on Windows; retain
the Windows PowerShell build as the Windows-native build/CI path when available.
