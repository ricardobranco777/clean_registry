#!/bin/bash

set -e

cleanup() {
	set +e
	unset DOCKER_HOST
	for runtime in podman docker ; do
		"$runtime" rmi "$scratch"
		"$runtime" rmi "$image:test" "$image:latest"
	done
	podman rm -vf "$registry"
	sudo rm -rf "$directory"
}

trap "cleanup ; exit 1" ERR

get_random_port() {
	read -r port_low port_high < /proc/sys/net/ipv4/ip_local_port_range
	echo $((port_low + RANDOM % (port_high - port_low)))
}

random_port=$(get_random_port)
directory="$PWD/registry$random_port"
image="localhost:$random_port/clean_registry"
scratch="localhost/scratch$random_port"
registry="registry$random_port"

podman build -t "$scratch" -f <(echo "FROM scratch") .
podman save "$scratch" | docker load
podman build -t "$image:test" --pull .
podman save "$image:test" | docker load

DOCKER_SOCKET="/var/run/docker.sock"
PODMAN_SOCKET=$(podman info --format json | jq -r '.host.remoteSocket.path')

#export CONTAINERS_REGISTRIES_CONF=tests/registries.conf

for runtime in docker podman ; do
	if [[ $runtime = docker ]] ; then
		#export DOCKER_HOST="$(docker context inspect -f json default | jq -r '.[0].Endpoints.docker.Host')"
		runtime_options=()
		push_options=()
	else
		export DOCKER_HOST="unix:///run/podman/podman.sock"
		runtime_options=()
		push_options=(--tls-verify=false)
	fi

	mkdir "$directory"
	"$runtime" run -d --name "$registry" -e REGISTRY_STORAGE_DELETE_ENABLED=1 -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/var/registry -p "$random_port:5000" -v "$directory:/var/registry" registry:2

	"$runtime" tag "$scratch" "$image:latest"
	"$runtime" "${runtime_options[@]}" push "${push_options[@]}" "$image:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	"$runtime" tag "$image:test" "$image:latest"
	"$runtime" "${runtime_options[@]}" push "${push_options[@]}" "$image:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 2 ]]

	# Test cleanup
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$image:test" --"$runtime" "$registry"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	# Test -x option
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$image:test" --"$runtime" -x "$registry" "${image##*/}"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 0 ]]

	"$runtime" rm -vf "$registry"
	sudo rm -rf "$directory"
done

cleanup
