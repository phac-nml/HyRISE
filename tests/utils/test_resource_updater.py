from hyrise.utils import resource_updater as ru


class _DummyResponse:
    def __init__(self, content=b"", text=""):
        self.content = content
        self.text = text

    def raise_for_status(self):
        return None


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


def test_download_file_rejects_path_traversal_filename(monkeypatch, tmp_path):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()

    monkeypatch.setattr(ru.requests, "get", lambda *args, **kwargs: _DummyResponse())

    downloaded = ru.download_file(
        "https://example.com/file.txt",
        "../outside.txt",
        resource_dir=str(resource_dir),
    )
    assert downloaded is None
    assert not (tmp_path / "outside.txt").exists()


def test_update_hivdb_xml_rejects_unexpected_latest_filename(monkeypatch, tmp_path):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()

    def fake_get(url, *args, **kwargs):
        if url.endswith("/HIVDB_latest.xml"):
            return _DummyResponse(text="../../evil.xml")
        return _DummyResponse(content=b"xml")

    monkeypatch.setattr(ru.requests, "get", fake_get)

    result = ru.update_hivdb_xml(resource_dir=str(resource_dir))
    assert result is None
