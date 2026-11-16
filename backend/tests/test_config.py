import pytest

from groundwork import config


def test_require_env_returns_the_value(monkeypatch):
    monkeypatch.setenv("GROUNDWORK_TEST_VAR", "some-value")
    assert config.require_env("GROUNDWORK_TEST_VAR") == "some-value"


def test_missing_env_var_is_named_in_the_error(monkeypatch):
    monkeypatch.delenv("GROUNDWORK_TEST_VAR", raising=False)
    with pytest.raises(config.MissingEnvError, match="GROUNDWORK_TEST_VAR isn't set"):
        config.require_env("GROUNDWORK_TEST_VAR")


def test_empty_env_var_counts_as_missing(monkeypatch):
    monkeypatch.setenv("GROUNDWORK_TEST_VAR", "")
    with pytest.raises(config.MissingEnvError, match="isn't set"):
        config.require_env("GROUNDWORK_TEST_VAR")


def test_real_postings_can_never_go_to_the_public_database():
    public_folder, public_url = config.CORPORA["public"]
    private_folder, private_url = config.CORPORA["private"]

    assert "data" not in public_folder.relative_to(config.REPO_ROOT).parts
    assert public_url != private_url
