#!/bin/bash

set -e

cleanup() {
	set +e
	unset DOCKER_HOST
	for runtime in podman docker ; do
		image_ids=()
		for image in "$regclean:test" "$regclean:latest" "$scratch" ; do
			images_ids+=("$(docker images --no-trunc --format '{{.ID}}' "$image")")
			"$runtime" rmi "$image"
		done
		images_ids+=("$(docker images --no-trunc --format '{{.ID}}' "$regclean")")
		for image_id in "${image_ids[@]}" ; do
			"$runtime" rmi "$image_id"
		done
	done
	podman rm -vf "$registry"
	sudo rm -rf "$directory"
}

trap "cleanup ; exit 1" ERR INT QUIT

get_random_port() {
	read -r port_low port_high < /proc/sys/net/ipv4/ip_local_port_range
	echo $((port_low + RANDOM % (port_high - port_low)))
}

random_port=$(get_random_port)
directory="$PWD/registry$random_port"
regclean="localhost:$random_port/clean_registry"
scratch="localhost/scratch$random_port"
registry="registry$random_port"

podman build -t "$scratch" -f <(echo "FROM scratch") .
podman save "$scratch" | docker load
podman build -t "$regclean:test" --pull .
podman save "$regclean:test" | docker load

DOCKER_SOCKET="$(docker context inspect -f json default | jq -r '.[0].Endpoints.docker.Host')"
DOCKER_SOCKET="${DOCKER_SOCKET#unix://}"
PODMAN_SOCKET=$(podman info --format json | jq -r '.host.remoteSocket.path')

for runtime in docker podman ; do
	if [[ $runtime = podman ]] ; then
		export DOCKER_HOST="unix:///run/podman/podman.sock"
		push_options=(--tls-verify=false)
	else
		push_options=()
	fi

	mkdir "$directory"
	"$runtime" run -d --name "$registry" -e REGISTRY_STORAGE_DELETE_ENABLED=1 -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/var/registry -p "$random_port:5000" -v "$directory:/var/registry" registry:2

	"$runtime" tag "$scratch" "$regclean:latest"
	"$runtime" push "${push_options[@]}" "$regclean:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	"$runtime" tag "$regclean:test" "$regclean:latest"
	"$runtime" push "${push_options[@]}" "$regclean:latest"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 2 ]]

	"$runtime" stop "$registry"

	echo -e "\nTEST: $runtime: Cleanup --dry-run\n"
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$regclean:test" --"$runtime" --dry-run "$registry"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 2 ]]

	echo -e "\nTEST: $runtime: Cleanup\n"
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$regclean:test" --"$runtime" "$registry"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	echo -e "\nTEST: $runtime: Remove image --dry-run\n"
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$regclean:test" --"$runtime" --dry-run -x "$registry" "${regclean##*/}"
	[[ $(find "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" -type f | wc -l) -eq 1 ]]

	echo -e "\nTEST: $runtime: Remove image\n"
	"$runtime" run --rm -e DOCKER_HOST --volumes-from "$registry" -v "$DOCKER_SOCKET:$DOCKER_SOCKET" -v "$PODMAN_SOCKET:/run/podman/podman.sock" "$regclean:test" --"$runtime" -x "$registry" "${regclean##*/}"
	[ ! -d "$directory/docker/registry/v2/repositories/clean_registry/_manifests/revisions/sha256" ]

	"$runtime" rm -vf "$registry"
	sudo rm -rf "$directory"
done

cleanup
