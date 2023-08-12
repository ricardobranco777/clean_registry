#!/usr/bin/env python3
"""
Docker Registry cleaner
"""

import logging
import os
import re
import shlex
import sys
import subprocess

from argparse import ArgumentParser
from contextlib import chdir
from glob import iglob
from pathlib import Path
from shutil import rmtree


VERSION = "3.0"


def is_container() -> bool:
    '''Returns True if we're inside a Podman/Docker container, False otherwise.'''
    return os.getenv("container") == "podman" or os.path.isfile("/.dockerenv")


def check_name(image: str) -> bool:
    '''Checks the whole repository:tag name'''
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

    tag_valid = len(tag) < 129 and re.match(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]*$', tag)
    repo_valid = all(
        re.match(r'[a-z0-9]+(?:(?:[._]|__|[-]*)[a-z0-9]+)*$', path)
        for path in repo.split("/")
    )
    return bool(len(image) < 256 and tag_valid and repo_valid)


def run_command(command: list) -> int:
    '''Run command'''
    with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
    ) as proc:
        for line in proc.stdout:
            logging.info(line.decode('utf-8').rstrip())
        return proc.wait()


class RegistryCleaner():
    '''Simple callable class for Docker Registry cleaning duties'''
    def __init__(self):
        registry_dir = os.environ.get("REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY", "/var/lib/registry")
        logging.debug("registry directory: %s", registry_dir)
        self._basedir = Path(f"{registry_dir}/docker/registry/v2/repositories")

    def __call__(self, images: list[str], remove: bool = False, dry_run: bool = False) -> None:
        with chdir(self._basedir):
            images = images or map(os.path.dirname, iglob("**/_manifests"))
        for image in images:
            self.clean_repo(image, remove, dry_run)
        self.garbage_collect(dry_run)

    def garbage_collect(self, dry_run: bool = False) -> None:
        '''Runs garbage-collect'''
        command = shlex.split("/bin/registry garbage-collect --delete-untagged")
        if dry_run:
            command.append("--dry-run")
        command.append("/etc/docker/registry/config.yml")
        logging.debug("Running %s", shlex.join(command))
        status = run_command(command)
        if status != 0:
            logging.error("Command returned %d", status)

    def remove_dir(self, path: str, dry_run: bool = False) -> None:
        '''Run rmtree() in verbose mode'''
        if dry_run:
            logging.info("directory %s skipped due to dry-run", path)
            return
        rmtree(self._basedir / path)
        logging.info("removed directory %s", path)

    def clean_tag(self, repo: str, tag: str, remove: bool = False, dry_run: bool = False) -> None:
        '''Clean a specific repo:tag'''
        link = self._basedir / f"{repo}/_manifests/tags/{tag}/current/link"
        if not link.is_file():
            logging.error("No such tag: %s in repository %s", tag, repo)
            return
        if remove:
            self.remove_dir(f"{repo}/_manifests/tags/{tag}", dry_run)

    def clean_repo(self, image: str, remove: bool = False, dry_run: bool = False) -> None:
        '''Clean all tags (or a specific one, if specified) from a specific repository'''
        repo, tag = image.split(":", 1) if ":" in image else (image, "")
        repodir = self._basedir / repo
        if not repodir.is_dir():
            logging.error("No such repository: %s", repo)
            return
        # Remove repo if there's only one tag
        tagsdir = self._basedir / f"{repo}/_manifests/tags"
        if remove and (not tag or [tag] == list(tagsdir.iterdir())):
            self.remove_dir(repo, dry_run)
            return
        if tag:
            self.clean_tag(repo, tag, remove, dry_run)


def parse_args():
    """Parse args"""
    parser = ArgumentParser()
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Don't remove anything")
    parser.add_argument(
        '-l', '--log', default='info',
        choices='debug info warning error critical'.split(),
        help="Log level (default is info)")
    parser.add_argument(
        '-x', '--remove', action='store_true',
        help="Remove the specified images or repositories")
    parser.add_argument(
        '-V', '--version', action='store_true',
        help="Show version and exit")
    parser.add_argument('images', nargs='*', help="REPOSITORY:[TAG]")
    return parser.parse_args()


def print_versions():
    '''Print useful information for debugging'''
    print(f'{os.path.basename(sys.argv[0])} {VERSION}')
    print(f'Python {sys.version}')
    print(subprocess.check_output(shlex.split("/bin/registry --version")).decode("utf-8").strip())
    with open("/etc/os-release", encoding="utf-8") as file:
        osrel = {k: v.strip('"') for k, v in [line.split('=') for line in file.read().splitlines()]}
    print(osrel['NAME'], osrel['VERSION_ID'])


def main():
    '''Main function'''
    if not is_container() or not os.path.isfile("/bin/registry"):
        sys.exit("ERROR: This script should run inside a registry:2 container!")

    args = parse_args()
    if args.version:
        print_versions()
        sys.exit(0)

    for image in args.images:
        if not check_name(image):
            sys.exit(f"ERROR: Invalid Docker repository/tag: {image}")

    if args.remove and not args.images:
        sys.exit("ERROR: The -x option requires that you specify at least one repository...")

    fmt = "%(asctime)s %(levelname)-8s %(message)s"
    logging.basicConfig(format=fmt, stream=sys.stderr, level=args.log.upper())

    RegistryCleaner()(
        images=args.images,
        remove=args.remove,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
