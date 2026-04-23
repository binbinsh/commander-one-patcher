#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import plistlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SUPPORTED_SHORT_VERSION = "3.17.1"
SUPPORTED_BUILD_VERSION = "3990"
SUPPORTED_ARM64_SHA256 = (
    "17c3b6060e28333568606103a19dbea3940cea00ab903e137ee6d5acd28fa064"
)

APP_BUNDLE_REL_BINARY = Path("Contents/MacOS/Commander One")
APP_BUNDLE_REL_INFO_PLIST = Path("Contents/Info.plist")
USER_PREFS_PATH = Path("~/Library/Preferences/com.eltima.cmd1.plist").expanduser()
USER_SAVED_STATE_PATH = Path(
    "~/Library/Saved Application State/com.eltima.cmd1.savedState"
).expanduser()

ARM64_TEXT_BASE = 0x100000000
ARM64_NOP = bytes.fromhex("1f2003d5")


@dataclass(frozen=True)
class BinaryPatch:
    name: str
    vmaddr: int
    expected_hex: str
    replacement_hex: str

    @property
    def file_offset(self) -> int:
        return self.vmaddr - ARM64_TEXT_BASE

    @property
    def expected(self) -> bytes:
        return bytes.fromhex(self.expected_hex)

    @property
    def replacement(self) -> bytes:
        return bytes.fromhex(self.replacement_hex)


PATCHES = (
    BinaryPatch(
        name="disable_save_left_tabs",
        vmaddr=0x100106868,
        expected_hex="40078052e10314aa6d000094",
        replacement_hex=(ARM64_NOP * 3).hex(),
    ),
    BinaryPatch(
        name="disable_save_right_tabs",
        vmaddr=0x100106898,
        expected_hex="60078052e10314aa61000094",
        replacement_hex=(ARM64_NOP * 3).hex(),
    ),
)


def run(cmd: list[str], *, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"missing required tool: {name}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_info_plist(app_path: Path) -> dict:
    with (app_path / APP_BUNDLE_REL_INFO_PLIST).open("rb") as f:
        return plistlib.load(f)


def app_is_running(app_name: str = "Commander One") -> bool:
    cp = run(["pgrep", "-x", app_name], check=False, capture_output=True)
    return bool(cp.stdout.strip())


def copy_app_bundle(source_app: Path, output_app: Path) -> None:
    output_app.parent.mkdir(parents=True, exist_ok=True)
    if output_app.exists():
        shutil.rmtree(output_app)
    run(["ditto", str(source_app), str(output_app)])


def extract_arch_slice(universal_binary: Path, arch: str, out_path: Path) -> None:
    run(["lipo", str(universal_binary), "-thin", arch, "-output", str(out_path)])


def read_archs(universal_binary: Path) -> list[str]:
    cp = run(["lipo", "-archs", str(universal_binary)], capture_output=True)
    return cp.stdout.strip().split()


def patch_arm64_binary(arm64_binary: Path) -> None:
    data = bytearray(arm64_binary.read_bytes())

    for patch in PATCHES:
        start = patch.file_offset
        end = start + len(patch.expected)
        current = bytes(data[start:end])
        if current != patch.expected:
            raise SystemExit(
                f"byte mismatch for {patch.name} at 0x{patch.file_offset:x}: "
                f"expected {patch.expected.hex()}, got {current.hex()}"
            )
        data[start:end] = patch.replacement

    arm64_binary.write_bytes(data)
    arm64_binary.chmod(0o755)


def verify_arm64_binary(arm64_binary: Path) -> None:
    data = arm64_binary.read_bytes()
    for patch in PATCHES:
        start = patch.file_offset
        end = start + len(patch.replacement)
        current = data[start:end]
        if current != patch.replacement:
            raise SystemExit(
                f"verification failed for {patch.name} at 0x{patch.file_offset:x}: "
                f"expected {patch.replacement.hex()}, got {current.hex()}"
            )


def rebuild_universal_binary(binary_path: Path) -> None:
    archs = read_archs(binary_path)
    if "arm64" not in archs:
        raise SystemExit("source binary does not contain an arm64 slice")

    with tempfile.TemporaryDirectory(prefix="commander-one-patch-") as tmpdir_name:
        tmpdir = Path(tmpdir_name)
        slices: dict[str, Path] = {}

        for arch in archs:
            slice_path = tmpdir / f"{arch}.bin"
            extract_arch_slice(binary_path, arch, slice_path)
            slices[arch] = slice_path

        arm64_hash = sha256_file(slices["arm64"])
        if arm64_hash != SUPPORTED_ARM64_SHA256:
            raise SystemExit(
                "unsupported arm64 slice hash:\n"
                f"  expected: {SUPPORTED_ARM64_SHA256}\n"
                f"  actual:   {arm64_hash}"
            )

        patch_arm64_binary(slices["arm64"])
        verify_arm64_binary(slices["arm64"])

        rebuilt_binary = tmpdir / "Commander One.universal"
        lipo_cmd = ["lipo", "-create"]
        lipo_cmd.extend(str(slices[arch]) for arch in archs)
        lipo_cmd.extend(["-output", str(rebuilt_binary)])
        run(lipo_cmd)

        shutil.copy2(rebuilt_binary, binary_path)
        binary_path.chmod(0o755)


def ad_hoc_sign(app_path: Path) -> None:
    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            "-",
            "--timestamp=none",
            str(app_path),
        ]
    )
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)])
    run(["xattr", "-dr", "com.apple.quarantine", str(app_path)], check=False)


def sanitize_user_prefs() -> Path:
    backup_path = USER_PREFS_PATH.with_name(
        f"{USER_PREFS_PATH.name}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    prefs: dict
    if USER_PREFS_PATH.exists():
        shutil.copy2(USER_PREFS_PATH, backup_path)
        with USER_PREFS_PATH.open("rb") as f:
            prefs = plistlib.load(f)
    else:
        prefs = {}

    def local_tab() -> dict:
        home = str(Path.home())
        return {
            "bundle": False,
            "symlink": False,
            "directory": True,
            "label": f"Macintosh HD{home}",
            "path": home,
            "options": {"path": "/", "DAVolumeName": "Macintosh HD"},
            "name": "TCXLocalFS",
        }

    def normalize_tabs(value: object) -> list[dict]:
        if not isinstance(value, list) or not value:
            return [local_tab()]

        first = value[0]
        if not isinstance(first, dict):
            return [local_tab()]

        if first.get("name") != "TCXLocalFS":
            return [local_tab()]

        path = first.get("path")
        if not isinstance(path, str) or not Path(path).exists():
            return [local_tab()]

        return value

    prefs["SavedLeftTabs"] = normalize_tabs(prefs.get("SavedLeftTabs"))
    prefs["SavedRightTabs"] = normalize_tabs(prefs.get("SavedRightTabs"))
    prefs["TCXPreferencesWindow-misc-save-folders"] = False
    prefs["TCXPreferencesWindow-misc-save-panel-state"] = False

    with USER_PREFS_PATH.open("wb") as f:
        plistlib.dump(prefs, f)

    return backup_path


def clear_saved_state() -> None:
    if USER_SAVED_STATE_PATH.exists():
        shutil.rmtree(USER_SAVED_STATE_PATH)


def default_backup_path(app_path: Path) -> Path:
    return app_path.with_name(
        f"{app_path.name}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )


def install_app_bundle(staged_app: Path, target_app: Path, *, backup_app: Path | None, force: bool) -> None:
    if target_app.exists() and backup_app is None:
        if not force:
            raise SystemExit(
                f"output app already exists: {target_app}\n"
                "rerun with --force to overwrite it"
            )
        shutil.rmtree(target_app)
        run(["ditto", str(staged_app), str(target_app)])
        return

    if backup_app is None:
        run(["ditto", str(staged_app), str(target_app)])
        return

    if app_is_running():
        raise SystemExit(
            "Commander One is currently running. Close it first before replacing "
            "/Applications/Commander One.app."
        )

    if backup_app.exists():
        if not force:
            raise SystemExit(
                f"backup app already exists: {backup_app}\n"
                "rerun with --force to overwrite the existing backup"
            )
        shutil.rmtree(backup_app)

    moved_original = False
    try:
        run(["mv", str(target_app), str(backup_app)])
        moved_original = True
        run(["ditto", str(staged_app), str(target_app)])
    except Exception:
        if target_app.exists():
            shutil.rmtree(target_app)
        if moved_original and backup_app.exists():
            run(["mv", str(backup_app), str(target_app)], check=False)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch Commander One.app in place by default, disabling only "
            "SavedLeftTabs/SavedRightTabs persistence."
        )
    )
    parser.add_argument(
        "--source-app",
        default="/Applications/Commander One.app",
        help="path to the original Commander One.app bundle",
    )
    parser.add_argument(
        "--output-app",
        default="/Applications/Commander One.app",
        help="path for the patched app; defaults to replacing the original app",
    )
    parser.add_argument(
        "--backup-app",
        help=(
            "backup path used when replacing the original app in place; "
            "defaults to /Applications/Commander One.app.backup-<timestamp>"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing output app or backup app if needed",
    )
    parser.add_argument(
        "--sanitize-prefs",
        action="store_true",
        help=(
            "normalize SavedLeftTabs/SavedRightTabs to local tabs in the current "
            "user's preferences and force the save-* toggles off"
        ),
    )
    parser.add_argument(
        "--clear-saved-state",
        action="store_true",
        help="remove ~/Library/Saved Application State/com.eltima.cmd1.savedState",
    )
    return parser.parse_args()


def main() -> int:
    for tool in ("ditto", "lipo", "codesign", "xattr"):
        require_tool(tool)

    args = parse_args()

    source_app = Path(args.source_app).expanduser().resolve()
    output_app = Path(args.output_app).expanduser().resolve()

    if not source_app.is_dir():
        raise SystemExit(f"source app not found: {source_app}")

    info = load_info_plist(source_app)
    short_version = str(info.get("CFBundleShortVersionString", ""))
    build_version = str(info.get("CFBundleVersion", ""))

    if short_version != SUPPORTED_SHORT_VERSION or build_version != SUPPORTED_BUILD_VERSION:
        raise SystemExit(
            "unsupported Commander One version:\n"
            f"  expected: {SUPPORTED_SHORT_VERSION} ({SUPPORTED_BUILD_VERSION})\n"
            f"  actual:   {short_version} ({build_version})"
        )

    backup_app = None
    if output_app == source_app:
        backup_app = (
            Path(args.backup_app).expanduser().resolve()
            if args.backup_app
            else default_backup_path(output_app)
        )

    with tempfile.TemporaryDirectory(prefix="commander-one-stage-") as tmpdir_name:
        staged_app = Path(tmpdir_name) / source_app.name
        copy_app_bundle(source_app, staged_app)
        rebuild_universal_binary(staged_app / APP_BUNDLE_REL_BINARY)
        ad_hoc_sign(staged_app)
        install_app_bundle(staged_app, output_app, backup_app=backup_app, force=args.force)

    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(output_app)])
    run(["xattr", "-dr", "com.apple.quarantine", str(output_app)], check=False)

    prefs_backup = None
    if args.sanitize_prefs:
        prefs_backup = sanitize_user_prefs()
    if args.clear_saved_state:
        clear_saved_state()

    print("patched app ready:")
    print(f"  {output_app}")
    if backup_app is not None:
        print("original app backup:")
        print(f"  {backup_app}")
    print()
    print("patched arm64 behaviors:")
    print("  - disable save of SavedLeftTabs")
    print("  - disable save of SavedRightTabs")
    if prefs_backup is not None:
        print()
        print("user preferences sanitized:")
        print(f"  backup: {prefs_backup}")
        print(f"  file:   {USER_PREFS_PATH}")
    if args.clear_saved_state:
        print()
        print(f"saved-state cleared: {USER_SAVED_STATE_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
