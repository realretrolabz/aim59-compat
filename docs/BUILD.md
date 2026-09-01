# Building the patched Wine 9.0 mciwave DLL

## Purpose

The project modifies Wine 9.0's `dlls/mciwave/mciwave.c` so AIM 5.9.3861 can
open notification WAV files when it includes `MCI_OPEN_SHAREABLE`.

## Ubuntu / Linux Mint prerequisites

The exact set of Wine build dependencies varies by distribution. The
AIM-specific requirement that mattered in the validated build is the 32-bit
MinGW compiler:

```bash
sudo apt install gcc-mingw-w64-i686
```

Also ensure the normal build tools are available:

```bash
sudo apt install build-essential curl patch python3
```

Wine's `configure` may report other missing optional/recommended development
packages. Install those appropriate for your distribution if required.

## Build

```bash
scripts/build-mciwave.sh
```

The script:

1. downloads Wine 9.0 source from WineHQ
2. applies `patches/wine-9.0-mciwave-aim.patch`
3. configures an i386 PE build
4. builds only `dlls/mciwave`
5. copies the PE32 DLL to `dist/`
6. changes the embedded `Wine builtin DLL` marker to `Wine patched DLL`
7. runs structural verification

Expected result:

```text
dist/mciwave-wine9-x86-aim.dll
```

## Verify

```bash
scripts/verify-mciwave.sh dist/mciwave-wine9-x86-aim.dll
```

The published starter binary has a fixed checksum recorded in
`checksums/SHA256SUMS`. A local rebuild may have a different byte-for-byte
hash depending on toolchain/build metadata; structural checks are therefore
separate from the published-binary checksum check.
