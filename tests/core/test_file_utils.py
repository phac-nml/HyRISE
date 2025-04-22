import os
import json
import pytest
from hyrise.core.file_utils import extract_sample_id, load_json_file
from hyrise.utils.html_utils import create_html_header, create_html_footer

test_dir = os.path.dirname(__file__)


# Tests for extract_sample_id


def test_extract_sample_id_with_ngs_suffix():
    filename = "/path/to/sample123_NGS_results.json"
    assert extract_sample_id(filename) == "sample123"


def test_extract_sample_id_without_ngs_suffix():
    filename = "another_sample.json"
    assert extract_sample_id(filename) == "another_sample"


def test_extract_sample_id_with_multiple_dots():
    filename = "/some/dir/sample.name.with.dots.json"
    assert extract_sample_id(filename) == "sample.name.with.dots"


# Tests for load_json_file


def test_load_json_file_not_found(tmp_path):
    missing = tmp_path / "nofile.json"
    with pytest.raises(FileNotFoundError) as exc:
        load_json_file(str(missing))
    assert f"File {missing} not found" in str(exc.value)


def test_load_json_file_preserve_list(tmp_path):
    data = [{"key": "value1"}, {"key": "value2"}]
    file_path = tmp_path / "data.json"
    file_path.write_text(json.dumps(data))
    result = load_json_file(str(file_path), preserve_list=True)
    assert isinstance(result, list)
    assert result == data


def test_load_json_file_default_behavior_list(tmp_path):
    # default preserve_list=False should unwrap single-item list
    single = [{"only": "item"}]
    file_path = tmp_path / "single.json"
    file_path.write_text(json.dumps(single))
    result = load_json_file(str(file_path))
    assert isinstance(result, dict)
    assert result == single[0]


def test_load_json_file_default_behavior_multi_list(tmp_path):
    # For multi-item list, still unwrap only first
    multi = [{"a": 1}, {"b": 2}]
    file_path = tmp_path / "multi.json"
    file_path.write_text(json.dumps(multi))
    result = load_json_file(str(file_path))
    assert isinstance(result, dict)
    assert result == multi[0]


# Tests for HTML utils


def test_create_html_header_structure():
    id_name = "testid"
    section_name = "Test Section"
    description = "This is a test"
    header = create_html_header(id_name, section_name, description)
    # Should start with comment block and div
    assert header.startswith("<!--")
    assert f"id: '{id_name}'" in header
    assert f"section_name: '{section_name}'" in header
    assert f"description: '{description}'" in header
    assert "<div class='mqc-custom-content'>" in header


def test_create_html_footer():
    footer = create_html_footer()
    assert footer == "</div>"
