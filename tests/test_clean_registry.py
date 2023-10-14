# pylint: disable=line-too-long,missing-module-docstring,missing-function-docstring,missing-class-docstring,redefined-outer-name

import logging
import shlex
import pytest
from clean_registry import (
    check_name,
    is_container,
    run_command,
    clean_registrydir,
    clean_tag,
    clean_repo,
    remove_dir,
    garbage_collect,
    main,
)


check_name_test_cases = [
    {
        "image_name": "myrepo:latest",
        "expected_validity": True,
        "test_description": "Valid image name with 'latest' tag",
    },
    {
        "image_name": "my_repo:latest",
        "expected_validity": True,
        "test_description": "Valid image name with underscore",
    },
    {
        "image_name": "my-repo:latest",
        "expected_validity": True,
        "test_description": "Valid image name with dash",
    },
    {
        "image_name": "my__repo:latest",
        "expected_validity": True,
        "test_description": "Valid image name with double underscore",
    },
    {
        "image_name": "my-repo:1.0",
        "expected_validity": True,
        "test_description": "Valid image name with tag",
    },
    {
        "image_name": "my-repo:tag!",
        "expected_validity": False,
        "test_description": "Invalid character '!' in tag",
    },
    {
        "image_name": "my-repo:longtag" * 10,
        "expected_validity": False,
        "test_description": "Tag length exceeds 128 characters",
    },
    {
        "image_name": "my-Repo:latest",
        "expected_validity": False,
        "test_description": "Uppercase characters in repository name",
    },
    {
        "image_name": "a" * 256 + ":latest",
        "expected_validity": False,
        "test_description": "Total length exceeds 256 characters",
    },
    {
        "image_name": "my_repo/my_image:latest",
        "expected_validity": True,
        "test_description": "Valid image name with '/' separator",
    },
    {
        "image_name": "my-repo/my_image:latest",
        "expected_validity": True,
        "test_description": "Valid image name with '/' separator in repo",
    },
    {
        "image_name": "my-repo/my_image:tag!",
        "expected_validity": False,
        "test_description": "Invalid character '!' in tag for repo/image",
    },
    {
        "image_name": "my-repo/my_image:longtag" * 10,
        "expected_validity": False,
        "test_description": "Tag length exceeds 128 characters for repo/image",
    },
    {
        "image_name": "my-repo/my_image:latest:tag",
        "expected_validity": False,
        "test_description": "Multiple colons in the name",
    },
    {
        "image_name": "my-repo//my_image:latest",
        "expected_validity": False,
        "test_description": "Double slashes in the name",
    },
    {
        "image_name": "my-repo/my_image:",
        "expected_validity": False,
        "test_description": "Empty tag",
    },
    {
        "image_name": "my-repo:latest/tag",
        "expected_validity": False,
        "test_description": "Slash in the tag",
    },
]


@pytest.mark.parametrize(
    "test_case",
    check_name_test_cases,
    ids=lambda test_case: test_case["test_description"],
)
def test_check_name(test_case):
    assert check_name(test_case["image_name"]) == test_case["expected_validity"]


is_container_test_cases = [
    {
        "container_env_value": "podman",
        "dockerenv_exists": False,
        "expected_result": True,
        "test_description": "Inside Podman container environment",
    },
    {
        "container_env_value": None,
        "dockerenv_exists": True,
        "expected_result": True,
        "test_description": "Inside Docker container environment",
    },
    {
        "container_env_value": None,
        "dockerenv_exists": False,
        "expected_result": False,
        "test_description": "Outside any container environment",
    },
]


@pytest.mark.parametrize(
    "test_case",
    is_container_test_cases,
    ids=lambda test_case: test_case["test_description"],
)
def test_is_container(test_case, monkeypatch):
    container_env_value = test_case["container_env_value"]
    if container_env_value is None:
        container_env_value = ""
    monkeypatch.setenv("container", container_env_value)

    if test_case["dockerenv_exists"]:
        monkeypatch.setattr("os.path.isfile", lambda path: path == "/.dockerenv")

    assert is_container() == test_case["expected_result"]


def test_run_command_success(mocker, caplog):
    caplog.set_level(logging.INFO)
    process_mock = mocker.MagicMock()
    process_mock.__enter__.return_value.stdout = ["stdout_line1\n", "stdout_line2\n"]
    process_mock.__enter__.return_value.returncode = 0

    mocker.patch("subprocess.Popen", return_value=process_mock)

    exit_code = run_command(["some_command"])
    assert exit_code == 0

    assert "stdout_line1" in caplog.text


def test_run_command_failure(mocker, caplog):
    caplog.set_level(logging.INFO)
    process_mock = mocker.MagicMock()
    process_mock.__enter__.return_value.stdout = ["stderr_line1\n", "stderr_line2\n"]
    process_mock.__enter__.return_value.returncode = 1

    mocker.patch("subprocess.Popen", return_value=process_mock)

    exit_code = run_command(["some_command"])
    assert exit_code == 1

    assert "stderr_line1" in caplog.text


def test_run_command_no_output(mocker, caplog):
    caplog.set_level(logging.INFO)
    process_mock = mocker.MagicMock()
    process_mock.__enter__.return_value.stdout = []
    process_mock.__enter__.return_value.returncode = 0

    mocker.patch("subprocess.Popen", return_value=process_mock)

    exit_code = run_command(["some_command"])
    assert exit_code == 0

    assert "Running some_command" in caplog.text


def test_run_command_error(mocker, caplog):
    caplog.set_level(logging.INFO)
    process_mock = mocker.MagicMock()
    process_mock.__enter__.side_effect = OSError(2, "some_command")

    mocker.patch("subprocess.Popen", return_value=process_mock)

    exit_code = run_command(["some_command"])
    assert exit_code == 1


@pytest.fixture
def mock_clean_repo(mocker):
    return mocker.patch("clean_registry.clean_repo")


@pytest.fixture
def mock_garbage_collect(mocker):
    return mocker.patch("clean_registry.garbage_collect")


def test_clean_registry_no_images(mock_clean_repo, mock_garbage_collect):
    images = []

    clean_registrydir(images)

    assert mock_clean_repo.call_count == 0
    assert mock_garbage_collect.call_count == 1


def test_clean_registry_images(monkeypatch, mock_clean_repo, mock_garbage_collect):
    images = ["image1", "image2"]

    monkeypatch.setenv("REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY", "/mocked/registry")
    clean_registrydir(images)

    assert mock_clean_repo.call_count == len(images)
    assert mock_garbage_collect.call_count == 1


@pytest.fixture
def mock_remove_dir(mocker):
    return mocker.patch("clean_registry.remove_dir")


def test_clean_tag_existing_tag(mocker, mock_remove_dir):
    basedir = "/mocked/basedir"
    repo = "repository"
    tag = "latest"
    dry_run = False

    mock_exists = mocker.patch("os.path.isfile")
    mock_exists.return_value = True

    clean_tag(basedir, repo, tag, dry_run)

    mock_exists.assert_called_once_with(
        f"{basedir}/{repo}/_manifests/tags/{tag}/current/link"
    )
    mock_remove_dir.assert_called_once_with(
        f"{basedir}/{repo}/_manifests/tags/{tag}", dry_run
    )


def test_clean_tag_nonexistent_tag(mocker, mock_remove_dir, caplog):
    basedir = "/mocked/basedir"
    repo = "repository"
    tag = "nonexistent"
    dry_run = False

    mock_exists = mocker.patch("os.path.isfile")
    mock_exists.return_value = False

    with caplog.at_level(logging.ERROR):
        clean_tag(basedir, repo, tag, dry_run)

    assert mock_exists.call_count == 1
    assert "No such tag: nonexistent in repository repository" in caplog.text
    assert not mock_remove_dir.called


@pytest.fixture
def mock_clean_tag(mocker):
    return mocker.patch("clean_registry.clean_tag")


def test_clean_repo_existing_repo(mocker, mock_clean_tag, mock_remove_dir):
    basedir = "/mocked/basedir"
    image = "repository:latest"
    dry_run = False

    mock_isdir = mocker.patch("os.path.isdir")
    mock_isdir.return_value = True

    mock_listdir = mocker.patch("os.listdir")
    mock_listdir.return_value = ["latest"]

    clean_repo(basedir, image, dry_run)

    repo, _ = image.split(":")

    mock_isdir.assert_called_once_with(f"{basedir}/{repo}")
    mock_listdir.assert_called_once_with(f"{basedir}/{repo}/_manifests/tags")
    mock_remove_dir.assert_called_once_with(f"{basedir}/{repo}", dry_run)
    assert not mock_clean_tag.called


def test_clean_repo_nonexistent_repo(mocker, mock_clean_tag, mock_remove_dir, caplog):
    basedir = "/mocked/basedir"
    image = "nonexistent_repo:latest"
    dry_run = False

    mock_isdir = mocker.patch("os.path.isdir")
    mock_isdir.return_value = False

    with caplog.at_level(logging.ERROR):
        clean_repo(basedir, image, dry_run)

    assert mock_isdir.call_count == 1
    assert "No such repository: nonexistent_repo" in caplog.text
    assert not mock_remove_dir.called
    assert not mock_clean_tag.called


def test_clean_repo_single_tag(mocker, mock_clean_tag, mock_remove_dir):
    basedir = "/mocked/basedir"
    image = "repository:latest"
    dry_run = False

    mock_isdir = mocker.patch("os.path.isdir")
    mock_isdir.return_value = True

    mock_listdir = mocker.patch("os.listdir")
    mock_listdir.return_value = ["latest"]

    clean_repo(basedir, image, dry_run)

    repo, _ = image.split(":")

    mock_isdir.assert_called_once_with(f"{basedir}/{repo}")
    mock_listdir.assert_called_once_with(f"{basedir}/{repo}/_manifests/tags")
    mock_remove_dir.assert_called_once_with(f"{basedir}/{repo}", dry_run)
    assert not mock_clean_tag.called


def test_clean_repo_specific_tag(mocker, mock_clean_tag, mock_remove_dir):
    basedir = "/mocked/basedir"
    image = "repository:specific_tag"
    dry_run = False

    mock_isdir = mocker.patch("os.path.isdir")
    mock_isdir.return_value = True

    mock_listdir = mocker.patch("os.listdir")
    mock_listdir.return_value = ["latest", "specific_tag"]

    clean_repo(basedir, image, dry_run)

    repo, tag = image.split(":")

    mock_isdir.assert_called_once_with(f"{basedir}/{repo}")
    mock_listdir.assert_called_once_with(f"{basedir}/{repo}/_manifests/tags")
    assert not mock_remove_dir.called
    mock_clean_tag.assert_called_once_with(basedir, repo, tag, dry_run)


@pytest.fixture
def mock_rmtree(mocker):
    return mocker.patch("clean_registry.rmtree")


def test_remove_dir_dry_run(mock_rmtree):
    directory = "/mocked/directory"
    dry_run = True

    remove_dir(directory, dry_run)

    assert not mock_rmtree.called


def test_remove_dir_normal(mock_rmtree):
    directory = "/mocked/directory"
    dry_run = False

    remove_dir(directory, dry_run)

    mock_rmtree.assert_called_once_with(directory)


@pytest.fixture
def mock_run_command(mocker):
    return mocker.patch("clean_registry.run_command")


def test_garbage_collect_dry_run(mock_run_command, caplog):
    dry_run = True
    mock_run_command.return_value = 0

    garbage_collect(dry_run)

    expected_command = shlex.split(
        "/bin/registry garbage-collect --delete-untagged --dry-run /etc/docker/registry/config.yml"
    )
    mock_run_command.assert_called_once_with(expected_command)
    assert not caplog.text


def test_garbage_collect_normal(mock_run_command, caplog):
    dry_run = False
    mock_run_command.return_value = 0

    garbage_collect(dry_run)

    expected_command = shlex.split(
        "/bin/registry garbage-collect --delete-untagged /etc/docker/registry/config.yml"
    )
    mock_run_command.assert_called_once_with(expected_command)
    assert not caplog.text


def test_garbage_collect_failed_command(mock_run_command, caplog):
    dry_run = False
    mock_run_command.return_value = 1

    with caplog.at_level(logging.ERROR):
        garbage_collect(dry_run)

    expected_command = shlex.split(
        "/bin/registry garbage-collect --delete-untagged /etc/docker/registry/config.yml"
    )
    mock_run_command.assert_called_once_with(expected_command)
    assert "Command returned 1" in caplog.text


def test_main_with_invalid_image(mocker):
    mocker.patch("clean_registry.is_container", return_value=True)
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch(
        "clean_registry.parse_args",
        return_value=mocker.Mock(
            version=False, images=["!nvalid-image"], log="info", dry_run=False
        ),
    )
    mock_clean_registrydir = mocker.patch("clean_registry.clean_registrydir")

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.type == SystemExit
    assert str(exc.value) == "ERROR: Invalid Docker repository/tag: !nvalid-image"

    assert not mock_clean_registrydir.called


def test_main_with_valid_images(mocker):
    mocker.patch("clean_registry.is_container", return_value=True)
    mocker.patch("os.path.isfile", return_value=True)
    images = ["valid:image"]
    mocker.patch(
        "clean_registry.parse_args",
        return_value=mocker.Mock(
            version=False, images=images, log="info", dry_run=False
        ),
    )
    mock_clean_registrydir = mocker.patch("clean_registry.clean_registrydir")

    main()

    assert mock_clean_registrydir.called_with(images, False)


def test_main_inside_container(mocker):
    mocker.patch("clean_registry.is_container", return_value=True)
    mocker.patch("os.path.isfile", return_value=True)
    images = []
    mocker.patch(
        "clean_registry.parse_args",
        return_value=mocker.Mock(
            version=False, images=images, log="info", dry_run=False
        ),
    )
    mock_clean_registrydir = mocker.patch("clean_registry.clean_registrydir")

    main()

    assert mock_clean_registrydir.called_with(images, False)


def test_main_outside_container(mocker):
    mocker.patch("os.path.isfile", return_value=False)
    mocker.patch(
        "clean_registry.parse_args",
        return_value=mocker.Mock(version=False, images=[], log="info", dry_run=False),
    )
    mock_clean_registrydir = mocker.patch("clean_registry.clean_registrydir")

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.type == SystemExit
    assert (
        str(exc.value) == "ERROR: This script should run inside a registry:2 container!"
    )

    assert not mock_clean_registrydir.called
