import os
import json
import shutil
import subprocess
from datetime import datetime
import pytest

from types import SimpleNamespace
import hyrise.core.processor as processor_module


@pytest.fixture(autouse=True)
def stub_visualizations_and_dependencies(monkeypatch, tmp_path):
    # Stub ensure_dependencies to default native no multiqc
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda use_container: {
            "use_container": False,
            "container_path": None,
            "multiqc_available": False,
        },
    )

    # Stub visualization functions to create dummy '_mqc.json' files
    def make_stub(func_name):
        def stub(data, sample_name, *args, **kwargs):
            # args[-1] is output_dir
            output_dir = args[-1] if args else kwargs.get("output_dir")
            filepath = os.path.join(output_dir, f"{sample_name}_{func_name}_mqc.json")
            with open(filepath, "w") as f:
                f.write("{}")

        return stub

    vis_funcs = [
        "create_drug_resistance_profile",
        "create_drug_class_resistance_summary",
        "create_mutation_resistance_contribution",
        "create_mutation_clinical_commentary",
        "create_mutation_details_table",
        "create_mutation_position_visualization",
        "create_mutation_type_summary",
    ]
    for fn in vis_funcs:
        monkeypatch.setattr(processor_module, fn, make_stub(fn))
    # Stub info and guide
    monkeypatch.setattr(
        processor_module,
        "create_unified_report_section",
        lambda data, sample_name, formatted_date, output_dir: open(
            os.path.join(output_dir, f"{sample_name}_guide_mqc.json"), "w"
        ).close(),
    )
    monkeypatch.setattr(
        processor_module,
        "create_sample_analysis_info",
        lambda data, sample_name, formatted_date, output_dir: open(
            os.path.join(output_dir, f"{sample_name}_info_mqc.json"), "w"
        ).close(),
    )
    yield


def write_json(tmp_path, data):
    json_file = tmp_path / "sample.json"
    json_file.write_text(json.dumps(data))
    return str(json_file)


def test_process_files_basic(tmp_path):
    # Prepare JSON
    json_file = write_json(tmp_path, {"key": "value"})
    output_dir = tmp_path / "out"
    # Run process_files
    results = processor_module.process_files(
        json_file=str(json_file),
        output_dir=str(output_dir),
        # defaults: no report, no multiqc
    )
    # Check outputs
    assert results["json_file"] == os.path.abspath(json_file)
    assert results["output_dir"] == os.path.abspath(str(output_dir))
    assert results["sample_name"] == "sample"
    # All stub visualization files should be generated
    for fn in [
        "create_drug_resistance_profile",
        "create_drug_class_resistance_summary",
        "create_mutation_resistance_contribution",
        "create_mutation_clinical_commentary",
        "create_mutation_details_table",
        "create_mutation_position_visualization",
        "create_mutation_type_summary",
    ]:
        expected_file = os.path.join(str(output_dir), f"sample_{fn}_mqc.json")
        assert os.path.exists(expected_file)
        assert expected_file in results["files_generated"]
    # No report generated
    assert results["config_file"] is None
    assert results["report_dir"] is None
    assert results["multiqc_command"] is None
    assert results["container_used"] is False


def test_process_files_with_guide_and_sample_info(tmp_path):
    json_file = write_json(tmp_path, {"key": "value"})
    output_dir = tmp_path / "out"
    # Run with guide and sample_info
    results = processor_module.process_files(
        json_file=str(json_file),
        output_dir=str(output_dir),
        guide=True,
        sample_info=True,
    )
    # Guide and info stub files
    guide_file = os.path.join(str(output_dir), "sample_guide_mqc.json")
    info_file = os.path.join(str(output_dir), "sample_info_mqc.json")
    assert os.path.exists(guide_file)
    assert os.path.exists(info_file)
    # Included in files_generated
    assert guide_file in results["files_generated"]
    assert info_file in results["files_generated"]


def test_generate_report_config_only(tmp_path, monkeypatch):
    json_file = write_json(tmp_path, {"a": 1})
    output_dir = tmp_path / "out"
    # Override dependencies: no container, multiqc unavailable
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda use_container: {
            "use_container": False,
            "container_path": None,
            "multiqc_available": False,
        },
    )

    # Fake report generator
    class FakeGen:
        def __init__(self, output_dir, version, sample_name, contact_email):
            self.config_path = os.path.join(output_dir, "config.yml")

        def create_metadata_summary(self, data):
            return {"meta": "info"}

        def generate_config(self):
            # create dummy config file
            with open(self.config_path, "w") as f:
                f.write("config")
            return self.config_path

    monkeypatch.setattr(processor_module, "HyRISEReportGenerator", FakeGen)
    # Run with generate_report True, run_multiqc False
    results = processor_module.process_files(
        json_file=json_file,
        output_dir=str(output_dir),
        generate_report=True,
        run_multiqc=False,
        contact_email="test@example.com",
    )
    # Config file created
    assert results["config_file"] == os.path.join(str(output_dir), "config.yml")
    # No multiqc_command when dependencies missing
    assert results["multiqc_command"] is None
    # Report directory is set
    assert results["report_dir"] == os.path.join(str(output_dir), "multiqc_report")


def test_process_files_raises_on_error(monkeypatch, tmp_path):
    # Stub load_json_file to raise
    monkeypatch.setattr(
        processor_module,
        "load_json_file",
        lambda jf: (_ for _ in ()).throw(ValueError("bad json")),
    )
    json_file = write_json(tmp_path, {})
    output_dir = tmp_path / "out"
    with pytest.raises(ValueError):
        processor_module.process_files(
            json_file=str(json_file), output_dir=str(output_dir)
        )
