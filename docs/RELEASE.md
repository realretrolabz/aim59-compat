# Release process

## Before release

```bash
make verify
make release
git status --short
git diff --check
```

Confirm there are no AOL/AIM binaries in Git history or the working tree.

`make verify` validates the archive built from the working tree. Run it from
the exact commit intended for publication, then review `dist/SHA256SUMS` before
uploading release assets.

## Release assets

For v0.1.4, upload the complete payload produced by `make release`:

```text
rrlzAIM-0.1.4-linux.tar.gz
rrlzAIMlinux.pyz
mciwave-wine9-x86-aim.dll
mciwave-wine10-x86-aim.dll
SHA256SUMS
```

The archive is the user-facing terminal distribution. The `.pyz` and loose
DLLs are retained as implementation assets. Do not publish AIM itself.

The GitHub Release should also link to the repository source at the matching
tag so the modified Wine binary's corresponding patch/build instructions are
readily available.

## Windows utility asset

The Windows utility is a separate, self-contained asset. Build it from the
matching source commit with the native Windows command:

```powershell
.\scripts\windows\build-aim59-setup.ps1
$hash = (Get-FileHash .build\windows-exe\rrlzAIM.exe -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  rrlzAIM.exe" | Set-Content -NoNewline .build\windows-exe\rrlzAIM.exe.sha256
```

For v0.1.4, also upload these separately built Windows assets:

```text
rrlzAIM.exe
rrlzAIM.exe.sha256
```

`rrlzAIM.exe` stays ignored and must not be committed, included in the Linux
archive, or bundled with the terminal patcher. The published SHA-256 file must
be generated from the exact EXE being uploaded; a Mono cross-build and a native
Windows build need not be byte-identical.

Never include an AIM installer, `aim.exe`, an AIM installation directory, or
private VM material with the Windows asset. The EXE is self-contained and does
not need `install-aim59.ps1` beside it.

## Tag

Example:

```bash
git tag -a v0.1.4 -m "realretrolabz AIM Manager v0.1.4"
git push origin v0.1.4
```

Create the release only after the tag and release assets have been reviewed.

## GitHub CLI example

```bash
gh release create v0.1.4 \
  dist/rrlzAIM-0.1.4-linux.tar.gz \
  dist/rrlzAIMlinux.pyz \
  dist/mciwave-wine9-x86-aim.dll \
  dist/mciwave-wine10-x86-aim.dll \
  dist/SHA256SUMS \
  --title "realretrolabz AIM Manager v0.1.4" \
  --notes "AIM 5.9.3861 compatibility tools for Linux/Wine and native Windows."
```

From the Windows build machine, attach the exact EXE and checksum generated
there:

```powershell
gh release upload v0.1.4 `
  .build\windows-exe\rrlzAIM.exe `
  .build\windows-exe\rrlzAIM.exe.sha256
```
