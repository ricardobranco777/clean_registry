# clean_registry
Clean the Docker Registry by removing untagged repositories and running the garbage collector in Docker Registry >= 2.4.0

The optional `-x` flag may be used to remove the specified repositories or tagged images.

NOTES:
  - This script stops the Registry container during cleanup to prevent corruption, making it temporarily unavailable to clients.
  - This script assumes the [filesystem](https://github.com/docker/distribution/blob/master/docs/configuration.md#storage) storage driver.
  - This script may run stand-alone (on local setups) or dockerized (which supports both local and remote Docker setups). To run stand-alone, you must install **docker-py** and **pyyaml** with:
  
  `pip3 install docker pyyaml`
  
## Usage:

```
clean_registry.py [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...
Options:
        -x, --remove    Remove the specified images or repositories.
        -q, --quiet     Supress non-error messages.
        -V, --version   Show version and exit.
```

## Docker usage with local Docker setup

`docker run --rm --volumes-from CONTAINER -v /var/run/docker.sock:/var/run/docker.sock ricardobranco/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...`

## Docker usage with [remote Docker setup](https://docs.docker.com/engine/security/https/#secure-by-default)

`docker run --rm --volumes-from CONTAINER -e DOCKER_HOST -e DOCKER_TLS_VERIFY=1 -v /root/.docker:/root/.docker ricardobranco/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...`

Note: Paths other than `/root/.docker` path may be specified with the **DOCKER_CERT_PATH** environment variable.  In any case, your `~/.docker/*.pem` files should be in the server to be able to run as a client against itself.
