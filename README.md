![Build Status](https://github.com/ricardobranco777/xwhich/actions/workflows/ci.yml/badge.svg)

# clean_registry

Clean the Docker Registry by removing untagged repositories and running the garbage collector in Docker Registry >= 2.4.0

Docker image available at `ghcr.io/ricardobranco777/clean_registry:latest`

The optional ``-x`` flag may be used to remove the specified repositories or tagged images.

NOTE:
With Docker Registry >= 2.7.0 you can run the garbage collector with the `-m` (`--delete-untagged`) option to remove untagged repositories but it doesn't work with multi-arch images as noted in this [bug](https://github.com/distribution/distribution/issues/3178).  The only workaround is to avoid multi-arch images and add the archictecture name to the tag.

This project is deprecated by [regview](https://github.com/ricardobranco777/regview/) which uses the Docker Registry API to delete manifests.

## NOTES:

- Make backups to avoid losing data.

- This script stops the Registry container during cleanup to prevent corruption, making it temporarily unavailable to clients.

- This script assumes the [filesystem](https://github.com/docker/distribution/blob/master/docs/configuration.md#storage) storage driver.

## Requirements

- Tested on Python 3.8+
- [docker-py](https://github.com/docker/docker-py/)

## Running standalone

This script may be run as stand-alone with Python 3.6+ (local Docker setups) or dockerized (which supports both local and remote Docker setups). To run stand-alone, the best is to run in virtualenv and install required packages via pip:

```bash
virtualenv --python=python3 .venv
. .venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

You may need to execute above commands as privileged user to access docker service (sudo + activate virtualenv).

## Usage

```
Usage: clean_registry.py [OPTIONS] VOLUME|CONTAINER [REPOSITORY[:TAG]]...
Options:
        -x, --remove    Remove the specified images or repositories.
        -q, --quiet     Supress non-error messages.
        -v, --volume    Specify a volume instead of container.
        -V, --version   Show version and exit.
```

## Docker usage with local Docker setup

```bash
docker run --rm --volumes-from CONTAINER -v /var/run/docker.sock:/var/run/docker.sock ricardobranco/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]] ...
```

## Docker usage with remote Docker setup

Make sure to read about [remote Docker setup](https://docs.docker.com/engine/security/https/#secure-by-default).

```bash
docker run --rm --volumes-from CONTAINER -e DOCKER_HOST -e DOCKER_TLS_VERIFY=1 -v /root/.docker:/root/.docker ricardobranco/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...
```

Note:

Paths other than ``/root/.docker`` path may be specified with the ``DOCKER_CERT_PATH`` environment variable.  In any case, your ``~/.docker/*.pem`` files should be in the server to be able to run as a client against itself.

## TODO

- Add unit tests and end-to-end tests
- Add Podman support
