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
        lambda *args, **kwargs: {
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


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    # Prevent ensure_dependencies from raising or invoking containers
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda *args, **kwargs: {
            "use_container": False,
            "multiqc_available": False,
        },
    )


def make_stub_writer(fn_name):
    """
    Return a stub function that writes an empty {sample_name}_{fn_name}_mqc.json
    into the output_dir when called.
    """

    def stub(data_item, sample_name, output_dir, *args, **kwargs):
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{sample_name}_{fn_name}_mqc.json")
        with open(out_path, "w") as f:
            json.dump({}, f)

    return stub


def test_process_files_basic(tmp_path, monkeypatch):
    # 1) Create a dummy JSON file name so extract_sample_id returns "sample"
    sample_json = tmp_path / "sample_NGS_results.json"
    sample_json.write_text("{}")

    # 2) Stub load_json_file to return one entry that WILL be processed
    monkeypatch.setattr(
        processor_module,
        "load_json_file",
        lambda path, preserve_list=True: [
            {
                "inputSequence": {"header": "H1"},
                "alignedGeneSequences": [
                    {
                        "gene": {"name": "G"},
                        "firstAA": 1,
                        "lastAA": 1,
                        "mutations": [],
                        "SDRMs": [],
                    }
                ],
                "drugResistance": [{}],
                "validationResults": [],
            }
        ],
    )

    # 3) Stub ensure_dependencies to a no‑op
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda *args, **kwargs: {
            "use_container": False,
            "multiqc_available": False,
        },
    )

    # 4) Stub each visualization function to write a fake _mqc.json file
    def make_stub(fn_name):
        def stub(data, sample_name, output_dir, *args, **kwargs):
            os.makedirs(output_dir, exist_ok=True)
            with open(
                os.path.join(output_dir, f"{sample_name}_{fn_name}_mqc.json"), "w"
            ) as f:
                f.write("{}")

        return stub

    viz_fns = [
        "create_drug_resistance_profile",
        "create_drug_class_resistance_summary",
        "create_mutation_resistance_contribution",
        "create_mutation_clinical_commentary",
        "create_mutation_details_table",
        "create_mutation_position_visualization",
        "create_mutation_type_summary",
    ]
    for fn in viz_fns:
        monkeypatch.setattr(processor_module, fn, make_stub(fn))

    # 5) Run process_files
    output_dir = tmp_path / "out"
    results = processor_module.process_files(
        json_file=str(sample_json),
        output_dir=str(output_dir),
    )

    # 6a) sample_name should be “sample”
    assert results["sample_name"] == "sample"

    # 6b) Each stub produced its _mqc.json file
    for fn in viz_fns:
        p = output_dir / f"sample_{fn}_mqc.json"
        assert p.exists(), f"Missing {p}"


def test_process_files_with_guide_and_sample_info(tmp_path, monkeypatch):
    # 1) Create a dummy JSON file so extract_sample_id -> "sample"
    sample_json = tmp_path / "sample_NGS_results.json"
    sample_json.write_text("{}")

    # 2) Stub load_json_file to return one processable entry
    monkeypatch.setattr(
        processor_module,
        "load_json_file",
        lambda path, preserve_list=True: [
            {
                "inputSequence": {"header": "H1"},
                "alignedGeneSequences": [
                    {
                        "gene": {"name": "G"},
                        "firstAA": 1,
                        "lastAA": 1,
                        "mutations": [],
                        "SDRMs": [],
                    }
                ],
                "drugResistance": [{}],
                "validationResults": [],
            }
        ],
    )

    # 3) Stub ensure_dependencies so nothing blows up
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda *args, **kwargs: {
            "use_container": False,
            "multiqc_available": False,
        },
    )

    # 4) Stub the core viz functions to no‑ops
    for fn in [
        "create_drug_resistance_profile",
        "create_drug_class_resistance_summary",
        "create_mutation_resistance_contribution",
        "create_mutation_clinical_commentary",
        "create_mutation_details_table",
        "create_mutation_position_visualization",
        "create_mutation_type_summary",
    ]:
        monkeypatch.setattr(processor_module, fn, lambda *args, **kwargs: None)

    # 5) Stub guide + info to write actual files
    def stub_guide(data_item, sample_name, formatted_date, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        open(os.path.join(output_dir, f"{sample_name}_guide_mqc.json"), "w").close()

    def stub_info(data_item, sample_name, formatted_date, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        open(os.path.join(output_dir, f"{sample_name}_info_mqc.json"), "w").close()

    monkeypatch.setattr(processor_module, "create_unified_report_section", stub_guide)
    monkeypatch.setattr(processor_module, "create_sample_analysis_info", stub_info)

    # 6) Run with guide + sample_info
    output_dir = tmp_path / "out"
    results = processor_module.process_files(
        json_file=str(sample_json),
        output_dir=str(output_dir),
        guide=True,
        sample_info=True,
    )

    # 7a) Check that the stub files exist
    guide_path = output_dir / "sample_guide_mqc.json"
    info_path = output_dir / "sample_info_mqc.json"
    assert guide_path.exists(), f"Expected {guide_path} to be created"
    assert info_path.exists(), f"Expected {info_path} to be created"

    # 7b) And that they were recorded in results["files_generated"]
    assert str(guide_path) in results["files_generated"]
    assert str(info_path) in results["files_generated"]


def test_generate_report_config_only(tmp_path, monkeypatch):
    json_file = write_json(tmp_path, {"a": 1})
    output_dir = tmp_path / "out"

    # 1) Stub ensure_dependencies
    monkeypatch.setattr(
        processor_module,
        "ensure_dependencies",
        lambda *args, **kwargs: {
            "use_container": False,
            "container_path": None,
            "multiqc_available": False,
        },
    )

    # 2) Fake report generator with full __init__ signature
    class FakeGen:
        def __init__(
            self, output_dir, version, sample_name, metadata_info, contact_email
        ):
            # record where we'll write the config
            self.config_path = os.path.join(output_dir, "config.yml")

        def generate_config(self):
            # ensure the out dir exists (process_files already did this)
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                f.write("config")
            return self.config_path

    monkeypatch.setattr(processor_module, "HyRISEReportGenerator", FakeGen)

    # 3) Stub load_json_file so process_sequences doesn't error
    monkeypatch.setattr(
        processor_module,
        "load_json_file",
        lambda path, preserve_list=True: [],
    )

    # 4) Run with generate_report=True but run_multiqc=False
    results = processor_module.process_files(
        json_file=str(json_file),
        output_dir=str(output_dir),
        generate_report=True,
        run_multiqc=False,
        contact_email="test@example.com",
    )

    # 5) Now config_file must be set to our dummy path
    expected = os.path.join(str(output_dir), "config.yml")
    assert results["config_file"] == expected
    # And the file must exist on disk
    assert os.path.exists(expected)
    # report_dir should also be set
    assert results["report_dir"] == os.path.join(str(output_dir), "multiqc_report")
    # multiqc_command stays None because multiqc_available is False
    assert results["multiqc_command"] is None
