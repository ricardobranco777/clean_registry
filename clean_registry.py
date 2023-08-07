#!/usr/bin/env python3
"""
Docker Registry cleaner
"""

import os
import re
import shlex
import sys
import tarfile
import subprocess

from argparse import ArgumentParser
from glob import iglob
from io import BytesIO
from shutil import rmtree

from packaging.version import Version
from requests.exceptions import RequestException

import docker
from docker.errors import DockerException
from podman import PodmanClient
from podman.errors import APIError, PodmanError

import yaml

VERSION = "2.0.1"

REGISTRY_DIR = "REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY"

USAGE = f"""{sys.argv[0]} [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...
Options:
        -x, --remove    Remove the specified images or repositories.
        -q, --quiet     Supress non-error messages.
        -V, --version   Show version and exit.
        --dry-run       Don't remove anything.
        --podman        Use podman client (default).
        --docker        Use docker client (default is podman).
"""


def is_container() -> bool:
    '''Returns True if we're inside a Podman/Docker container, False otherwise.'''
    return os.getenv("container") == "podman" or os.path.isfile("/.dockerenv")


def remove_dir(path: str, quiet: bool = False, dry_run: bool = False) -> None:
    '''Run rmtree() in verbose mode'''
    if dry_run:
        print(f"directory {path} skipped due to dry-run")
        return
    rmtree(path)
    if not quiet:
        print(f"removed directory {path}")


def clean_revisions(repo: str, quiet: bool = False, dry_run: bool = False) -> None:
    '''Remove the revision manifests that are not present in the tags directory'''
    revisions = set(os.listdir(f"{repo}/_manifests/revisions/sha256/"))
    manifests = set(map(os.path.basename, iglob(f"{repo}/_manifests/tags/*/*/sha256/*")))
    revisions.difference_update(manifests)
    for revision in revisions:
        remove_dir(f"{repo}/_manifests/revisions/sha256/{revision}", quiet, dry_run)


def clean_tag(repo: str, tag: str, remove: bool = False, quiet: bool = False, dry_run: bool = False) -> bool:
    '''Clean a specific repo:tag'''
    link = f"{repo}/_manifests/tags/{tag}/current/link"
    if not os.path.isfile(link):
        print(f"ERROR: No such tag: {tag} in repository {repo}", file=sys.stderr)
        return False
    if remove:
        remove_dir(f"{repo}/_manifests/tags/{tag}", quiet, dry_run)
    else:
        with open(link, encoding="utf-8") as infile:
            current = infile.read()[len("sha256:"):]
        path = f"{repo}/_manifests/tags/{tag}/index/sha256/"
        for index in os.listdir(path):
            if index == current:
                continue
            remove_dir(f"{path}{index}", quiet, dry_run)
    clean_revisions(repo, quiet, dry_run)
    return True


def clean_repo(image: str, remove: bool = False, quiet: bool = False, dry_run: bool = False) -> bool:
    '''Clean all tags (or a specific one, if specified) from a specific repository'''
    repo, tag = image.split(":", 1) if ":" in image else (image, "")

    if not os.path.isdir(repo):
        print(f"ERROR: No such repository: {repo}", file=sys.stderr)
        return False

    if remove:
        tags = set(os.listdir(f"{repo}/_manifests/tags/"))
        if not tag or len(tags) == 1 and tag in tags:
            remove_dir(repo, quiet, dry_run)
            return True

    if tag:
        return clean_tag(repo, tag, remove, quiet, dry_run)

    currents = set()
    for link in iglob(f"{repo}/_manifests/tags/*/current/link"):
        with open(link, encoding="utf-8") as infile:
            currents.add(infile.read()[len("sha256:"):])
    for index in iglob(f"{repo}/_manifests/tags/*/index/sha256/*"):
        if os.path.basename(index) not in currents:
            remove_dir(index, quiet, dry_run)

    clean_revisions(repo, quiet, dry_run)
    return True


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

    return len(image) < 256 and tag_valid and repo_valid


class RegistryCleaner():
    '''Simple callable class for Docker Registry cleaning duties'''
    def __init__(self, container: str, use_docker=False):
        if use_docker:
            try:
                self.client = docker.from_env()
            except (RequestException, DockerException) as err:
                sys.exit(f"ERROR: {str(err)}")
        else:
            base_url = os.environ['DOCKER_HOST'] = os.getenv('DOCKER_HOST', 'unix:///run/podman/podman.sock')
            try:
                self.client = PodmanClient(base_url=base_url)
            except (APIError, PodmanError) as exc:
                sys.exit(f"Broken Podman environment: {exc}", file=sys.stderr)
            if not self.client.info()['host']['remoteSocket']["exists"]:
                sys.exit("Please run systemctl --user enable --now podman.socket", file=sys.stderr)

        try:
            self.container = self.client.containers.get(container)
            if use_docker:
                self.info = self.client.api.inspect_container(container)
            else:
                self.info = self.container.inspect()
        except (RequestException, DockerException, APIError, PodmanError) as err:
            sys.exit(f"ERROR: {str(err)}")

        if self.info['State']['Running']:
            sys.exit("ERROR: Please stop the container {container} before cleaning")

        _, distribution, version = self.get_image_version()
        if distribution != "github.com/docker/distribution" or Version(version) < Version("v2.4.0"):
            sys.exit("ERROR: You're not running Docker Registry 2.4.0+")

        self.registry_dir = self.get_registry_dir()
        os.environ[REGISTRY_DIR] = self.registry_dir

    def __call__(self, images: list[str], remove: bool = False, quiet: bool = False, dry_run: bool = False):
        try:
            os.chdir(f"{self.registry_dir}/docker/registry/v2/repositories")
        except OSError as err:
            sys.exit(f"ERROR: {str(err)}")

        images = images or map(os.path.dirname, iglob("**/_manifests", recursive=True))

        exit_status = 0
        for image in images:
            if not clean_repo(image, remove, quiet, dry_run):
                exit_status = 1

        if dry_run:
            print("Skipping the garbage collector")
        else:
            if not self.garbage_collect():
                exit_status = 1

        self.client.close()
        return exit_status

    def get_file(self, path: str) -> bytes:
        '''Returns the contents of the specified file from the container'''
        try:
            with BytesIO(b"".join(
                    _ for _ in self.container.get_archive(path)[0]
            )) as buf, tarfile.open(fileobj=buf) \
                    as tar, tar.extractfile(os.path.basename(path)) \
                    as infile:
                data = infile.read()
        except (RequestException, DockerException, APIError, PodmanError) as err:
            sys.exit(f"ERROR: {str(err)}")
        return data

    def get_registry_dir(self) -> str:
        '''Gets the Registry directory'''
        registry_dir = os.getenv(REGISTRY_DIR)
        if registry_dir:
            return registry_dir

        for env in self.info['Config']['Env']:
            var, value = env.split("=", 1)
            if var == REGISTRY_DIR:
                registry_dir = value
                break

        if not registry_dir:
            config_yml = self.info['Args'][0]
            data = yaml.load(self.get_file(config_yml), Loader=yaml.FullLoader)
            try:
                registry_dir = data['storage']['filesystem']['rootdirectory']
            except KeyError:
                sys.exit("ERROR: Unsupported storage driver")

        return registry_dir

    def get_image_version(self) -> list[str]:
        '''Gets the Docker distribution version running on the container'''
        try:
            if self.info['State']['Running']:
                data = self.container.exec_run("/bin/registry --version")
                if isinstance(data, tuple):  # podman
                    data = data[1]
                else:
                    data = data.output
            else:
                data = self.client.containers.run(
                    self.info['Config']['Image'], command="--version", remove=True
                )
            return data.decode('utf-8').split()
        except (RequestException, DockerException, APIError, PodmanError) as err:
            sys.exit(f"ERROR: {str(err)}")

    def garbage_collect(self, quiet: bool = False) -> bool:
        '''Runs garbage-collect'''
        command = "/bin/registry garbage-collect /etc/docker/registry/config.yml"
        with subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
        ) as proc:
            # It seems we have to consume stdout so we have a return code
            out = proc.stdout.read()
            if not quiet:
                print(out.decode('utf-8'))
        return bool(proc.returncode == 0)


def parse_args():
    """Parse args"""
    parser = ArgumentParser(usage=USAGE, add_help=False)
    parser.add_argument('-h', '--help', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-x', '--remove', action='store_true')
    parser.add_argument('-V', '--version', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--podman', default=True, action='store_true')
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('container', nargs='?')
    parser.add_argument('images', nargs='*')
    return parser.parse_args()


def main():
    '''Main function'''
    args = parse_args()
    if args.docker:
        args.podman = False
    if args.help:
        print(f'usage: {USAGE}')
        sys.exit(0)
    elif args.version:
        print(f'{sys.argv[0]} {VERSION}')
        sys.exit(0)
    elif not args.container:
        print(f'usage: {USAGE}')
        sys.exit(1)

    if not is_container():
        sys.exit("ERROR: This script should run inside a container!")

    for image in args.images:
        if not check_name(image):
            sys.exit(f"ERROR: Invalid Docker repository/tag: {image}")

    if args.remove and not args.images:
        sys.exit("ERROR: The -x option requires that you specify at least one repository...")

    status = RegistryCleaner(
        container=args.container,
        use_docker=args.docker,
    )(
        images=args.images,
        remove=args.remove,
        quiet=args.quiet,
        dry_run=args.dry_run,
    )
    sys.exit(status)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
