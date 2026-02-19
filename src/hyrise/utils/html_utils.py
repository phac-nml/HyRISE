# hyrise/utils/html_utils.py
"""
HTML generation utilities for HyRISE package
"""

import html
import json
import re


def _esc(value):
    """Escape arbitrary values for safe HTML text insertion."""
    return html.escape(str(value), quote=True)


def _safe_dom_id(value):
    """Normalize IDs used in HTML/JS contexts."""
    normalized = re.sub(r"[^A-Za-z0-9_\-:.]", "_", str(value))
    return normalized or "chart"


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
id: '{_esc(id_name)}'
section_name: '{_esc(section_name)}'
description: '{_esc(description)}'
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


def create_styled_table(headers, rows, table_class="table table-bordered table-hover"):
    """
    Create an HTML table with the specified headers and rows

    Args:
        headers (list): List of column header strings
        rows (list): List of row data (each row is a list of values)
        table_class (str): CSS classes for the table

    Returns:
        str: HTML table
    """
    html = f"<table class='{_esc(table_class)}'>\n"

    # Add header row
    html += "<thead><tr>\n"
    for header in headers:
        html += f"<th>{_esc(header)}</th>\n"
    html += "</tr></thead>\n"

    # Add data rows
    html += "<tbody>\n"
    for row in rows:
        html += "<tr>\n"
        for cell in row:
            html += f"<td>{_esc(cell)}</td>\n"
        html += "</tr>\n"
    html += "</tbody>\n"

    html += "</table>\n"
    return html


def create_bar_chart_css():
    """
    Create CSS styles for bar chart visualizations

    Returns:
        str: CSS styles as string
    """
    return """<style>
.bar-chart {
    margin: 20px 0;
}
.bar-container {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}
.bar-label {
    width: 150px;
    text-align: right;
    padding-right: 10px;
    font-weight: bold;
}
.bar-wrapper {
    flex-grow: 1;
}
.bar {
    height: 25px;
    background-color: #337ab7;
    display: flex;
    align-items: center;
}
.bar-value {
    color: white;
    padding-left: 5px;
    font-weight: bold;
}
</style>
"""


def create_bar(label, value, max_value, color="#337ab7"):
    """
    Create a single bar for a bar chart

    Args:
        label (str): Bar label
        value (float): Bar value
        max_value (float): Maximum value for scaling
        color (str): Bar color (hex or CSS color name)

    Returns:
        str: HTML for a single bar
    """
    width_percent = (value / max_value * 100) if max_value > 0 else 0

    html = "<div class='bar-container'>\n"
    html += f"  <div class='bar-label'>{_esc(label)}</div>\n"
    html += "  <div class='bar-wrapper'>\n"
    html += f"    <div class='bar' style='width: {width_percent}%; background-color: {_esc(color)};'>\n"
    html += f"      <div class='bar-value'>{_esc(value)}</div>\n"
    html += "    </div>\n"
    html += "  </div>\n"
    html += "</div>\n"

    return html


def create_pie_chart_js(chart_id, data, labels, colors, title=None):
    """
    Create a pie chart using JavaScript (for more interactive charts)

    Args:
        chart_id (str): Unique ID for the chart
        data (list): List of numeric values
        labels (list): List of labels corresponding to values
        colors (list): List of colors for each segment
        title (str, optional): Chart title

    Returns:
        str: HTML and JavaScript for a pie chart
    """
    if not data or len(data) != len(labels):
        return "<p>Invalid data for pie chart</p>"

    safe_chart_id = _safe_dom_id(chart_id)
    labels_js = json.dumps(labels).replace("</", "<\\/")
    data_js = json.dumps(data)
    colors_js = json.dumps(colors)
    title_js = json.dumps("" if title is None else str(title)).replace("</", "<\\/")

    # Create HTML structure
    html = f"""
    <div>
        <canvas id="{safe_chart_id}" width="400" height="300"></canvas>
    </div>
    <script>
    (function() {{
        // Create chart when the page loads
        window.addEventListener('load', function() {{
            var ctx = document.getElementById('{safe_chart_id}').getContext('2d');
            var chart = new Chart(ctx, {{
                type: 'pie',
                data: {{
                    labels: {labels_js},
                    datasets: [{{
                        data: {data_js},
                        backgroundColor: {colors_js},
                        borderColor: 'white',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    title: {{
                        display: {str(title is not None).lower()},
                        text: {title_js}
                    }},
                    legend: {{
                        display: true,
                        position: 'right'
                    }}
                }}
            }});
        }});
    }})();
    </script>
    """

    return html


def create_color_legend(color_map, title=None):
    """
    Create a color legend for visualizations

    Args:
        color_map (dict): Dictionary mapping labels to colors
        title (str, optional): Legend title

    Returns:
        str: HTML for a color legend
    """
    html = "<div class='color-legend' style='margin: 15px 0;'>\n"

    if title:
        html += f"<h5>{_esc(title)}</h5>\n"

    html += "<div style='display: flex; flex-wrap: wrap;'>\n"

    for label, color in color_map.items():
        html += f"""
        <div style="display: flex; align-items: center; margin-right: 20px; margin-bottom: 5px;">
            <div style="width: 15px; height: 15px; background-color: {_esc(color)}; margin-right: 5px;"></div>
            <span>{_esc(label)}</span>
        </div>
        """

    html += "</div>\n"
    html += "</div>\n"

    return html
