# Commander One Patcher

Small local tools for patching and translating `Commander One.app`.

## What It Does

- `patch-commander-one.py`
  Patches the app binary so Commander One no longer persists
  `SavedLeftTabs` and `SavedRightTabs`. This avoids slow launches caused by
  restoring remote tabs. It can also sanitize the current user's preferences
  and clear macOS saved state.
- `update-translation.sh`
  Replaces the app's `zh-Hans.lproj` with the translation files from this
  repo, then re-signs the app.

## Supported Build

- `Commander One 3.17.1 (3990)`
- `arm64` slice SHA-256:
  `17c3b6060e28333568606103a19dbea3940cea00ab903e137ee6d5acd28fa064`

## Usage

```bash
cd ~/Projects/Personal/commander-one-patcher

./patch-commander-one.py --sanitize-prefs --clear-saved-state
bash ./update-translation.sh
```

Defaults:

- Both scripts target `/Applications/Commander One.app`.
- The app must be closed before running them.
- The app is re-signed after changes.
- The patch script creates an app backup when replacing in place.

Run `--help` on either script for the full options list.
