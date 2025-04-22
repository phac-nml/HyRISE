import os
import json
import glob
import pytest

from hyrise.visualizers.hiv_visualizations import (
    create_mutation_details_table,
    create_mutation_position_visualization,
    create_mutation_type_summary,
    create_drug_resistance_profile,
    create_drug_class_resistance_summary,
    create_mutation_resistance_contribution,
    create_mutation_clinical_commentary,
)


@pytest.fixture
def dummy_data():
    data = {
        "alignedGeneSequences": [
            {
                "gene": {"name": "TEST"},
                "SDRMs": [{"text": "M1"}],
                "mutations": [
                    {
                        "text": "M1",
                        "primaryType": "Major",
                        "position": 10,
                        "isApobecMutation": False,
                        "isUnusual": False,
                    },
                    {
                        "text": "M2",
                        "primaryType": "Accessory",
                        "position": 20,
                        "isApobecMutation": True,
                        "isUnusual": True,
                    },
                ],
                "firstAA": 1,
                "lastAA": 30,
            }
        ],
        "drugResistance": [
            {
                "gene": {"name": "TEST"},
                "drugScores": [
                    {
                        "drug": {"displayAbbr": "D1"},
                        "drugClass": {"name": "CL"},
                        "text": "Low-Level",
                        "score": 5,
                        "level": 3,
                        "partialScores": [
                            {
                                "score": 5,
                                "mutations": [
                                    {
                                        "text": "M1",
                                        "primaryType": "Major",
                                        "isSDRM": True,
                                    },
                                    {
                                        "text": "M2",
                                        "primaryType": "Accessory",
                                        "isSDRM": False,
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "drug": {"displayAbbr": "D2"},
                        "drugClass": {"name": "CL"},
                        "text": "High-Level",
                        "score": 20,
                        "level": 5,
                        "partialScores": [
                            {
                                "score": 15,
                                "mutations": [
                                    {
                                        "text": "M2",
                                        "primaryType": "Accessory",
                                        "isSDRM": False,
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ],
    }
    # Inject a clinical 'comments' field so clinical commentary is generated
    for dr in data["drugResistance"]:
        for ds in dr["drugScores"]:
            for partial in ds["partialScores"]:
                for mut in partial["mutations"]:
                    mut["comments"] = [{"text": "Clinical implication here"}]
    return data


def test_create_mutation_details_table(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_mutation_details_table(dummy_data, sample_id="S1", output_dir=str(out))
    files = list(out.glob("mutation_details_test_mqc.json"))
    assert files, "mutation_details JSON not created"
    tbl = json.loads(files[0].read_text())
    assert tbl["id"].startswith("mutation_details_test_table")
    # row_id should be "{sample_id}_{mutation_text}"
    assert "data" in tbl and "S1_M1" in tbl["data"]
    assert "S1_M2" in tbl["data"]


def test_create_mutation_position_visualization(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_mutation_position_visualization(
        dummy_data, sample_id="S1", output_dir=str(out)
    )
    files = list(out.glob("mutation_position_map_test_mqc.html"))
    assert files, "position map HTML not created"
    html = files[0].read_text()
    # check header and a tooltip snippet
    assert "<h3>TEST Mutation Position Map</h3>" in html
    assert "position-tooltip" in html


def test_create_mutation_type_summary(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_mutation_type_summary(dummy_data, sample_id="S1", output_dir=str(out))
    files = list(out.glob("mutation_summary_test_mqc.json"))
    assert files, "mutation summary JSON not created"
    summ = json.loads(files[0].read_text())
    assert summ["id"].startswith("mutation_summary_test_table")
    assert "Major" in summ["data"]


def test_create_drug_resistance_profile(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_drug_resistance_profile(dummy_data, sample_id="S1", output_dir=str(out))
    files = list(out.glob("drug_resistance_test_table_mqc.json"))
    assert files, "drug resistance profile JSON not created"
    prof = json.loads(files[0].read_text())
    assert prof["id"].startswith("drug_resistance_test_table")
    # check that row keys include our sample/drug
    row_keys = prof["data"].keys()
    assert any("S1_D1" in rk for rk in row_keys)


def test_create_drug_class_resistance_summary(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_drug_class_resistance_summary(
        dummy_data, sample_id="S1", output_dir=str(out)
    )
    files = list(out.glob("drug_class_overview_test_table_mqc.json"))
    assert files, "drug class overview JSON not created"
    tbl = json.loads(files[0].read_text())
    assert tbl["id"].startswith("drug_class_overview_test_table")
    assert "CL" in {v["Drug Class"] for v in tbl["data"].values()}


def test_create_mutation_resistance_contribution(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_mutation_resistance_contribution(
        dummy_data, sample_id="S1", output_dir=str(out)
    )
    files = list(out.glob("mutation_contribution_test_mqc.json"))
    assert files, "mutation contribution JSON not created"
    ctr = json.loads(files[0].read_text())
    assert ctr["id"].startswith("mutation_contribution_test_table")
    # Only "D2" meets the ≥15 score threshold in our dummy data
    assert any("D2" in entry["Drug"] for entry in ctr["data"].values())


def test_create_mutation_clinical_commentary(tmp_path, dummy_data):
    out = tmp_path / "out"
    out.mkdir()
    create_mutation_clinical_commentary(dummy_data, sample_id="S1", output_dir=str(out))
    files = list(out.glob("mutation_clinical_test_table_mqc.json"))
    assert files, "mutation clinical commentary JSON not created"
    clinical = json.loads(files[0].read_text())
    assert clinical["id"].startswith("mutation_clinical_test_table")
    # ensure we have the expected keys
    exemplar = next(iter(clinical["data"].values()))
    assert "Clinical Implication" in exemplar
