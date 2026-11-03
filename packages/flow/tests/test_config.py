"""P6-T03 and P6-T11: the DBOS settings decided before the first migration, and TLS for a remote database.
No database needed."""

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
    monkeypatch.setenv(config.DATABASE_URL_ENV, "postgresql://u:hunter2@h/db?sslmode=require")
    settings = config.FlowSettings.from_env()
    assert settings.database_url.endswith("@h/db?sslmode=require")
    assert "hunter2" not in repr(settings) and "hunter2" not in str(settings)


def test_qa_timeout_has_a_short_default_and_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv(config.DATABASE_URL_ENV, "postgresql://u:pw@h/db?sslmode=require")
    monkeypatch.delenv(config.QA_TIMEOUT_ENV, raising=False)
    assert config.FlowSettings.from_env().qa_timeout_seconds == config.DEFAULT_QA_TIMEOUT_SECONDS == 60.0
    monkeypatch.setenv(config.QA_TIMEOUT_ENV, "86400")
    assert config.FlowSettings.from_env().qa_timeout_seconds == 86400.0
    for bad in ("soon", "0", "-5"):
        monkeypatch.setenv(config.QA_TIMEOUT_ENV, bad)
        with pytest.raises(RuntimeError, match=config.QA_TIMEOUT_ENV):
            config.FlowSettings.from_env()


# --- P6-T11 -------------------------------------------------------------------------------------

NEON_URL = "postgresql://owner:hunter2@ep-quiet-dust-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require"
# The Render environment as docs/notes/p6-t11.md lists it for the database part, plus the variables
# DBOS itself reads that a platform might export. None of the latter may change a first-migration choice.
RENDER_ENV = {
    config.DATABASE_URL_ENV: NEON_URL,
    config.QA_TIMEOUT_ENV: "86400",
    "DBOS__VMID": "srv-render-instance-7f9c",
    "DBOS__APPVERSION": "git-3f2a9c1",
    "DBOS__CONDUCTOR_KEY": "conductor-key-from-the-dashboard",
    "DBOS__CONDUCTOR_URL": "wss://example.invalid/conductor",
    "DBOS__CONDUCTOR_APP_NAME": "other-app",
}


def test_first_migration_choices_hold_when_the_render_environment_is_set(monkeypatch):
    from dbos import DBOS
    from dbos._utils import GlobalParams

    for name, value in RENDER_ENV.items():
        monkeypatch.setenv(name, value)
    settings = config.FlowSettings.from_env()
    cfg = config.dbos_config(settings)
    assert (cfg["application_version"], cfg["executor_id"], cfg["use_listen_notify"]) == ("argus-flow-1", "argus-flow-0", False)
    assert not {"conductor_key", "conductor_url", "conductor_executor_metadata"} & cfg.keys()
    # and what DBOS itself ends up with, read after constructing it (no launch, no connection)
    dbos = DBOS(config=cfg)
    try:
        assert GlobalParams.app_version == "argus-flow-1" and GlobalParams.executor_id == "argus-flow-0"
        assert dbos.conductor_key is None and not GlobalParams.dbos_cloud  # DBOS__CONDUCTOR_* only count in DBOS Cloud
    finally:
        DBOS.destroy()


def test_a_remote_database_must_ask_for_tls(monkeypatch):
    for url in (
        "postgresql://u:hunter2@ep-x.neon.tech/db",
        "postgresql://u:hunter2@ep-x.neon.tech/db?sslmode=prefer",
        "postgresql://u:hunter2@ep-x.neon.tech/db?sslmode=disable",
    ):
        monkeypatch.setenv(config.DATABASE_URL_ENV, url)
        with pytest.raises(RuntimeError, match="TLS") as e:
            config.FlowSettings.from_env()
        assert "hunter2" not in str(e.value) and "neon.tech" not in str(e.value)
    for url in (NEON_URL, NEON_URL.replace("require", "verify-full") + "&sslrootcert=system"):
        monkeypatch.setenv(config.DATABASE_URL_ENV, url)
        assert config.FlowSettings.from_env().database_url == url


def test_a_local_database_needs_no_tls(monkeypatch):
    for host in ("127.0.0.1:55436", "localhost", "[::1]:5432"):
        monkeypatch.setenv(config.DATABASE_URL_ENV, f"postgresql://u:pw@{host}/db")
        assert config.FlowSettings.from_env().database_url.endswith(f"@{host}/db")


def test_an_unparseable_url_is_refused_without_echoing_it(monkeypatch):
    monkeypatch.setenv(config.DATABASE_URL_ENV, "host=h password=hunter2 sslmode")
    with pytest.raises(RuntimeError, match="not a valid") as e:
        config.FlowSettings.from_env()
    assert "hunter2" not in str(e.value) and e.value.__cause__ is None and e.value.__suppress_context__
