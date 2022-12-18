import argparse
import hashlib
import json
import os
import sys
import tarfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, NamedTuple

from mypy_extensions import TypedDict

ManifestFile = TypedDict("ManifestFile", {"path": str, "checksum": str})
Manifest = TypedDict(
    "Manifest",
    {
        "archive_name": str,
        "checksum": str,
        "checksum_algorithm": str,
        "creation_time": int,
        "files": List[ManifestFile],
    },
)


class ChecksumMismatch(NamedTuple):
    generated: str
    expected: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    backup_parser = subparsers.add_parser("backup", help="Backup a given directory")
    backup_parser.add_argument("path", type=Path, help="Path to backup")
    backup_parser.add_argument("archive_name", type=Path, help="Desired archive name")
    backup_parser.add_argument(
        "--checksum-algorithm",
        choices=hashlib.algorithms_available,
        default="sha1",
        help="Checksum algorithm to use (default is %(default)s",
    )
    backup_parser.set_defaults(cmd=cmd_backup)

    restore_parser = subparsers.add_parser(
        "restore", help="Restore a backup of a given directory"
    )
    restore_parser.add_argument(
        "manifest", type=Path, help="Manifest file for the backup"
    )
    restore_parser.add_argument("path", type=Path, help="Path to restore backup to")
    restore_parser.set_defaults(cmd=cmd_restore)

    return parser.parse_args()


@contextmanager
def cd(path: Path):
    old_path = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)


def generate_checksum(filename: Path, checksum_algorithm: str) -> str:
    with filename.open("rb") as f:
        file_bytes = f.read()

    checksum = hashlib.new(checksum_algorithm)
    checksum.update(file_bytes)
    return checksum.hexdigest()


def tar_files(output_path: Path, paths: List[Path]) -> None:
    with tarfile.open(f"{output_path}.tar.gz", "w:gz") as tar:
        for path in paths:
            tar.add(str(path))


def cmd_backup(args: argparse.Namespace) -> int:
    manifest: Manifest = {
        "archive_name": f"{args.archive_name}.tar.gz",
        "checksum": "",
        "checksum_algorithm": args.checksum_algorithm,
        "creation_time": int(time.time()),
        "files": [],
    }

    paths_to_backup = []

    cwd = Path.cwd()
    for directory, dirnames, filenames in os.walk(args.path):
        directory_path = Path(directory)

        for filename in filenames:
            file_path = directory_path / filename
            relative_path = file_path.resolve().relative_to(cwd)

            paths_to_backup.append(relative_path)

            manifest["files"].append(
                {
                    "path": str(relative_path),
                    "checksum": generate_checksum(
                        directory_path / filename, manifest["checksum_algorithm"]
                    ),
                }
            )

    tar_files(args.archive_name, paths_to_backup)

    manifest["checksum"] = generate_checksum(
        Path(manifest["archive_name"]), manifest["checksum_algorithm"]
    )

    with open(f"{args.archive_name}.manifest", "w") as f:
        json.dump(manifest, f, sort_keys=True, indent=4)

    return os.EX_OK


def cmd_restore(args: argparse.Namespace) -> int:
    with args.manifest.open("r") as f:
        manifest: Manifest = json.load(f)

    generated_checksum = generate_checksum(
        Path(manifest["archive_name"]), manifest["checksum_algorithm"]
    )
    if generated_checksum != manifest["checksum"]:
        print(
            f"Mismatched archive checksums. Expected: {manifest['checksum']}, "
            f"generated {generated_checksum}",
            file=sys.stderr,
        )
        return os.EX_DATAERR

    with tarfile.open(manifest["archive_name"], "r:gz") as tar, cd(args.path):
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(tar)

    path_checksums = {f["path"]: f["checksum"] for f in manifest["files"]}

    bad_checksums = {}
    restored_paths = set()

    for directory, dirnames, filenames in os.walk(args.path):
        directory_path = Path(directory)

        for filename in filenames:
            relative_path = (directory_path / filename).relative_to(args.path)
            relative_path_str = str(relative_path)

            expected_checksum = path_checksums.get(relative_path_str)
            if expected_checksum is None:
                continue

            generated_checksum = generate_checksum(
                relative_path, manifest["checksum_algorithm"]
            )
            if generated_checksum != expected_checksum:
                bad_checksums[relative_path] = ChecksumMismatch(
                    generated_checksum, expected_checksum
                )
                continue

            restored_paths.add(relative_path_str)

    missing_paths = set()
    for path_str in path_checksums:
        if path_str not in restored_paths:
            missing_paths.add(path_str)

    failed = False
    if bad_checksums:
        messages = []
        for path in sorted(bad_checksums):
            mismatch = bad_checksums[path]
            messages.append(
                f"{path}: expected {mismatch.expected}, got {mismatch.generated}"
            )
        print("Bad checksums: {}".format("\n".join(messages)), file=sys.stderr)
        failed = True

    if missing_paths:
        print(
            "Missing paths: {}".format(", ".join(sorted(missing_paths))),
            file=sys.stderr,
        )
        failed = True

    if failed:
        print("Backup restoration failed", file=sys.stderr)
        return os.EX_DATAERR

    print("Backup restored successfully")
    return os.EX_OK


def main() -> int:
    args = parse_args()

    if not hasattr(args, "cmd"):
        print(
            "Please specify a command. Run with --help for more information.",
            file=sys.stderr,
        )
        return os.EX_USAGE

    return args.cmd(args)


if __name__ == "__main__":
    sys.exit(main())
