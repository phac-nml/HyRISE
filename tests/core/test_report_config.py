import os
import subprocess
import shutil
import yaml
import base64
import pytest
from types import SimpleNamespace
from unittest import mock
from bs4 import BeautifulSoup
from typing import Dict, Tuple
from hyrise.core.report_config import HyRISEReportGenerator
from pathlib import Path


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

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: DummyResult())
    success, out = gen.run_multiqc()
    assert success is True
    assert out == "ok"


def test_run_multiqc_failure(monkeypatch, tmp_path):
    gen = HyRISEReportGenerator(output_dir=str(tmp_path))
    gen.config_path = str(tmp_path / "cfg.yml")
    open(gen.config_path, "w").close()
    gen.report_dir = str(tmp_path / "multiqc_report")

    # Stub subprocess.run to raise
    def fake_run(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="err")

    monkeypatch.setattr(subprocess, "run", fake_run)
    success, err = gen.run_multiqc()
    assert success is False
    assert "err" in err


def test_post_process_report_flow(monkeypatch, tmp_path):
    report_dir = tmp_path / "multiqc_report"
    report_dir.mkdir()
    html = report_dir / "hyrise_resistance_report.html"
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


class TestHtmlModification:

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        with mock.patch("logging.getLogger") as mock_logger:
            logger_instance = mock.MagicMock()
            mock_logger.return_value = logger_instance
            yield logger_instance

    @pytest.fixture
    def report_generator(self, mock_logger):
        """Create a report generator instance with mocked logger."""
        generator = HyRISEReportGenerator(
            output_dir="/tmp/test_output",
            version="0.2.1",
            sample_name="Test Sample",
        )
        # Override the logger with our mock
        generator.logger = mock_logger
        return generator

    @pytest.fixture
    def test_dir(self, tmp_path):
        """Create a temporary directory for test files."""
        test_path = tmp_path / "test_hyrise"
        test_path.mkdir()
        yield test_path
        # Cleanup
        shutil.rmtree(test_path)

    @pytest.fixture
    def sample_html_path(self, test_dir):
        """Create a sample MultiQC HTML file for testing."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta name="description" content="MultiQC report for bioinformatics analyses">
            <title>MultiQC Report</title>
            <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA...">
        </head>
        <body>
            <div class="navbar navbar-default navbar-fixed-top">
                <div class="container-fluid">
                    <div class="navbar-header">
                        <a class="navbar-brand" href="#">
                            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA..." alt="MultiQC">
                        </a>
                        <h1>MultiQC <small class="hidden-xs">v1.14</small></h1>
                    </div>
                </div>
            </div>
            <div class="mainpage">
                <div id="page_title">
                    <h1>MultiQC Report</h1>
                </div>
                <p class="lead">MultiQC is a modular tool to aggregate results from bioinformatics analyses across many samples.</p>
                <div id="mqc_welcome" class="well">
                    <h3>Welcome to MultiQC</h3>
                    <p>This report contains results from a bioinformatics analysis.</p>
                </div>
                <div id="mqc_about">
                    <h4>About MultiQC</h4>
                    <p>MultiQC is a tool to create aggregate reports.</p>
                    <p>For more information, please see <a href="https://multiqc.info">multiqc.info</a></p>
                </div>
                <div id="mqc_citing">
                    <h4>Citing MultiQC</h4>
                    <p>If you use MultiQC in your publication, please cite it:</p>
                    <blockquote>
                        <strong>MultiQC: Summarize analysis results for multiple tools</strong><br>
                        <em>Ewels P, et al.</em><br>
                        Bioinformatics. 2016;32(19):3047-8
                    </blockquote>
                </div>
                <div id="mqc_toolbox">
                    <h3>MultiQC Toolbox</h3>
                    <p>Various tools and settings to configure your report</p>
                </div>
            </div>
            <footer class="footer">
                <div class="container-fluid">
                    <p>MultiQC v1.14 - developed by <a href="https://github.com/ewels">Phil Ewels</a></p>
                    <p>Maintained at <a href="https://github.com/MultiQC/MultiQC">github.com/MultiQC/MultiQC</a></p>
                </div>
            </footer>
        </body>
        </html>
        """
        html_path = test_dir / "test_multiqc_report.html"
        html_path.write_text(html_content)
        return str(html_path)

    @pytest.fixture
    def minimal_html_path(self, test_dir):
        """Create a minimal HTML file to test fallback mechanisms."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MultiQC Report</title>
        </head>
        <body>
            <h1>MultiQC Report</h1>
            <p>This is a minimal report structure.</p>
        </body>
        </html>
        """
        html_path = test_dir / "minimal_multiqc_report.html"
        html_path.write_text(html_content)
        return str(html_path)

    @pytest.fixture
    def complex_html_path(self, test_dir):
        """Create a more complex HTML structure to test robust selectors."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MultiQC Report - Complex Structure</title>
        </head>
        <body>
            <header>
                <div class="logo-container">
                    <img src="data:image/png;base64,AAAA" alt="Report Logo">
                </div>
                <div class="version-container">
                    <span>v1.14.2</span>
                </div>
            </header>
            <main>
                <section class="welcome">
                    <h2>Introduction</h2>
                    <p>Welcome to the MultiQC report.</p>
                </section>
                <section>
                    <h3>About This Report</h3>
                    <p>Generated by MultiQC, a tool for aggregating bioinformatics results.</p>
                </section>
            </main>
            <div class="mqc-toolbox">
                <h4>Tools and Options</h4>
            </div>
            <div class="citations">
                <h4>How to Cite</h4>
                <p>Please reference MultiQC in your publications.</p>
            </div>
            <footer>
                <p>Powered by MultiQC</p>
            </footer>
        </body>
        </html>
        """
        html_path = test_dir / "complex_multiqc_report.html"
        html_path.write_text(html_content)
        return str(html_path)

    @pytest.fixture
    def mock_favicon_path(self, test_dir):
        """Create a mock favicon file."""
        favicon_path = test_dir / "assets"
        favicon_path.mkdir(exist_ok=True)

        favicon_file = favicon_path / "favicon.svg"
        favicon_file.write_text("<svg>Mock Favicon</svg>")

        # Monkeypatch the paths that are checked in the function
        with mock.patch("pathlib.Path") as MockPath:
            MockPath.return_value = favicon_path
            MockPath.side_effect = lambda x: (
                favicon_path / x if isinstance(x, str) and "assets" in x else Path(x)
            )
            yield str(favicon_file)

    @pytest.fixture
    def logo_data_uri(self):
        """Create a sample logo data URI."""
        mock_logo = "<svg>Mock Logo</svg>"
        encoded = base64.b64encode(mock_logo.encode()).decode()
        return f"data:image/svg+xml;base64,{encoded}"

    def test_successful_modification(
        self, report_generator, sample_html_path, logo_data_uri
    ):
        """Test that the function successfully modifies the HTML."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            sample_html_path, logo_data_uri
        )

        # Check the result
        assert success is True
        assert any(modifications.values()), "No modifications were made"

        # Check that the file was modified
        with open(sample_html_path, "r") as f:
            modified_html = f.read()

        # Parse the modified HTML to check specific changes
        soup = BeautifulSoup(modified_html, "html.parser")

        # Check title modification
        assert "HyRISE" in soup.title.string
        assert "MultiQC" not in soup.title.string

        # Check logo modification if logo was provided
        if logo_data_uri and modifications["logo"]:
            img_tags = soup.find_all("img")
            assert any(
                img["src"] == logo_data_uri for img in img_tags if "src" in img.attrs
            )

        # Check footer replacement
        footer = soup.find(class_="footer") or soup.find("footer")
        assert footer is not None
        assert "HyRISE" in footer.get_text()

        # Verify at least some modifications were made
        expected_mods = ["title", "footer", "about_section", "welcome"]
        assert any(modifications[key] for key in expected_mods)

        # Check that MultiQC attribution is still present
        about_section = soup.find(id="mqc_about")
        if about_section:
            assert "MultiQC" in about_section.get_text()

    def test_minimal_html_structure(
        self, report_generator, minimal_html_path, logo_data_uri
    ):
        """Test modification of a minimal HTML structure to ensure fallbacks work."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            minimal_html_path, logo_data_uri
        )

        # Should succeed even with minimal HTML
        assert success is True

        # Check that at least title was modified
        assert modifications["title"] is True

        # Verify the title change in the file
        with open(minimal_html_path, "r") as f:
            modified_html = f.read()

        soup = BeautifulSoup(modified_html, "html.parser")
        assert "HyRISE" in soup.title.string
        if logo_data_uri and modifications["logo"]:
            assert any(
                img.get("src") == logo_data_uri for img in soup.find_all("img")
            )

    def test_complex_html_structure(
        self, report_generator, complex_html_path, logo_data_uri
    ):
        """Test modification of a more complex HTML structure to test selector robustness."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            complex_html_path, logo_data_uri
        )

        # Should succeed even with complex HTML
        assert success is True

        # Check that some modifications were made
        with open(complex_html_path, "r") as f:
            modified_html = f.read()

        soup = BeautifulSoup(modified_html, "html.parser")

        # At minimum, title should be changed
        assert "HyRISE" in soup.title.string

        # Check welcome section if it was modified
        if modifications["welcome"]:
            welcome = soup.find(class_="welcome")
            if welcome:
                # Check for the actual title used in the implementation
                assert "HIV Resistance Analysis Report" in welcome.get_text()
                # Check for the presence of expected content
                assert (
                    "summarizes HIV drug resistance mutations detected in your sample"
                    in welcome.get_text()
                )

    def test_file_not_found(self, report_generator, test_dir, logo_data_uri):
        """Test behavior when HTML file doesn't exist."""
        non_existent_path = os.path.join(test_dir, "non_existent.html")

        # Run the modification
        success, modifications = report_generator.modify_html(
            non_existent_path, logo_data_uri
        )

        # Should fail gracefully
        assert success is False
        assert not any(modifications.values())

        # Check logging
        report_generator.logger.error.assert_called()

    @mock.patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_permission_error(
        self, mock_open, report_generator, sample_html_path, logo_data_uri
    ):
        """Test behavior when file cannot be opened due to permissions."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            sample_html_path, logo_data_uri
        )

        # Should fail gracefully
        assert success is False
        assert not any(modifications.values())

        # Check logging
        report_generator.logger.error.assert_called()

    def test_html_parse_error(self, report_generator, test_dir, logo_data_uri):
        """Test behavior when HTML cannot be processed."""
        # Instead of invalid HTML, force an error in processing
        with mock.patch(
            "builtins.open",
            side_effect=[
                # First call works (to read the file)
                mock.mock_open(
                    read_data="<html><head><title>Test</title></head><body></body></html>"
                )(),
                # Second call fails (when trying to write modifications)
                IOError("Simulated write error"),
            ],
        ):
            random_path = os.path.join(test_dir, "test.html")

            # Run the modification - should fail on write
            success, modifications = report_generator.modify_html(
                random_path, logo_data_uri
            )

            # Should definitely fail
            assert not success

            # Error should be logged
            report_generator.logger.error.assert_called()

    def test_without_logo(self, report_generator, sample_html_path):
        """Test modification without providing a logo."""
        # Run the modification without logo
        success, modifications = report_generator.modify_html(sample_html_path, "")

        # Should succeed but logo not modified
        assert success is True
        assert modifications["logo"] is False

        # Other modifications should still happen
        assert any(modifications.values())

    def test_svg_logo_replacement_for_modern_multiqc_structure(
        self, report_generator, test_dir, logo_data_uri
    ):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>MultiQC Report</title></head>
        <body>
          <h1 class="side-nav-logo">
            <svg class="multiqc-logo" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>
          </h1>
        </body>
        </html>
        """
        html_path = test_dir / "svg_logo_multiqc.html"
        html_path.write_text(html_content)

        success, modifications = report_generator.modify_html(str(html_path), logo_data_uri)
        assert success is True
        assert modifications["logo"] is True

        soup = BeautifulSoup(html_path.read_text(), "html.parser")
        assert soup.select_one("svg.multiqc-logo") is None
        injected = soup.select_one("h1.side-nav-logo img")
        assert injected is not None
        assert injected.get("src") == logo_data_uri

    def test_logo_wrapper_anchor_scoped_to_logo_only(
        self, report_generator, test_dir, logo_data_uri
    ):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>MultiQC Report</title></head>
        <body>
          <a href="https://github.com/phac-nml/HyRISE" target="_blank">
            <div class="multiqc-logo-wrapper">
              <img src="old-logo.svg" alt="MultiQC logo"/>
              <span class="title-text">HyRISE Report</span>
            </div>
          </a>
        </body>
        </html>
        """
        html_path = test_dir / "logo_wrapper_anchor_scope.html"
        html_path.write_text(html_content)

        success, _ = report_generator.modify_html(str(html_path), logo_data_uri)
        assert success is True

        soup = BeautifulSoup(html_path.read_text(), "html.parser")
        wrapper = soup.select_one(".multiqc-logo-wrapper")
        assert wrapper is not None
        assert wrapper.parent.name != "a"
        logo_link = wrapper.find("a")
        assert logo_link is not None
        assert logo_link.find("img") is not None
        assert wrapper.select_one(".title-text").find_parent("a") is None

    # def test_with_favicon(self, report_generator, sample_html_path, mock_favicon_path, logo_data_uri):
    #     """Test modification with favicon path accessible."""
    #     with mock.patch.object(PathLib.Path, 'exists', return_value=True):
    #         with mock.patch('builtins.open', mock.mock_open(read_data=b'<svg>Mock Favicon</svg>')):
    #             success, modifications = report_generator.modify_html(sample_html_path, logo_data_uri)

    #     # Should succeed with favicon modification
    #     assert success is True
    #     assert modifications["favicon"] is True

    def test_backup_creation(self, report_generator, sample_html_path, logo_data_uri):
        """Test that a backup file is created."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            sample_html_path, logo_data_uri
        )

        # Check for backup file
        backup_path = f"{sample_html_path}.backup"
        assert os.path.exists(backup_path)

        # Backup should contain original content
        with open(backup_path, "r") as f:
            backup_content = f.read()

        assert "MultiQC Report" in backup_content
        assert "HyRISE" not in backup_content

    @mock.patch("shutil.copy2", side_effect=Exception("Copy failed"))
    def test_backup_failure(
        self, mock_copy, report_generator, sample_html_path, logo_data_uri
    ):
        """Test behavior when backup creation fails."""
        # Run the modification
        success, modifications = report_generator.modify_html(
            sample_html_path, logo_data_uri
        )

        # Should still succeed even if backup fails
        assert success is True
        assert any(modifications.values())

        # Check logging
        report_generator.logger.warning.assert_called()

    @mock.patch.object(HyRISEReportGenerator, "modify_html")
    def test_post_process_report(
        self, mock_modify, report_generator, sample_html_path, logo_data_uri
    ):
        """Test the post_process_report method that calls modify_html."""
        # Set up mock return value
        mock_modify.return_value = (True, {"title": True, "footer": True})

        # Create report directory
        report_dir = os.path.dirname(sample_html_path)
        os.makedirs(report_dir, exist_ok=True)

        # Copy sample HTML to expected report path
        report_path = os.path.join(report_dir, "multiqc_report.html")
        shutil.copy2(sample_html_path, report_path)

        # Set report directory in report generator
        report_generator.report_dir = report_dir

        # Run post-processing
        success, modifications = report_generator.post_process_report(logo_path=None)

        # Verify modify_html was called correctly
        mock_modify.assert_called_once()
        assert success is True
        assert modifications == {"title": True, "footer": True}
