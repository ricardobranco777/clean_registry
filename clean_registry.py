#!/usr/bin/env python3
"""
This script purges untagged repositories and runs the garbage collector in Docker Registry >= 2.4.0.
It works on the whole registry or the specified repositories.
The optional -x flag may be used to completely remove the specified repositories or tagged images.

NOTES:
  - This script stops the Registry container during cleanup to prevent corruption,
    making it temporarily unavailable to clients.
  - This script assumes local storage (the filesystem storage driver).
  - This script may run stand-alone (on local setups) or dockerized (which supports remote Docker setups).
  - This script is Python 3 only.

v1.6.1 by Ricardo Branco

MIT License
"""

import os
import re
import shlex
import sys
import tarfile
import subprocess

from argparse import ArgumentParser
from distutils.version import LooseVersion
from glob import iglob
from io import BytesIO
from shutil import rmtree
from requests.exceptions import RequestException

import docker
from docker.errors import DockerException

import yaml

VERSION = "1.6.1"
REGISTRY_DIR = "REGISTRY_STORAGE_FILESYSTEM_ROOTREGISTRY_DIR"
args = None


os.environ['LC_ALL'] = 'C.UTF-8'


def dockerized():
    '''Returns True if we're inside a Docker container, False otherwise.'''
    return os.path.isfile("/.dockerenv")


def remove(path):
    '''Run rmtree() in verbose mode'''
    rmtree(path)
    if not args.quiet:
        print(f"removed directory {path}")


def clean_revisions(repo):
    '''Remove the revision manifests that are not present in the tags directory'''
    revisions = set(os.listdir(f"{repo}/_manifests/revisions/sha256/"))
    manifests = set(map(os.path.basename, iglob(f"{repo}/_manifests/tags/*/*/sha256/*")))
    revisions.difference_update(manifests)
    for revision in revisions:
        remove(f"{repo}/_manifests/revisions/sha256/{revision}")


def clean_tag(repo, tag):
    '''Clean a specific repo:tag'''
    link = f"{repo}/_manifests/tags/{tag}/current/link"
    if not os.path.isfile(link):
        print(f"ERROR: No such tag: {tag} in repository {repo}", file=sys.stderr)
        return False
    if args.remove:
        remove(f"{repo}/_manifests/tags/{tag}")
    else:
        with open(link) as infile:
            current = infile.read()[len("sha256:"):]
        path = f"{repo}/_manifests/tags/{tag}/index/sha256/"
        for index in os.listdir(path):
            if index == current:
                continue
            remove(f"{path}{index}")
    clean_revisions(repo)
    return True


def clean_repo(image):
    '''Clean all tags (or a specific one, if specified) from a specific repository'''
    repo, tag = image.split(":", 1) if ":" in image else (image, "")

    if not os.path.isdir(repo):
        print(f"ERROR: No such repository: {repo}", file=sys.stderr)
        return False

    if args.remove:
        tags = set(os.listdir(f"{repo}/_manifests/tags/"))
        if not tag or len(tags) == 1 and tag in tags:
            remove(repo)
            return True

    if tag:
        return clean_tag(repo, tag)

    currents = set()
    for link in iglob(f"{repo}/_manifests/tags/*/current/link"):
        with open(link) as infile:
            currents.add(infile.read()[len("sha256:"):])
    for index in iglob(f"{repo}/_manifests/tags/*/index/sha256/*"):
        if os.path.basename(index) not in currents:
            remove(index)

    clean_revisions(repo)
    return True


def check_name(image):
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

    return len(image) < 256 and len(tag) < 129 and \
        re.match('[a-zA-Z0-9_][a-zA-Z0-9_.-]*$', tag) and \
        all(re.match('[a-z0-9]+(?:(?:[._]|__|[-]*)[a-z0-9]+)*$', path)
            for path in repo.split("/"))


class RegistryCleaner():
    '''Simple callable class for Docker Registry cleaning duties'''
    def __init__(self, container=None, volume=None):
        try:
            self.docker = docker.from_env()
        except (RequestException, DockerException) as err:
            sys.exit(f"ERROR: {str(err)}")

        if container is None:
            self.container = None
            try:
                self.volume = self.docker.volumes.get(volume)
                self.registry_dir = self.volume.attrs['Mountpoint']
            except (RequestException, DockerException) as err:
                sys.exit(f"ERROR: {str(err)}")
            if dockerized():
                try:
                    self.registry_dir = os.environ[REGISTRY_DIR]
                except KeyError:
                    self.registry_dir = "/var/lib/registry"
            return

        try:
            self.info = self.docker.api.inspect_container(container)
            self.container = self.info['Id']
        except (RequestException, DockerException) as err:
            sys.exit(f"ERROR: {str(err)}")

        if not self.info['Config']['Image'].startswith("registry:2"):
            sys.exit(f"ERROR: The container {container} is not running the registry:2 image")

        if LooseVersion(self.get_image_version()) < LooseVersion("v2.4.0"):
            sys.exit("ERROR: You're not running Docker Registry 2.4.0+")

        self.registry_dir = self.get_registry_dir()

        if dockerized():
            os.environ[REGISTRY_DIR] = self.registry_dir

    def __call__(self):
        try:
            os.chdir(f"{self.registry_dir}/docker/registry/v2/repositories")
        except OSError as err:
            sys.exit(f"ERROR: {str(err)}")

        if self.container is not None:
            self.docker.api.stop(self.container)

        images = args.images or \
            map(os.path.dirname, iglob("**/_manifests", recursive=True))

        exit_status = 0
        for image in images:
            if not clean_repo(image):
                exit_status = 1

        if not self.garbage_collect():
            exit_status = 1

        if self.container is not None:
            try:
                self.docker.api.start(self.container)
            except (RequestException, DockerException):
                pass  # Ignore error if we try to start a stopped container

        self.docker.close()
        return exit_status

    def get_file(self, path):
        '''Returns the contents of the specified file from the container'''
        try:
            with BytesIO(b"".join(
                    _ for _ in self.docker.api.get_archive(self.container, path)[0]
            )) as buf, tarfile.open(fileobj=buf) \
                    as tar, tar.extractfile(os.path.basename(path)) \
                    as infile:
                data = infile.read()
        except (RequestException, DockerException) as err:
            sys.exit(f"ERROR: {str(err)}")
        return data

    def get_registry_dir(self):
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
                driver = [
                    _ for _ in 'azure gcs inmemory oss s3 swift'.split()
                    if _ in data['storage']
                ][0]
                sys.exit(f"ERROR: Unsupported storage driver: {driver}")

        if dockerized():
            return registry_dir

        for item in self.info['Mounts']:
            if item['Destination'] == registry_dir:
                return item['Source']
        return None

    def get_image_version(self):
        '''Gets the Docker distribution version running on the container'''
        try:
            if self.info['State']['Running']:
                data = self.docker.containers.get(
                    self.container
                ).exec_run("/bin/registry --version").output
            else:
                data = self.docker.containers.run(
                    self.info['Config']['Image'], command="--version", remove=True
                )
            return data.decode('utf-8').split()[2]
        except (RequestException, DockerException) as err:
            sys.exit(f"ERROR: {str(err)}")

    def garbage_collect(self):
        '''Runs garbage-collect'''
        command = "garbage-collect /etc/docker/registry/config.yml"
        if dockerized():
            command = f"/bin/registry {command}"
            with subprocess.Popen(
                    shlex.split(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT
            ) as proc:
                # It seems we have to consume stdout so we have a return code
                out = proc.stdout.read()
                if not args.quiet:
                    print(out.decode('utf-8'))
            status = bool(proc.returncode == 0)
        else:
            cli = self.docker.containers.run(
                "registry:2",
                command=command,
                detach=True,
                stderr=True,
                volumes={
                    self.registry_dir: {
                        'bind': "/var/lib/registry",
                        'mode': "rw"
                    }
                }
            )
            if not args.quiet:
                for line in cli.logs(stream=True):
                    print(line.decode('utf-8'), end="")
            status = bool(cli.wait()['StatusCode'] == 0)
            cli.remove()
        return status


def main():
    '''Main function'''
    progname = os.path.basename(sys.argv[0])
    usage = f"\rUsage: {progname} [OPTIONS] VOLUME|CONTAINER [REPOSITORY[:TAG]]..." + """
Options:
        -x, --remove    Remove the specified images or repositories.
        -v, --volume    Specify a volume instead of container.
        -q, --quiet     Supress non-error messages.
        -V, --version   Show version and exit."""

    parser = ArgumentParser(usage=usage, add_help=False)
    parser.add_argument('-h', '--help', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-x', '--remove', action='store_true')
    parser.add_argument('-v', '--volume', action='store_true')
    parser.add_argument('-V', '--version', action='store_true')
    parser.add_argument('container_or_volume', nargs='?')
    parser.add_argument('images', nargs='*')
    global args
    args = parser.parse_args()

    if args.help:
        print(f'usage: {usage}')
        sys.exit(0)
    elif args.version:
        print(f'{progname} {VERSION}')
        sys.exit(0)
    elif not args.container_or_volume:
        print(f'usage: {usage}')
        sys.exit(1)

    for image in args.images:
        if not check_name(image):
            sys.exit(f"ERROR: Invalid Docker repository/tag: {image}")

    if args.remove and not args.images:
        sys.exit("ERROR: The -x option requires that you specify at least one repository...")

    if args.volume:
        cleaner = RegistryCleaner(volume=args.container_or_volume)
    else:
        cleaner = RegistryCleaner(container=args.container_or_volume)

    sys.exit(cleaner())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
