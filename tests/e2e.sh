#!/bin/bash

set -e

cleanup() {
	set +e
	echo -e "\nCleaning up for $runtime\n"
	for runtime in podman docker ; do
		"$runtime" rm -vf "$registry"
		# shellcheck disable=SC2046
		"$runtime" rmi -f $("$runtime" images --no-trunc --format '{{.ID}}' "localhost:$random_port/*" | sort -u)
	done
	sudo rm -rf "$directory"
}

trap 'cleanup ; echo -e "\nFAILED" ; exit 1' ERR INT QUIT

get_random_port() {
	read -r port_low port_high < /proc/sys/net/ipv4/ip_local_port_range
	echo $((port_low + RANDOM % (port_high - port_low)))
}

random_port=$(get_random_port)
directory="$PWD/registry$random_port"
regclean="localhost:$random_port/clean_registry"
scratch="localhost:$random_port/scratch"
registry="registry$random_port"

# Build once, load anywhere...
podman build -t "$scratch" -f <(echo "FROM scratch") .
podman save "$scratch" | docker load
podman build -t "$regclean:test" --pull .
podman save "$regclean:test" | docker load

DOCKER_HOST="$(docker context inspect -f json default | jq -r '.[0].Endpoints.docker.Host')"
DOCKER_SOCKET="${DOCKER_HOST#unix://}"
PODMAN_SOCKET="$(podman info --format json | jq -r '.host.remoteSocket.path')"
CONTAINER_HOST="$PODMAN_SOCKET"
PODMAN_SOCKET="${PODMAN_SOCKET#unix://}"

for runtime in docker podman ; do
	options=(--rm --volumes-from "$registry")
	if [[ $runtime = podman ]] ; then
		options+=(-e CONTAINER_HOST="$CONTAINER_HOST" -v "$PODMAN_SOCKET:$PODMAN_SOCKET")
		runtime_options=(--tls-verify=false)
	else
		options+=(-e DOCKER_HOST="$DOCKER_HOST" -v "$DOCKER_SOCKET:$DOCKER_SOCKET")
		runtime_options=()
	fi

	mkdir "$directory"
	# REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY is needed because of https://github.com/containers/podman/issues/19529
	"$runtime" run -d --name "$registry" -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/var/registry -p "$random_port:5000" -v "$directory:/var/registry" registry:2

	"$runtime" tag "$scratch" "$regclean:latest"
	"$runtime" push "${runtime_options[@]}" "$regclean:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	"$runtime" tag "$regclean:test" "$regclean:latest"
	"$runtime" push "${runtime_options[@]}" "$regclean:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 2 ]]

	"$runtime" stop "$registry"

	echo -e "\nTEST: $runtime: Cleanup --dry-run\n"
	"$runtime" run "${options[@]}" "$regclean:test" --dry-run -l debug "$registry"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 2 ]]

	echo -e "\nTEST: $runtime: Cleanup\n"
	"$runtime" run "${options[@]}" "$regclean:test" -l debug "$registry"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	# Image should be pullable
	"$runtime" start "$registry"
	"$runtime" pull "${runtime_options[@]}" "$regclean:latest"
	"$runtime" stop "$registry"

	echo -e "\nTEST: $runtime: Remove image --dry-run\n"
	"$runtime" run "${options[@]}" "$regclean:test" --dry-run -x -l debug "$registry" "${regclean##*/}"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	echo -e "\nTEST: $runtime: Remove image\n"
	"$runtime" run "${options[@]}" "$regclean:test" -x -l debug "$registry" "${regclean##*/}"
	[ ! -d "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" ]

	"$runtime" rm -vf "$registry"
	sudo rm -rf "$directory"
done

cleanup

echo -e "\nPASSED"
