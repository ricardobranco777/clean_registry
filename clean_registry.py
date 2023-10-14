#!/usr/bin/env python3
"""
Docker Registry cleaner
"""

import argparse
import logging
import os
import re
import shlex
import sys
import subprocess

from shutil import rmtree


VERSION = "3.1.1"


def is_container() -> bool:
    """Returns True if we're inside a Podman/Docker container, False otherwise."""
    return os.getenv("container") == "podman" or os.path.isfile("/.dockerenv")


def check_name(image: str) -> bool:
    """Checks the whole repository:tag name"""
    repo, tag = image.split(":", 1) if ":" in image else (image, "latest")

    # From https://github.com/moby/moby/blob/master/image/spec/v1.2.md
    # Tag values are limited to the set of characters [a-zA-Z0-9_.-], except they may not start with a . or - character.
    # Tags are limited to 128 characters.
    #
    # From https://github.com/docker/distribution/blob/master/docs/spec/api.md
    # 1. A repository name is broken up into path components. A component of a repository name must be at least
    #    one lowercase, alpha-numeric characters, optionally separated by periods, dashes or underscores.
    #    More strictly, it must match the regular expression [a-z0-9]+(?:[._-][a-z0-9]+)*
    # 2. If a repository name has two or more path components, they must be separated by a forward slash ("/").
    # 3. The total length of a repository name, including slashes, must be less than 256 characters.

    # Note: Internally, distribution permits multiple dashes and up to 2 underscores as separators.
    # See https://github.com/docker/distribution/blob/master/reference/regexp.go

    tag_valid = len(tag) < 129 and re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", tag)
    repo_valid = all(
        re.fullmatch(r"[a-z0-9]+(?:(?:[._]|__|[-]*)[a-z0-9]+)*", path)
        for path in repo.split("/")
    )
    return bool(len(image) < 256 and tag_valid and repo_valid)


def run_command(command: list[str]) -> int:
    """Run command"""
    logging.info("Running %s", shlex.join(command))
    try:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,  # Line-buffered
            shell=False,
        ) as process:
            if process.stdout is not None:
                for line in process.stdout:
                    logging.info(line.rstrip())
        return process.returncode
    except OSError as exc:
        logging.error("%s", exc)
    return 1


def clean_registrydir(images: list[str], dry_run: bool = False) -> None:
    """Clean registry"""
    registry_dir = os.environ.get(
        "REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY", "/var/lib/registry"
    )
    logging.debug("registry directory: %s", registry_dir)
    basedir = f"{registry_dir}/docker/registry/v2/repositories"
    for image in images:
        clean_repo(basedir, image, dry_run)
    garbage_collect(dry_run)


def garbage_collect(dry_run: bool = False) -> None:
    """Runs garbage-collect"""
    command = shlex.split("/bin/registry garbage-collect --delete-untagged")
    if dry_run:
        command.append("--dry-run")
    command.append("/etc/docker/registry/config.yml")
    logging.debug("Running %s", shlex.join(command))
    status = run_command(command)
    if status != 0:
        logging.error("Command returned %d", status)


def remove_dir(directory: str, dry_run: bool = False) -> None:
    """Run rmtree() in verbose mode"""
    if dry_run:
        logging.info("directory %s skipped due to dry-run", directory)
        return
    rmtree(directory)
    logging.info("removed directory %s", directory)


def clean_tag(basedir: str, repo: str, tag: str, dry_run: bool = False) -> None:
    """Clean a specific repo:tag"""
    if not os.path.isfile(f"{basedir}/{repo}/_manifests/tags/{tag}/current/link"):
        logging.error("No such tag: %s in repository %s", tag, repo)
        return
    remove_dir(f"{basedir}/{repo}/_manifests/tags/{tag}", dry_run)


def clean_repo(basedir: str, image: str, dry_run: bool = False) -> None:
    """Clean all tags (or a specific one, if specified) from a specific repository"""
    repo, tag = image.split(":", 1) if ":" in image else (image, "")
    if not os.path.isdir(f"{basedir}/{repo}"):
        logging.error("No such repository: %s", repo)
        return
    # Remove repo if there's only one tag
    if not tag or [tag] == os.listdir(f"{basedir}/{repo}/_manifests/tags"):
        remove_dir(f"{basedir}/{repo}", dry_run)
        return
    if tag:
        clean_tag(basedir, repo, tag, dry_run)


def parse_args() -> argparse.Namespace:
    """Parse args"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="don't remove anything")
    parser.add_argument(
        "-l",
        "--log",
        default="info",
        choices="debug info warning error critical".split(),
        help="log level (default is info)",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("images", nargs="*", help="REPOSITORY:[TAG]")
    return parser.parse_args()


def main():
    """Main function"""
    if not is_container() or not os.path.isfile("/bin/registry"):
        sys.exit("ERROR: This script should run inside a registry:2 container!")

    args = parse_args()

    for image in args.images:
        if not check_name(image):
            sys.exit(f"ERROR: Invalid Docker repository/tag: {image}")

    fmt = "%(asctime)s %(levelname)-8s %(message)s"
    logging.basicConfig(format=fmt, stream=sys.stderr, level=args.log.upper())

    clean_registrydir(images=args.images, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
