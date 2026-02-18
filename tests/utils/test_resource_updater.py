from hyrise.utils import resource_updater as ru


def test_get_resource_dir_uses_xdg_data(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ru,
        "resolve_resource_dir",
        lambda config, cli_resource_dir=None: str(
            tmp_path / "hyrise-data" / "resources"
        ),
    )
    resource_dir = ru.get_resource_dir()
    assert resource_dir.exists()
    assert resource_dir == (tmp_path / "hyrise-data" / "resources")


def test_get_latest_resource_path_returns_highest_hivdb_version(tmp_path):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()
    (resource_dir / "HIVDB_9.7.xml").write_text("a")
    (resource_dir / "HIVDB_9.9.xml").write_text("b")
    (resource_dir / "HIVDB_10.1.xml").write_text("c")

    latest = ru.get_latest_resource_path("hivdb_xml", resource_dir=str(resource_dir))
    assert latest == str(resource_dir / "HIVDB_10.1.xml")


def test_select_latest_hivdb_xml_ignores_nonmatching_files(tmp_path):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()
    (resource_dir / "HIVDB_10.1.xml").write_text("a")
    (resource_dir / "HIVDB_latest.xml").write_text("b")
    (resource_dir / "HIVDB_9.9.xml").write_text("c")

    latest = ru.select_latest_hivdb_xml(resource_dir.glob("HIVDB_*.xml"))
    assert latest == resource_dir / "HIVDB_10.1.xml"


def test_get_latest_resource_path_returns_none_when_missing(tmp_path):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()
    assert (
        ru.get_latest_resource_path("apobec_drms", resource_dir=str(resource_dir))
        is None
    )
