# Release process

## Before release

```bash
make verify
make patcher
git status --short
git diff --check
```

Confirm there are no AOL/AIM binaries in Git history or the working tree.

Review `lutris/aim-5.9.3861.yml` and confirm that its versioned GitHub URLs
match the release tag.

## Suggested release assets

For v0.1.0:

```text
mciwave-wine9-x86-aim.dll
aim59-patcher.pyz
aim-5.9.3861.yml
SHA256SUMS
```

The GitHub Release should also link to the repository source at the matching
tag so the modified Wine binary's corresponding patch/build instructions are
readily available.

## Tag

Example:

```bash
git tag -a v0.1.0 -m "AIM 5.9 Wine compatibility v0.1.0"
git push origin v0.1.0
```

Create the release only after the tag and release assets have been reviewed.

## GitHub CLI example

```bash
gh release create v0.1.0 \
  binaries/mciwave-wine9-x86-aim.dll \
  dist/aim59-patcher.pyz \
  lutris/aim-5.9.3861.yml \
  checksums/SHA256SUMS \
  --title "AIM 5.9 Compatibility v0.1.0" \
  --notes "Initial Wine 9.0 / AIM 5.9.3861 compatibility release."
```
