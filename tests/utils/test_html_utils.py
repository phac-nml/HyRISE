import pytest
from hyrise.utils.html_utils import (
    create_html_header,
    create_html_footer,
    create_styled_table,
    create_bar_chart_css,
    create_bar,
    create_pie_chart_js,
    create_color_legend,
)


def test_create_styled_table_default_class():
    headers = ["Col1", "Col2"]
    rows = [[1, 2], [3, 4]]
    html = create_styled_table(headers, rows)
    # Check table tag with default class
    assert "<table class='table table-bordered table-hover'>" in html
    # Check header cells
    assert "<th>Col1</th>" in html
    assert "<th>Col2</th>" in html
    # Check row data
    assert "<td>1</td>" in html
    assert "<td>4</td>" in html
    # Check correct number of <tr> tags (1 header + 2 rows = 3)
    assert html.count("<tr>") == 3


def test_create_styled_table_custom_class():
    headers = ["H"]
    rows = [[10]]
    cls = "my-table"
    html = create_styled_table(headers, rows, table_class=cls)
    assert f"<table class='{cls}'>" in html


def test_create_bar_chart_css_contains_style_and_class():
    css = create_bar_chart_css()
    assert "<style>" in css
    assert ".bar-chart" in css
    assert ".bar-container" in css
    assert ".bar-value" in css
    assert "</style>" in css


def test_create_bar_correct_width_and_label():
    label = "Test"
    value = 25
    max_value = 100
    html = create_bar(label, value, max_value)
    # width 25% calculated
    assert "width: 25.0%;" in html
    # label and value present
    assert (
        "<div class='bar-label'>Test</div>" in html
        or '<div class="bar-label">Test</div>' in html
    )
    assert (
        "<div class='bar-value'>25</div>" in html
        or '<div class="bar-value">25</div>' in html
    )


def test_create_ba():
    html = create_bar("L", 10, 0)
    # width should be 0%
    assert "width: 0%;" in html


def test_create_pie_chart_js_invalid_data():
    # data/labels length mismatch
    html = create_pie_chart_js("c1", [1, 2], ["a"], ["red", "blue"])
    assert html.strip() == "<p>Invalid data for pie chart</p>"


def test_create_pie_chart_js_valid_no_title():
    data = [5, 10]
    labels = ["A", "B"]
    colors = ["red", "blue"]
    html = create_pie_chart_js("chart1", data, labels, colors)
    # Contains canvas id
    assert 'id="chart1"' in html
    # Contains labels and data arrays
    assert str(labels) in html
    assert str(data) in html
    # title display false
    assert "display: false" in html


def test_create_pie_chart_js_valid_with_title():
    html = create_pie_chart_js("c2", [1], ["X"], ["#fff"], title="MyChart")
    assert 'id="c2"' in html
    assert "MyChart" in html
    # title display true
    assert "display: true" in html


def test_create_color_legend_no_title():
    cmap = {"One": "#111", "Two": "#222"}
    html = create_color_legend(cmap)
    # Should contain class
    assert "<div class='color-legend'" in html or '<div class="color-legend"' in html
    # Should list both labels and colors
    for label, color in cmap.items():
        assert label in html
        assert color in html


def test_create_color_legend_with_title():
    cmap = {"A": "red"}
    html = create_color_legend(cmap, title="Legend")
    # Title present as h5
    assert "<h5>Legend</h5>" in html
