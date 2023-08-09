import pytest
from clean_registry import check_name, is_container


check_name_test_cases = [
    {
        'image_name': "myrepo:latest",
        'expected_validity': True,
        'test_description': "Valid image name with 'latest' tag",
    },
    {
        'image_name': "my_repo:latest",
        'expected_validity': True,
        'test_description': "Valid image name with underscore",
    },
    {
        'image_name': "my-repo:latest",
        'expected_validity': True,
        'test_description': "Valid image name with dash",
    },
    {
        'image_name': "my__repo:latest",
        'expected_validity': True,
        'test_description': "Valid image name with double underscore",
    },
    {
        'image_name': "my-repo:1.0",
        'expected_validity': True,
        'test_description': "Valid image name with tag",
    },
    {
        'image_name': "my-repo:tag!",
        'expected_validity': False,
        'test_description': "Invalid character '!' in tag",
    },
    {
        'image_name': "my-repo:longtag" * 10,
        'expected_validity': False,
        'test_description': "Tag length exceeds 128 characters",
    },
    {
        'image_name': "my-Repo:latest",
        'expected_validity': False,
        'test_description': "Uppercase characters in repository name",
    },
    {
        'image_name': "a" * 256 + ":latest",
        'expected_validity': False,
        'test_description': "Total length exceeds 256 characters",
    },
    {
        'image_name': "my_repo/my_image:latest",
        'expected_validity': True,
        'test_description': "Valid image name with '/' separator",
    },
    {
        'image_name': "my-repo/my_image:latest",
        'expected_validity': True,
        'test_description': "Valid image name with '/' separator in repo",
    },
    {
        'image_name': "my-repo/my_image:tag!",
        'expected_validity': False,
        'test_description': "Invalid character '!' in tag for repo/image",
    },
    {
        'image_name': "my-repo/my_image:longtag" * 10,
        'expected_validity': False,
        'test_description': "Tag length exceeds 128 characters for repo/image",
    },
    {
        'image_name': "my-repo/my_image:latest:tag",
        'expected_validity': False,
        'test_description': "Multiple colons in the name",
    },
    {
        'image_name': "my-repo//my_image:latest",
        'expected_validity': False,
        'test_description': "Double slashes in the name",
    },
    {
        'image_name': "my-repo/my_image:",
        'expected_validity': False,
        'test_description': "Empty tag",
    },
    {
        'image_name': "my-repo:latest/tag",
        'expected_validity': False,
        'test_description': "Slash in the tag",
    },
]


@pytest.mark.parametrize("test_case", check_name_test_cases, ids=lambda test_case: test_case['test_description'])
def test_check_name(test_case):
    assert check_name(test_case['image_name']) == test_case['expected_validity']


is_container_test_cases = [
    {
        'container_env_value': "podman",
        'dockerenv_exists': False,
        'expected_result': True,
        'test_description': "Inside Podman container environment",
    },
    {
        'container_env_value': None,
        'dockerenv_exists': True,
        'expected_result': True,
        'test_description': "Inside Docker container environment",
    },
    {
        'container_env_value': None,
        'dockerenv_exists': False,
        'expected_result': False,
        'test_description': "Outside any container environment",
    },
]


@pytest.mark.parametrize("test_case", is_container_test_cases, ids=lambda test_case: test_case['test_description'])
def test_is_container(test_case, monkeypatch):
    container_env_value = test_case['container_env_value']
    if container_env_value is None:
        container_env_value = ""
    monkeypatch.setenv("container", container_env_value)

    if test_case['dockerenv_exists']:
        monkeypatch.setattr("os.path.isfile", lambda path: path == "/.dockerenv")

    assert is_container() == test_case['expected_result']
