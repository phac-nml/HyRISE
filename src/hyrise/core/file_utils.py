# hyrise/core/file_utils.py
"""
File handling utilities for HyRISE package
"""
import os
import json


def extract_sample_id(filename):
    """
    Extract sample ID from filename

    Args:
        filename (str): Path to the JSON file

    Returns:
        str: The extracted sample ID
    """
    basename = os.path.basename(filename)
    if "_NGS_results.json" in basename:
        return basename.split("_NGS_results.json")[0]
    else:
        return basename.split(".json")[0]


def load_json_file(json_file, preserve_list=True):
    """
    Load and parse a JSON file

    Args:
        json_file (str): Path to the JSON file
        preserve_list (bool): If True, preserve list structure if the JSON is a list.
                            Default changed to True to handle multiple sequences.

    Returns:
        dict or list: The parsed JSON data
    """
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"File {json_file} not found")

    with open(json_file, "r") as f:
        data = json.load(f)

    # Handle list format (Sierra sometimes returns a list with multiple items)
    if not preserve_list and isinstance(data, list) and len(data) > 0:
        data = data[0]

    return data


# hyrise/utils/html_utils.py
"""
HTML generation utilities for HyRISE package
"""


def create_html_header(id_name, section_name, description):
    """
    Create HTML header comment block for MultiQC

    Args:
        id_name (str): The ID for the MultiQC section
        section_name (str): The display name for the section
        description (str): Description of the section

    Returns:
        str: HTML header comment block
    """
    return f"""<!--
id: '{id_name}'
section_name: '{section_name}'
description: '{description}'
-->
<div class='mqc-custom-content'>
"""


def create_html_footer():
    """
    Create HTML footer for MultiQC custom content

    Returns:
        str: HTML footer
    """
    return "</div>"
