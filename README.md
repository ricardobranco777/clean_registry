![Build Status](https://github.com/ricardobranco777/clean_registry/actions/workflows/ci.yml/badge.svg)

[![codecov](https://codecov.io/gh/ricardobranco777/clean_registry/branch/master/graph/badge.svg)](https://codecov.io/gh/ricardobranco777/clean_registry)

# clean_registry

Docker Registry cleanup and image removal tool.

Docker image for `linux/amd64` available at `ghcr.io/ricardobranco777/clean_registry:latest`

By default it performs a cleanup of untagged images with the help of the Docker Registry garbage collector or remove the specified repositories or tagged images.

## Usage

```bash
docker run --rm -v REGISTRY_DIRECTORY:/var/lib/registry ghcr.io/ricardobranco777/clean_registry [OPTIONS] [REPOSITORY[:TAG]] ...
```

## Options

```
  --dry-run      Don't remove anything
  -l {debug,info,warning,error,critical}, --log {debug,info,warning,error,critical}
                 Log level (default is info)
  -V, --version  Show version and exit
```

## BUGS / LIMITATIONS

- The `--delete-untagged` option added to [Docker Registry](https://github.com/distribution/distribution) does NOT work with multi-arch images as noted in this [bug](https://github.com/distribution/distribution/issues/3178).  The only workaround is to avoid multi-arch images completely and append the architecture name to the tag instead.
- Do NOT use it with sigstore/cosign as they [hijack](https://github.com/sigstore/cosign#registry-api-changes) the Registry API in the most obnoxious way by storing signatures as tags, also breaking in the process every registry listing tool.
- Only the [filesystem](https://github.com/docker/distribution/blob/master/docs/configuration.md#storage) storage driver is supported.

## Examples

```bash
# Run with --dry-run
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry --dry-run

# Cleanup of untagged images
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry registry

# Test remove tagged image with --dry-run
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry --dry-run old_image:latest

# Remove tagged image
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry old_image:latest

# Test remove whole repo (all tags) with --dry-run
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry --dry-run old_image

# Remove whole repo (all tags)
docker run --rm -v /path/to/registry:/var/lib/registry ghcr.io/ricardobranco777/clean_registry old_image
```
