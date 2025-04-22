import os
import subprocess
import shutil
import yaml
import base64
import pytest
from pathlib import Path
from types import SimpleNamespace
from hyrise.core.report_config import HyRISEReportGenerator


@pytest.fixture
def temp_logo_file(tmp_path):
    # Create a small PNG file
    logo = tmp_path / "logo.png"
    content = b"\x89PNG\r\n\x1a\n"  # PNG header
    with open(logo, "wb") as f:
        f.write(content)
    return str(logo)


def test_embed_logo_not_found(tmp_path, caplog):
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    # Non-existent path
    data_uri = gen.embed_logo(logo_path=str(tmp_path / "nofile.png"))
    assert data_uri == ""
    # Should log a warning
    assert "using fallback" in caplog.text.lower()


def test_embed_logo_png(tmp_path, temp_logo_file, caplog):
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    caplog.set_level("INFO")
    uri = gen.embed_logo(logo_path=temp_logo_file)
    assert uri.startswith("data:image/png;base64,")
    # Decoded should start with PNG header
    decoded = base64.b64decode(uri.split(",")[1])
    assert decoded.startswith(b"\x89PNG")
    assert "Found logo file" in caplog.text


def test_create_metadata_summary_empty():
    gen = HyRISEReportGenerator(output_dir=".", sample_name="test")
    data = {}
    summary = gen.create_metadata_summary(data)
    # Check keys exist
    assert "sample_id" in summary
    assert "analysis_date" in summary
    assert "database" in summary
    assert isinstance(summary["genes"], dict)
    assert summary["database"]["version"] == "Unknown"


def test_generate_config_and_file(tmp_path):
    out = tmp_path / "out"
    gen = HyRISEReportGenerator(
        output_dir=str(out), version="1.2.3", sample_name="S1", contact_email="a@b.com"
    )
    # Provide some metadata_info
    gen.metadata_info = {
        "sample_id": "S1",
        "analysis_date": "2025-04-21 00:00:00",
        "genes": {"PR": {"mutations_count": 5, "sdrm_count": 2}},
        "database": {"version": "9.9", "publish_date": "2025-01-01"},
    }
    config_path = gen.generate_config()
    # File exists
    assert os.path.exists(config_path)
    cfg = yaml.safe_load(open(config_path))
    # Validate some keys
    assert cfg["title"].startswith("HyRISE")
    assert any(h.get("Contact E-mail") for h in cfg["report_header_info"])
    # Check CSS asset written
    css_files = cfg.get("custom_css_files", [])
    assert css_files
    assert os.path.exists(css_files[0])


def test_run_multiqc_success(monkeypatch, tmp_path):
    outdir = tmp_path / "out"
    gen = HyRISEReportGenerator(output_dir=str(outdir))
    # Create dummy config file and report dir
    os.makedirs(str(outdir), exist_ok=True)
    gen.config_path = str(outdir / "cfg.yml")
    open(gen.config_path, "w").close()
    gen.report_dir = str(outdir / "multiqc_report")

    # Stub subprocess.run
    class DummyResult:
        returncode = 0
        stdout = "ok"

    monkeypatch.setattr(
        subprocess, "run", lambda cmd, shell, check, capture_output, text: DummyResult()
    )
    success, out = gen.run_multiqc()
    assert success is True
    assert out == "ok"


def test_run_multiqc_failure(monkeypatch, tmp_path):
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    gen.config_path = str(tmp_path / "cfg.yml")
    open(gen.config_path, "w").close()
    gen.report_dir = str(tmp_path / "multiqc_report")

    # Stub subprocess.run to raise
    def fake_run(cmd, shell, check, capture_output, text):
        raise subprocess.CalledProcessError(1, cmd, stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    success, err = gen.run_multiqc()
    assert success is False
    assert "err" in err


def test_modify_html(tmp_path):
    # Create minimal HTML
    html = tmp_path / "test.html"
    content = """<html><head><title>Old</title><link rel="icon" type="image/png" href="old.ico"><meta name="description" content="multiqc desc"></head><body>\
<h3>MultiQC Toolbox</h3><img src="data:image/png;base64,AAA"><footer>foot</footer>\
<h4>About MultiQC</h4><p>Info MultiQC</p><div id="mqc_welcome">Welcome</div></body></html>"""
    html.write_text(content)
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    logo_uri = "data:image/png;base64,BBB"
    success, mods = gen.modify_html(str(html), logo_uri)
    assert success is True
    # Check flags
    assert mods["logo"] is True
    assert mods["title"] is True
    assert mods["toolbox"] is True
    assert mods["footer"] is True
    assert mods["about_section"] is True
    assert mods["welcome"] is True
    assert mods["favicon"] is True
    # Read back
    new = html.read_text()
    assert "<title>HyRISE Report</title>" in new
    assert "BBB" in new
    assert "HyRISE Toolbox" in new or "HyRISE" in new


def test_post_process_report_flow(monkeypatch, tmp_path):
    report_dir = tmp_path / "multiqc_report"
    report_dir.mkdir()
    html = report_dir / "multiqc_report.html"
    html.write_text("<html></html>")
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    gen.report_dir = str(report_dir)
    # Stub embed_logo and modify_html
    monkeypatch.setattr(gen, "embed_logo", lambda path=None: "XYZ")
    monkeypatch.setattr(gen, "modify_html", lambda path, uri: (True, {"foo": True}))
    success, mods = gen.post_process_report()
    # Backup exists
    assert os.path.exists(str(html) + ".backup")
    assert success is True
    assert mods == {"foo": True}


def test_generate_report_full(monkeypatch, tmp_path):
    # Setup directories
    inp = tmp_path / "data.json"
    content = {"key": "val"}
    inp.write_text(yaml.dump(content))
    out = tmp_path / "out"
    # Stub run_multiqc and post_process_report
    gen = HyRISEReportGenerator(output_dir=str(out))
    monkeypatch.setattr(HyRISEReportGenerator, "run_multiqc", lambda self: (True, ""))
    monkeypatch.setattr(
        HyRISEReportGenerator, "post_process_report", lambda self, logo: (True, {})
    )
    # Run generate_report
    results = gen.generate_report(
        input_data_path=str(inp), logo_path=None, run_multiqc=True, skip_html_mod=False
    )
    assert results["config_generated"] is True
    assert results["multiqc_run"] is True
    assert results["html_modified"] is True
    # report_path may not exist since no real html, so allow None or correct key
    assert "report_path" in results
