# clean_registry
Clean the Docker Registry by removing untagged repositories and running the garbage collector in Docker Registry >= 2.4.0

The optional `-x` flag may be used to remove the specified repositories or tagged images.

NOTES:
  - This script stops the Registry container during cleanup to prevent corruption, making it temporarily unavailable to clients.
  - This script assumes local storage (the **filesystem** storage driver).
  - This script may run standalone or dockerized.  To run standalone, you must install **docker-py** with `pip3 install docker` and **pyyaml** with `pip3 install pyyaml`.
  - This script is Python 3 only.
  
## Usage:

```
clean_registry.py [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...
Options:
        -x, --remove    Remove the specified images or repositories.
        -q, --quiet     Supress non-error messages.
        -V, --version   Show version and exit.
```

## Docker usage:

`docker run --rm --volumes-from CONTAINER -v /var/run/docker.sock:/var/run/docker.sock ricardobranco/clean_registry [OPTIONS] CONTAINER [REPOSITORY[:TAG]]...`
