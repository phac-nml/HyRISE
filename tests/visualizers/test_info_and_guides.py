import os
import json
import pytest

from hyrise.visualizers.info_and_guides import (
    create_sample_analysis_info,
    create_interpretation_guides,
    create_unified_report_section,
)


@pytest.fixture
def dummy_info_data():
    # minimal data with version entries, one gene, and a validation result
    data = {
        "drugResistance": [
            {
                "gene": {"name": "GENE1"},
                "version": {"text": "v1.2.3", "publishDate": "2020-01-01"},
            }
        ],
        "alignedGeneSequences": [
            {
                "gene": {"name": "GENE1"},
                "firstAA": 5,
                "lastAA": 100,
                "mutations": [{"text": "X1"}],
                "SDRMs": [],
            }
        ],
        "validationResults": [{"level": "WARNING", "message": "Test warning"}],
    }
    return data


def test_create_sample_analysis_info(tmp_path, dummy_info_data):
    out = tmp_path / "out"
    out.mkdir()
    # run with one validation result to exercise HTML output
    create_sample_analysis_info(
        dummy_info_data,
        sample_id="S1",
        formatted_date="2025-04-21 12:00:00",
        output_dir=str(out),
    )
    # JSON tables
    assert (out / "sample_info_table_mqc.json").exists()
    assert (out / "gene_info_table_mqc.json").exists()
    # sequence validation HTML
    seq_val = out / "sequence_validation_mqc.html"
    assert seq_val.exists()
    html = seq_val.read_text()
    assert "<h3>Sequence Validation</h3>" in html
    assert "Test warning" in html

    # check sample_info content
    info = json.loads((out / "sample_info_table_mqc.json").read_text())
    assert info["id"] == "sample_info_table"
    assert "S1" in info["data"]
    gene = json.loads((out / "gene_info_table_mqc.json").read_text())
    assert gene["id"] == "gene_info_table"
    # row id is sample_id_geneName
    assert any(r.startswith("S1_GENE1") for r in gene["data"])


def test_create_sample_analysis_info_escapes_validation_html(tmp_path, dummy_info_data):
    out = tmp_path / "out"
    out.mkdir()
    dummy_info_data["validationResults"] = [
        {"level": "<img>", "message": "<script>alert(1)</script>"}
    ]
    create_sample_analysis_info(
        dummy_info_data,
        sample_id="S1",
        formatted_date="2025-04-21 12:00:00",
        output_dir=str(out),
    )
    html = (out / "sequence_validation_mqc.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_create_interpretation_guides(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    create_interpretation_guides(str(out))
    expected = [
        "resistance_interpretation_table_mqc.json",
        "mutation_type_table_mqc.json",
        "drug_class_info_table_mqc.json",
    ]
    for fn in expected:
        p = out / fn
        assert p.exists(), f"{fn} was not created"
        j = json.loads(p.read_text())
        # ID should be the filename without the "_mqc.json" suffix
        expected_id = fn.replace("_mqc.json", "")
        assert (
            j.get("id") == expected_id
        ), f"Expected id {expected_id}, got {j.get('id')}"


def test_create_unified_report_section(tmp_path, dummy_info_data):
    out = tmp_path / "out"
    out.mkdir()
    create_unified_report_section(
        dummy_info_data,
        sample_id="S1",
        formatted_date="2025-04-21 12:00:00",
        output_dir=str(out),
    )
    # unified HTML
    uni = out / "unified_report_section_mqc.html"
    assert uni.exists()
    html = uni.read_text()
    # should start with our header comment block and include section titles
    assert "<!--" in html and "id: 'unified_hiv_report_section'" in html
    assert "About This Report" in html
    # also underlying tables should have been generated
    assert (out / "sample_info_table_mqc.json").exists()
    assert (out / "resistance_interpretation_table_mqc.json").exists()
