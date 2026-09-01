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

For v0.1.1, upload the complete payload produced by `make release`:

```text
aim59-compat-0.1.1-linux.tar.gz
aim59-patcher.pyz
mciwave-wine9-x86-aim.dll
aim-5.9.3861.yml
SHA256SUMS
```

The archive is the user-facing terminal distribution. The `.pyz` and loose
DLL are retained as Lutris implementation assets. Do not publish AIM itself.

The GitHub Release should also link to the repository source at the matching
tag so the modified Wine binary's corresponding patch/build instructions are
readily available.

## Tag

Example:

```bash
git tag -a v0.1.1 -m "AIM 5.9 Wine compatibility v0.1.1"
git push origin v0.1.1
```

Create the release only after the tag and release assets have been reviewed.

## GitHub CLI example

```bash
gh release create v0.1.1 \
  dist/aim59-compat-0.1.1-linux.tar.gz \
  dist/aim59-patcher.pyz \
  dist/mciwave-wine9-x86-aim.dll \
  dist/aim-5.9.3861.yml \
  dist/SHA256SUMS \
  --title "AIM 5.9 Compatibility v0.1.1" \
  --notes "Terminal and Lutris installers for AIM 5.9.3861 on Wine 9.0."
```
