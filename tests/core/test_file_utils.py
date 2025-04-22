import os
import json
import pytest

from hyrise.core.file_utils import extract_sample_id, load_json_file
from hyrise.utils.html_utils import create_html_header, create_html_footer


# ----------------------------
# Tests for extract_sample_id
# ----------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("sample_NGS_results.json", "sample"),
        ("/path/to/another_sample_NGS_results.json", "another_sample"),
        ("just_a_file.json", "just_a_file"),
        ("nested.name.with.dots.json", "nested.name.with.dots"),
        ("/abs/path/foo.bar.json", "foo.bar"),
    ],
)
def test_extract_sample_id_variants(filename, expected):
    assert extract_sample_id(filename) == expected


# -----------------------------
# Tests for load_json_file
# -----------------------------


def test_load_json_file_not_found(tmp_path):
    missing = tmp_path / "no_such.json"
    with pytest.raises(FileNotFoundError) as exc:
        load_json_file(str(missing))
    assert "not found" in str(exc.value)


def test_load_json_file_dict(tmp_path):
    data = {"a": 1, "b": 2}
    f = tmp_path / "data.json"
    f.write_text(json.dumps(data))

    # preserve_list=True should return the dict unchanged
    loaded = load_json_file(str(f), preserve_list=True)
    assert isinstance(loaded, dict)
    assert loaded == data

    # preserve_list=False on a dict should also return it unchanged
    loaded2 = load_json_file(str(f), preserve_list=False)
    assert isinstance(loaded2, dict)
    assert loaded2 == data


def test_load_json_file_list(tmp_path):
    data = [{"x": 10}, {"x": 20}]
    f = tmp_path / "list.json"
    f.write_text(json.dumps(data))

    # preserve_list=True returns the full list
    loaded = load_json_file(str(f), preserve_list=True)
    assert isinstance(loaded, list)
    assert loaded == data

    # preserve_list=False returns only the first element
    loaded_first = load_json_file(str(f), preserve_list=False)
    assert isinstance(loaded_first, dict)
    assert loaded_first == data[0]


# --------------------------------
# Tests for HTML utility functions
# --------------------------------


def test_create_html_header_basic():
    id_name = "sec1"
    section_name = "My Section"
    description = "This is a test section"
    header = create_html_header(id_name, section_name, description)

    # It should contain the MultiQC comment block and opening div
    expected = (
        "<!--\n"
        "id: 'sec1'\n"
        "section_name: 'My Section'\n"
        "description: 'This is a test section'\n"
        "-->\n"
        "<div class='mqc-custom-content'>\n"
    )
    assert header == expected


def test_create_html_footer():
    assert create_html_footer() == "</div>"
