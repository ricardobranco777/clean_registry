![Build Status](https://github.com/ricardobranco777/registry_clean/actions/workflows/ci.yml/badge.svg)

# clean_registry

Clean the Docker Registry by removing untagged repositories and running the garbage collector in Docker Registry >= 2.4.0

Docker image for `linux/amd64` available at `ghcr.io/ricardobranco777/clean_registry:latest`

The optional `-x` flag may be used to remove the specified repositories or tagged images.

NOTE:
With Docker Registry >= 2.7.0 you can run the garbage collector with the `-m` (`--delete-untagged`) option to remove untagged repositories but it doesn't work with multi-arch images as noted in this [bug](https://github.com/distribution/distribution/issues/3178).  The only workaround is to avoid multi-arch images and append the archictecture name to the tag.

## NOTES:

- Make backups to avoid losing data!!!

- You must stop the Registry container before cleanup and start it afterwards.

- This script assumes the [filesystem](https://github.com/docker/distribution/blob/master/docs/configuration.md#storage) storage driver.

## Requirements

- Podman or Docker to run the image

## Usage

```
Usage: clean_registry.py [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...
Options:
        -x, --remove    Remove the specified images or repositories.
        -q, --quiet     Supress non-error messages.
        -V, --version   Show version and exit.
        --dry-run       Don't remove anything.
        --podman        Use podman client (default).
        --docker        Use docker client (default is podman).
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

## Podman

`alias docker=podman`

## TODO

- Add unit tests
