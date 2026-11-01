"""P6-T03: the DBOS settings decided before the first migration. No database needed."""

import pytest

from flow import config


def test_dbos_config_pins_version_and_executor_and_sets_no_conductor_key():
    cfg = config.dbos_config(config.FlowSettings(database_url="postgresql://u:secret@h/db"))
    assert cfg["application_version"] == config.APPLICATION_VERSION == "argus-flow-1"
    assert cfg["executor_id"] == config.EXECUTOR_ID == "argus-flow-0"
    assert cfg["use_listen_notify"] is False
    assert "conductor_key" not in cfg and "conductor_url" not in cfg


def test_database_url_comes_from_the_environment_and_is_not_printed(monkeypatch):
    monkeypatch.delenv(config.DATABASE_URL_ENV, raising=False)
    with pytest.raises(RuntimeError, match=config.DATABASE_URL_ENV):
        config.FlowSettings.from_env()
    monkeypatch.setenv(config.DATABASE_URL_ENV, "postgresql://u:hunter2@h/db")
    settings = config.FlowSettings.from_env()
    assert settings.database_url.endswith("@h/db")
    assert "hunter2" not in repr(settings) and "hunter2" not in str(settings)


def test_qa_timeout_has_a_short_default_and_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv(config.DATABASE_URL_ENV, "postgresql://u:pw@h/db")
    monkeypatch.delenv(config.QA_TIMEOUT_ENV, raising=False)
    assert config.FlowSettings.from_env().qa_timeout_seconds == config.DEFAULT_QA_TIMEOUT_SECONDS == 60.0
    monkeypatch.setenv(config.QA_TIMEOUT_ENV, "86400")
    assert config.FlowSettings.from_env().qa_timeout_seconds == 86400.0
    for bad in ("soon", "0", "-5"):
        monkeypatch.setenv(config.QA_TIMEOUT_ENV, bad)
        with pytest.raises(RuntimeError, match=config.QA_TIMEOUT_ENV):
            config.FlowSettings.from_env()
