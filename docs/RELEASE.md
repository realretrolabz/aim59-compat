# Release process

## Before release

```bash
make verify
make release
git status --short
git diff --check
```

Confirm there are no AOL/AIM binaries in Git history or the working tree.

Review `lutris/aim-5.9.3861.yml` and confirm that its versioned GitHub URLs
match the release tag.

## Release assets

For v0.1.3, upload the complete payload produced by `make release`:

```text
aim59-compat-0.1.3-linux.tar.gz
aim59-patcher.pyz
mciwave-wine9-x86-aim.dll
mciwave-wine10-x86-aim.dll
aim-5.9.3861.yml
SHA256SUMS
```

The archive is the user-facing terminal distribution and the asset consumed by
the Lutris YAML. The `.pyz` and loose DLLs are retained as implementation
assets. Do not publish AIM itself.

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

For an initial Windows release, upload only:

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
git tag -a v0.1.3 -m "AIM 5.9 Wine compatibility v0.1.3"
git push origin v0.1.3
```

Create the release only after the tag and release assets have been reviewed.

## GitHub CLI example

```bash
gh release create v0.1.3 \
  dist/aim59-compat-0.1.3-linux.tar.gz \
  dist/aim59-patcher.pyz \
  dist/mciwave-wine9-x86-aim.dll \
  dist/mciwave-wine10-x86-aim.dll \
  dist/aim-5.9.3861.yml \
  dist/SHA256SUMS \
  --title "AIM 5.9 Compatibility v0.1.3" \
  --notes "Terminal patcher for AIM 5.9.3861 with versioned Wine DLLs."
```
