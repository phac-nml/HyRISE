import hyrise.config as config


def test_load_config_returns_empty_when_missing(monkeypatch, tmp_path):
    missing = tmp_path / "missing.toml"
    monkeypatch.delenv("HYRISE_CONFIG", raising=False)
    loaded = config.load_config(str(missing))
    assert loaded == {}


def test_load_config_from_explicit_file(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
[container]
path = "/tmp/hyrise.sif"
runtime = "apptainer"

[resources]
dir = "/tmp/hyrise-resources"
""".strip()
    )
    loaded = config.load_config(str(cfg))
    assert loaded["container"]["path"] == "/tmp/hyrise.sif"
    assert loaded["container"]["runtime"] == "apptainer"
    assert loaded["resources"]["dir"] == "/tmp/hyrise-resources"


def test_resolve_option_precedence(monkeypatch):
    monkeypatch.setenv("HYRISE_TEST_OPTION", "from-env")
    # CLI wins over config/env/default
    assert (
        config.resolve_option(
            "from-cli", "from-config", "HYRISE_TEST_OPTION", "default"
        )
        == "from-cli"
    )
    # Config wins over env/default when CLI missing
    assert (
        config.resolve_option(None, "from-config", "HYRISE_TEST_OPTION", "default")
        == "from-config"
    )
    # Env wins over default when CLI/config missing
    assert (
        config.resolve_option(None, None, "HYRISE_TEST_OPTION", "default") == "from-env"
    )
    # Default fallback
    monkeypatch.delenv("HYRISE_TEST_OPTION", raising=False)
    assert (
        config.resolve_option(None, None, "HYRISE_TEST_OPTION", "default") == "default"
    )


def test_get_container_search_paths_order(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_default_data_dir", lambda: tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    cfg = {"container": {"search_paths": [str(tmp_path / "extra.sif")]}}

    paths = list(config.get_container_search_paths(config=cfg, cli_container_path=None))
    assert paths[0] == str((tmp_path / "hyrise.sif").resolve())
    assert paths[1] == str((tmp_path / "data" / "hyrise.sif").resolve())
    assert paths[2] == str((tmp_path / "extra.sif").resolve())


def test_resolve_resource_dir_defaults_to_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_default_data_dir", lambda: tmp_path / "xdg-data")
    resolved = config.resolve_resource_dir(config={}, cli_resource_dir=None)
    assert resolved == str((tmp_path / "xdg-data" / "resources").resolve())
