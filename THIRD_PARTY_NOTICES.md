# Third-party notices

## Wine `mciwave.dll`

`binaries/mciwave-wine9-x86-aim.dll` and
`binaries/mciwave-wine10-x86-aim.dll` are modified builds of the matching
Wine 9.0 and 10.0 `dlls/mciwave` components.

Wine is licensed under the GNU Lesser General Public License, version 2.1 or
(at your option) any later version. See `COPYING.LGPL-2.1`.

The corresponding source modification is provided in:

- `patches/wine-9.0-mciwave-aim.patch`
- `patches/wine-10.0-mciwave-aim.patch`
- `scripts/build-mciwave.sh`

The published binary in this starter repository has SHA-256:

- Wine 9.0: `23c52cbf2d9ebafc05a5abe10609a0ed49652445318ae8499bba2e1788c57df0`
- Wine 10.0: `17ba9b95d64fde4ad2d98abdbc623edaa7a66c6f3815221a16aa1f3d0fe30dd2`

Wine upstream:

- https://gitlab.winehq.org/wine/wine
- https://www.winehq.org/

## AOL Instant Messenger

This repository does **not** include or license AOL Instant Messenger.
AIM remains third-party proprietary software. At the user's request, the
patcher can retrieve AIM 5.9.3861 from an unaffiliated third-party archive or
a user-provided URL. Downloaded installers are hash-verified, cached outside
the repository, and are not project release assets.
