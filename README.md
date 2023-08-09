![Build Status](https://github.com/ricardobranco777/clean_registry/actions/workflows/ci.yml/badge.svg)

# clean_registry

Docker Registry cleanup and image removal tool.

Docker image for `linux/amd64` available at `ghcr.io/ricardobranco777/clean_registry:latest`

By default it performs a cleanup of untagged images with the help of the Docker Registry garbage collector.  The optional `-x` flag may be used to remove the specified repositories or tagged images.

## Usage

```bash
docker run --rm --volumes-from CONTAINER [DOCKER_OPTIONS...] ghcr.io/ricardobranco777/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]] ...
```

## Options

```
  --dry-run      Don't remove anything
  -l {debug,info,warning,error,critical}, --log {debug,info,warning,error,critical}
                 Log level (default is info)
  -x, --remove   Remove the specified images or repositories
  -V, --version  Show version and exit
```

## BUGS / LIMITATIONS

- The `--delete-untagged` option added to [Docker Registry](https://github.com/distribution/distribution) does NOT work with multi-arch images as noted in this [bug](https://github.com/distribution/distribution/issues/3178).  The only workaround is to avoid multi-arch images completely and append the architecture name to the tag instead.
- Do NOT use it with sigstore/cosign as they [hijack](https://github.com/sigstore/cosign#registry-api-changes) the Registry API in the most obnoxious way by storing signatures as tags, also breaking in the process every registry listing tool.
- Only the [filesystem](https://github.com/docker/distribution/blob/master/docs/configuration.md#storage) storage driver is supported.

## Examples

### With local Docker setup

```bash
# Run with --dry-run
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry --dry-run registry

# Cleanup of untagged images
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry registry

# Test remove tagged image with --dry-run
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry --dry-run -x registry old_image:latest

# Remove tagged image
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry -x registry old_image:latest

# Test remove whole repo (all tags) with --dry-run
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry --dry-run -x registry old_image

# Remove whole repo (all tags)
docker run --rm --volumes-from registry -v /var/run/docker.sock:/var/run/docker.sock ghcr.io/ricardobranco777/clean_registry -x registry old_image
```

NOTES:
- To directly work on a directory you can specify a null container as empty string:

`docker run --rm -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/some/directory ghcr.io/ricardobranco777/clean_registry [--dry-run] [-x] "" [REPOSITORY[:TAG]...`

- The path to the socket can be found with:

`docker context inspect -f json default | jq -r '.[0].Endpoints.docker.Host'`

### With [remote Docker setup](https://docs.docker.com/engine/security/protect-access/)

```bash
docker run --rm --volumes-from registry -e DOCKER_HOST -e DOCKER_TLS_VERIFY=1 -v /root/.docker:/root/.docker ghcr.io/ricardobranco777/clean_registry [OPTIONS] registry [REPOSITORY[:TAG]]...
```

NOTES:
- Paths other than ``/root/.docker`` path may be specified with the ``DOCKER_CERT_PATH`` environment variable.
- Docker environment variables are documented [here](https://docs.docker.com/engine/reference/commandline/cli/#environment-variables).

### With [Podman](https://podman.io/)

```bash
PODMAN_SOCKET="$(podman info --format json | jq -r '.host.remoteSocket.path')"
export CONTAINER_HOST="$PODMAN_SOCKET"
PODMAN_SOCKET="${PODMAN_SOCKET#unix://}"

podman run --rm --volumes-from registry -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/var/registry -e CONTAINER_HOST -v "$PODMAN_SOCKET:$PODMAN_SOCKET" ghcr.io/ricardobranco777/clean_registry [OPTIONS] registry [REPOSITORY[:TAG]]...
```

NOTES:
- Specifying `REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY` with the path used by the container registry is needed because of this [bug](https://github.com/containers/podman/issues/19529).
- With rootless `podman` you can't clean up a registry container running on Docker because the socket and files are owned by root.  You can use `docker` to remove a registry in `podman` though, provided that you use the `CONTAINER_HOST` environment variable and mount the Podman socket.
