# hyrise/visualizers/resistance.py
"""
Resistance-related visualizations for HyRISE package
"""
import os
import json
from collections import defaultdict

from ..utils.html_utils import (
    create_html_header,
    create_html_footer,
    create_bar_chart_css,
    create_bar,
)


def create_resistance_table(data, sample_id, output_dir):
    """
    Create a single comprehensive table of drug resistance scores for each gene

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize data by gene
    gene_drug_data = defaultdict(dict)

    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            resistance_level = drug_score["text"]
            score = drug_score["score"]
            level = drug_score.get("level", 0)

            safe_drug_name = (
                drug_name.replace("/", "_").replace(" ", "_").replace("-", "_")
            )
            row_id = f"{sample_id}_{safe_drug_name}"
            gene_drug_data[gene_name][row_id] = {
                "Drug": drug_name,
                "Drug Class": drug_class,
                "Score": score,
                "Level": level,
                "Resistance Level": resistance_level,
            }

    # Create a single table for each gene
    for gene_name, drugs_data in gene_drug_data.items():
        if drugs_data:
            table_data = {
                "id": f"drug_resistance_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Drug Resistance Profile",
                "description": f"Comprehensive analysis of antiretroviral drug susceptibility and resistance patterns based on genetic mutations, with quantitative resistance scores and clinical interpretations for {gene_name} gene.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"drug_resistance_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Drug Resistance Profile",
                    "save_file": True,
                    "col1_header": "Sample ID",
                },
                "headers": {
                    "Drug": {"title": "Drug", "description": "Antiretroviral drug"},
                    "Drug Class": {
                        "title": "Class",
                        "description": "Drug class (e.g., NRTI, NNRTI, PI, INSTI)",
                    },
                    "Score": {
                        "title": "Score",
                        "description": "Drug resistance score",
                        "min": 0,
                        "max": 60,
                        "scale": "RdYlGn-rev",
                        "format": "{:.0f}",
                    },
                    "Level": {
                        "title": "Level",
                        "description": "Numeric resistance level (1-5)",
                        "hidden": True,  # Hidden by default but available for sorting
                    },
                    "Resistance Level": {
                        "title": "Interpretation",
                        "description": "Resistance interpretation",
                    },
                },
                "data": drugs_data,
            }

            # Write to file
            output_file = os.path.join(
                output_dir, f"drug_resistance_{gene_name.lower()}_table_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(table_data, f, indent=2)


def create_relevant_drug_commentary(data, sample_id, output_dir):
    """
    Create a focused HTML section with drug resistance commentary organized by mutation type

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    gene_comments = defaultdict(lambda: defaultdict(list))

    # Collect comments for all mutations and organize by type
    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            # Only include drugs with at least some resistance (score ≥ 5)
            if drug_score["score"] < 5:
                continue

            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")

            # Get partial score comments for contributions
            for partial in drug_score.get("partialScores", []):
                # Include all partial scores for completeness
                score = partial.get("score", 0)

                for mutation in partial.get("mutations", []):
                    mutation_type = mutation.get("primaryType", "Other")

                    if "comments" in mutation and mutation.get("comments"):
                        for comment in mutation.get("comments", []):
                            comment_text = comment.get("text", "")
                            mutation_text = mutation.get("text", "")
                            type_text = comment.get("type", "")

                            # Check if this is a new unique comment
                            is_new = True
                            for existing in gene_comments[gene_name][mutation_type]:
                                if (
                                    existing["Mutation"] == mutation_text
                                    and existing["Commentary"] == comment_text
                                ):
                                    is_new = False
                                    break

                            if (
                                is_new and comment_text
                            ):  # Only include if comment has text
                                gene_comments[gene_name][mutation_type].append(
                                    {
                                        "Drug": drug_name,
                                        "Drug Class": drug_class,
                                        "Mutation": mutation_text,
                                        "Commentary": comment_text,
                                        "Type": type_text,
                                        "Score Contribution": score,
                                    }
                                )

    # Create commentary for each gene
    for gene_name, type_comments in gene_comments.items():
        if any(comments for comments in type_comments.values()):
            # Create HTML content
            html_content = create_html_header(
                f"drug_commentary_{gene_name.lower()}",
                f"{gene_name} Resistance Mutation Clinical Implications",
                f"Interactive analysis of {gene_name} mutations and their clinical significance for HIV drug resistance, organized by mutation type. Each mutation's impact on drug efficacy is presented with detailed commentary from the HIV drug resistance database.",
            )

            html_content += f"<h3>Clinical Significance of {gene_name} Mutations</h3>\n"

            # Add tabbed interface for different mutation types
            html_content += """
            <style>
                .hyrise-tabs {
                    display: flex;
                    flex-wrap: wrap;
                    border-bottom: 1px solid #ddd;
                    margin-bottom: 15px;
                }
                .hyrise-tab {
                    padding: 8px 15px;
                    cursor: pointer;
                    background-color: #f8f9fa;
                    border: 1px solid #ddd;
                    border-bottom: none;
                    margin-right: 5px;
                    border-radius: 5px 5px 0 0;
                }
                .hyrise-tab.active {
                    background-color: #fff;
                    border-bottom: 1px solid #fff;
                    margin-bottom: -1px;
                    font-weight: bold;
                }
                .hyrise-tab-content {
                    display: none;
                    padding: 15px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 5px 5px;
                }
                .hyrise-tab-content.active {
                    display: block;
                }
            </style>
            <div class="hyrise-tabs">
            """

            # Create tabs for each mutation type plus an "All" tab
            mutation_types = sorted(type_comments.keys())
            html_content += f"<div class=\"hyrise-tab active\" onclick=\"showTab('{gene_name}', 'All')\">All</div>\n"

            for i, mutation_type in enumerate(mutation_types):
                if type_comments[mutation_type]:  # Only show tab if there are comments
                    active = (
                        "active" if i == -1 else ""
                    )  # -1 means never active (All tab is active)
                    html_content += f"<div class=\"hyrise-tab {active}\" onclick=\"showTab('{gene_name}', '{mutation_type}')\">{mutation_type}</div>\n"

            html_content += "</div>\n"

            # Create content for "All" tab
            html_content += f'<div id="{gene_name}-All-content" class="hyrise-tab-content active">\n'
            all_comments = []
            for mutation_type in mutation_types:
                all_comments.extend(type_comments[mutation_type])

            if not all_comments:
                html_content += "<p>No significant clinical implications were found for the mutations in this sample.</p>\n"
            else:
                html_content += "<table class='table table-bordered table-hover table-responsive'>\n"
                html_content += "<thead><tr><th>Type</th><th>Mutation</th><th>Drug</th><th>Clinical Implication</th></tr></thead>\n"
                html_content += "<tbody>\n"

                for comment in sorted(
                    all_comments, key=lambda x: (x["Type"], x["Mutation"])
                ):
                    html_content += f"<tr><td>{comment['Type']}</td><td>{comment['Mutation']}</td><td>{comment['Drug']} ({comment['Drug Class']})</td><td>{comment['Commentary']}</td></tr>\n"

                html_content += "</tbody></table>\n"

            html_content += "</div>\n"

            # Create content for each mutation type
            for mutation_type in mutation_types:
                if type_comments[
                    mutation_type
                ]:  # Only create content if there are comments
                    html_content += f'<div id="{gene_name}-{mutation_type}-content" class="hyrise-tab-content">\n'

                    html_content += (
                        f"<h4>{mutation_type} Mutations Clinical Significance</h4>\n"
                    )
                    html_content += "<table class='table table-bordered table-hover table-responsive'>\n"
                    html_content += "<thead><tr><th>Mutation</th><th>Drug</th><th>Score Contribution</th><th>Clinical Implication</th></tr></thead>\n"
                    html_content += "<tbody>\n"

                    for comment in sorted(
                        type_comments[mutation_type],
                        key=lambda x: (x["Mutation"], x["Drug"]),
                    ):
                        html_content += f"<tr><td>{comment['Mutation']}</td><td>{comment['Drug']} ({comment['Drug Class']})</td><td>{comment['Score Contribution']}</td><td>{comment['Commentary']}</td></tr>\n"

                    html_content += "</tbody></table>\n"
                    html_content += "</div>\n"

            # Add JavaScript for tab functionality
            html_content += """
            <script>
            function showTab(gene, tabName) {
                // Hide all tabs
                var tabContents = document.getElementsByClassName('hyrise-tab-content');
                for (var i = 0; i < tabContents.length; i++) {
                    tabContents[i].className = tabContents[i].className.replace(' active', '');
                }                
                // Show selected tab
                var activeTab = document.getElementById(gene + '-' + tabName + '-content');
                if (activeTab) {
                    activeTab.className += ' active';
                }
                // Update tab styling
                var tabs = document.getElementsByClassName('hyrise-tab');
                for (var i = 0; i < tabs.length; i++) {
                    tabs[i].className = tabs[i].className.replace(' active', '');
                    if (tabs[i].innerText === tabName) {
                        tabs[i].className += ' active';
                    }
                }
            }
            </script>
            """

            html_content += create_html_footer()

            # Write to file
            output_file = os.path.join(
                output_dir, f"drug_commentary_{gene_name.lower()}_mqc.html"
            )
            with open(output_file, "w") as f:
                f.write(html_content)


def create_resistance_level_distribution(data, sample_id, output_dir):
    """
    Create a summary of resistance levels across drugs using MultiQC's native plot types

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    import os
    import json
    from collections import defaultdict

    # Define resistance levels for consistent ordering
    level_order = {
        "Susceptible": 1,
        "Potential Low-Level": 2,
        "Low-Level": 3,
        "Intermediate": 4,
        "High-Level": 5,
    }

    level_map = {
        1: "Susceptible",
        2: "Potential Low-Level",
        3: "Low-Level",
        4: "Intermediate",
        5: "High-Level",
    }

    # Color palette for resistance levels
    color_map = {
        "Susceptible": "#777777",  # Gray
        "Potential Low-Level": "#5bc0de",  # Light blue
        "Low-Level": "#5cb85c",  # Green
        "Intermediate": "#f0ad4e",  # Orange
        "High-Level": "#d9534f",  # Red
    }

    # Organize data by gene
    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        # Data structures for different visualizations
        heatmap_data = defaultdict(lambda: defaultdict(int))
        table_data = {}
        bar_data = defaultdict(int)
        drug_class_counts = defaultdict(int)

        # Process drug scores
        for drug_score in dr_entry.get("drugScores", []):
            level_num = drug_score.get("level", 0)
            level_text = level_map.get(level_num, f"Level {level_num}")
            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")

            # Update heatmap data (drug class vs resistance level)
            heatmap_data[drug_class][level_text] += 1

            # Update bar chart data (overall resistance level counts)
            bar_data[level_text] += 1

            # Update drug class counter
            drug_class_counts[drug_class] += 1

            # Update table data
            row_id = f"{sample_id}_{drug_name}"
            table_data[row_id] = {
                "Drug": drug_name,
                "Class": drug_class,
                "Resistance Level": level_text,
                "Score": drug_score.get("score", 0),
            }

        # Skip if no data was found for this gene
        if not table_data:
            continue

        # 1. Create a heatmap visualization (drug classes vs resistance levels)
        # Prepare data in the format MultiQC expects for heatmap
        heatmap_plot = {
            "id": f"resistance_heatmap_{gene_name.lower()}",
            "section_name": f"{gene_name} Resistance Heatmap",
            "description": f"Heatmap showing distribution of resistance levels across drug classes for {gene_name}",
            "pconfig": {
                "id": f"resistance_heatmap_{gene_name.lower()}",
                "title": f"{gene_name} Resistance by Class and Level",
                "xlab": "Resistance Level",
                "ylab": "Drug Class",
            },
            "plot_type": "heatmap",
            "data": {},
        }

        # Convert hierarchical data to the flat structure needed for heatmap
        for drug_class in sorted(heatmap_data.keys()):
            heatmap_plot["data"][drug_class] = {}
            for level_text in sorted(level_order.keys(), key=lambda x: level_order[x]):
                count = heatmap_data[drug_class].get(level_text, 0)
                heatmap_plot["data"][drug_class][level_text] = count

        # Write heatmap data to file
        # with open(os.path.join(output_dir, f"resistance_heatmap_{gene_name.lower()}_mqc.json"), 'w') as f:
        #     json.dump(heatmap_plot, f, indent=2)

        # 2. Create a bar graph for overall resistance level distribution
        # MultiQC bargraph expects a simpler data structure
        bar_plot = {
            "id": f"resistance_bargraph_{gene_name.lower()}",
            "section_name": f"{gene_name} Resistance Distribution",
            "description": f"Distribution of resistance levels across all drugs for {gene_name}",
            "pconfig": {
                "id": f"resistance_bargraph_{gene_name.lower()}",
                "title": f"{gene_name} Overall Resistance Distribution",
                "ylab": "Number of Drugs",
                "cpswitch": False,
                "tt_percentages": False,
                "ymin": 0,
            },
            "data": {"All Drugs": {}},
            "plot_type": "bargraph",
        }

        # Populate data in the format MultiQC expects
        for level_text in sorted(level_order.keys(), key=lambda x: level_order[x]):
            bar_plot["data"]["All Drugs"][level_text] = bar_data.get(level_text, 0)

        # Write bar graph data to file
        # with open(os.path.join(output_dir, f"resistance_bargraph_{gene_name.lower()}_mqc.json"), 'w') as f:
        #     json.dump(bar_plot, f, indent=2)

        # 3. Create a table view with all drug resistance data
        table_plot = {
            "id": f"resistance_table_{gene_name.lower()}",
            "section_name": f"{gene_name} Resistance Table",
            "description": f"Detailed table of resistance levels for all drugs in {gene_name}",
            "pconfig": {
                "id": f"resistance_table_{gene_name.lower()}",
                "title": f"{gene_name} Drug Resistance Levels",
                "col1_header": "Drug",
                "sortRows": True,
            },
            "headers": {
                "Drug": {"title": "Drug", "description": "Drug name", "scale": False},
                "Class": {
                    "title": "Drug Class",
                    "description": "Class of antiretroviral drug",
                    "scale": False,
                },
                "Resistance Level": {
                    "title": "Resistance Level",
                    "description": "Interpreted resistance level",
                    "scale": False,
                    "hidden": False,
                },
                "Score": {
                    "title": "Score",
                    "description": "Resistance score",
                    "scale": "RdYlGn-rev",
                    "min": 0,
                    "max": 100,
                },
            },
            "data": table_data,
            "plot_type": "table",
        }

        # Write table data to file
        # with open(os.path.join(output_dir, f"resistance_table_{gene_name.lower()}_mqc.json"), 'w') as f:
        #     json.dump(table_plot, f, indent=2)

        # 4. Create a summary pie chart visualization
        # MultiQC piechart expects a simple dictionary of labels to values
        pie_data = {}
        for level_text, count in bar_data.items():
            # Use actual count rather than percentage for pie chart
            # MultiQC will handle the percentage calculation
            pie_data[f"{level_text} ({count})"] = count

        pie_plot = {
            "id": f"resistance_piechart_{gene_name.lower()}",
            "section_name": f"{gene_name} Resistance Summary",
            "description": f"Summary of resistance level distribution for {gene_name}",
            "pconfig": {
                "id": f"resistance_piechart_{gene_name.lower()}",
                "title": f"{gene_name} Resistance Level Distribution",
            },
            "data": pie_data,
            "plot_type": "pie",
        }

        # Write pie chart data to file
        # with open(os.path.join(output_dir, f"resistance_piechart_{gene_name.lower()}_mqc.json"), 'w') as f:
        #     json.dump(pie_plot, f, indent=2)


def create_partial_score_analysis(data, sample_id, output_dir):
    """
    Create an interactive visualization of how mutations contribute to resistance scores

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize data by gene
    gene_mutation_contribution = defaultdict(lambda: defaultdict(dict))

    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            # Only include drugs with significant resistance (score ≥ 15)
            if drug_score["score"] < 15:
                continue

            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            total_score = drug_score["score"]

            # Process all partial scores for this drug
            for partial in drug_score.get("partialScores", []):
                score = partial.get("score", 0)

                # Only include significant partial scores (≥ 5 points)
                if score < 5:
                    continue

                # Get all mutations in this partial score
                mutation_texts = []
                mutation_types = []

                for mutation in partial.get("mutations", []):
                    mutation_texts.append(mutation.get("text", ""))
                    mutation_types.append(mutation.get("primaryType", "Other"))

                if mutation_texts:
                    # Create mutation key and determine primary type
                    mutation_key = " + ".join(mutation_texts)

                    # Determine the primary type for this combination
                    primary_type = "Other"
                    if "Major" in mutation_types:
                        primary_type = "Major"
                    elif "Accessory" in mutation_types:
                        primary_type = "Accessory"

                    # Calculate contribution percentage
                    contribution = (score / total_score * 100) if total_score > 0 else 0

                    # Create a unique row ID without sample_id
                    # Use a combination of drug name and mutation to ensure uniqueness
                    safe_drug_name = (
                        drug_name.replace("/", "_").replace(" ", "_").replace("-", "_")
                    )
                    safe_mutation_name = (
                        mutation_key.replace(" ", "_")
                        .replace("/", "_")
                        .replace("-", "_")
                    )
                    row_id = f"{sample_id}_{safe_drug_name}_{safe_mutation_name}"

                    # Store the data
                    gene_mutation_contribution[gene_name][row_id] = {
                        "Drug": drug_name,
                        "Drug Class": drug_class,
                        "Mutations": mutation_key,
                        "Mutation Type": primary_type,
                        "Score": score,
                        "Total Score": total_score,
                        "Contribution (%)": round(contribution, 1),
                    }

    # Create a table for each gene
    for gene_name, contribution_data in gene_mutation_contribution.items():
        if contribution_data:
            table_data = {
                "id": f"mutation_contribution_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Mutation-Specific Resistance Contribution",
                "description": f"Detailed breakdown of how individual genetic mutations and mutation patterns contribute to overall drug resistance scores in {gene_name}, highlighting the relative impact of specific mutations on drug efficacy.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"mutation_contribution_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Mutation Contribution to Resistance",
                    "save_file": True,
                    "col1_header": "Sample ID",
                },
                "headers": {
                    "Drug": {"title": "Drug", "description": "Antiretroviral drug"},
                    "Drug Class": {
                        "title": "Class",
                        "description": "Drug class category",
                    },
                    "Mutations": {
                        "title": "Mutations",
                        "description": "Mutation pattern",
                    },
                    "Mutation Type": {
                        "title": "Type",
                        "description": "Primary mutation type",
                    },
                    "Score": {
                        "title": "Contribution",
                        "description": "Points contributed to resistance score",
                        "scale": "RdYlGn-rev",
                        "min": 0,
                        "max": 60,
                        "format": "{:.0f}",
                    },
                    "Total Score": {
                        "title": "Total Score",
                        "description": "Total resistance score for the drug",
                    },
                    "Contribution (%)": {
                        "title": "% of Total",
                        "description": "Percentage contribution to total resistance",
                        "scale": "RdYlGn-rev",
                        "min": 0,
                        "max": 100,
                        "format": "{:.1f}%",
                    },
                },
                "data": contribution_data,
            }

            # Write to file
            output_file = os.path.join(
                output_dir, f"mutation_contribution_{gene_name.lower()}_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(table_data, f, indent=2)


def create_drug_class_overview(data, sample_id, output_dir):
    """
    Create a high-level overview of drug resistance by drug class

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize by gene and drug class
    gene_class_overview = defaultdict(
        lambda: defaultdict(
            lambda: {
                "total_drugs": 0,
                "resistant_drugs": 0,
                "high_resistance": 0,
                "intermediate": 0,
                "low_resistance": 0,
                "potential_low": 0,
                "susceptible": 0,
                "max_score": 0,
                "drugs": [],
            }
        )
    )

    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            score = drug_score["score"]
            level = drug_score.get("level", 0)

            # Update counts
            overview = gene_class_overview[gene_name][drug_class]
            overview["total_drugs"] += 1
            overview["drugs"].append(
                {"name": drug_name, "score": score, "level": level}
            )

            # Update max score if this is higher
            if score > overview["max_score"]:
                overview["max_score"] = score

            # Count by resistance level
            if level == 5:  # High-Level
                overview["high_resistance"] += 1
                overview["resistant_drugs"] += 1
            elif level == 4:  # Intermediate
                overview["intermediate"] += 1
                overview["resistant_drugs"] += 1
            elif level == 3:  # Low-Level
                overview["low_resistance"] += 1
                overview["resistant_drugs"] += 1
            elif level == 2:  # Potential Low-Level
                overview["potential_low"] += 1
            elif level == 1:  # Susceptible
                overview["susceptible"] += 1

    # Create visualization for each gene
    for gene_name, class_overview in gene_class_overview.items():
        if class_overview:
            # Create HTML content
            html_content = create_html_header(
                f"drug_class_overview_{gene_name.lower()}",
                f"{gene_name} Drug Class Overview",
                f"High-level overview of drug resistance by drug class for {gene_name}.",
            )

            html_content += f"<h3>{gene_name} Resistance by Drug Class</h3>\n"

            # Add CSS for visualization
            html_content += """
            <style>
            .overview-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            .overview-table th, .overview-table td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            .overview-table th { background-color: #f2f2f2; }
            .overview-pills { margin-top: 10px; }
            .pill { display: inline-block; padding: 3px 8px; border-radius: 10px; margin-right: 5px; font-size: 13px; }
            .pill.high { background-color: #d9534f; color: white; }
            .pill.int { background-color: #f0ad4e; color: white; }
            .pill.low { background-color: #5cb85c; color: white; }
            .pill.pot { background-color: #5bc0de; color: white; }
            .pill.sus { background-color: #777777; color: white; }
            .resistance-meter { height: 30px; background-color: #f5f5f5; border-radius: 15px; overflow: hidden; margin: 10px 0; }
            .meter-segment { height: 100%; float: left; color: white; text-align: center; line-height: 30px; font-weight: bold; }
            .overall-status { padding: 15px; margin: 15px 0; border-radius: 5px; font-weight: bold; text-align: center; }
            .status-high { background-color: #f2dede; color: #a94442; border: 1px solid #ebccd1; }
            .status-int { background-color: #fcf8e3; color: #8a6d3b; border: 1px solid #faebcc; }
            .status-low { background-color: #dff0d8; color: #3c763d; border: 1px solid #d6e9c6; }
            .status-sus { background-color: #d9edf7; color: #31708f; border: 1px solid #bce8f1; }
            </style>
            """

            # Create overall status message
            total_drugs = sum(cls["total_drugs"] for cls in class_overview.values())
            total_resistant = sum(
                cls["resistant_drugs"] for cls in class_overview.values()
            )
            resistant_percent = (
                (total_resistant / total_drugs * 100) if total_drugs > 0 else 0
            )

            status_class = "status-sus"
            status_message = "No significant drug resistance detected"

            if resistant_percent >= 50:
                status_class = "status-high"
                status_message = "High level of drug resistance detected across multiple drug classes"
            elif resistant_percent >= 25:
                status_class = "status-int"
                status_message = "Moderate drug resistance detected"
            elif resistant_percent > 0:
                status_class = "status-low"
                status_message = "Low-level drug resistance detected"

            html_content += (
                f"<div class='overall-status {status_class}'>{status_message}</div>\n"
            )

            # Create overview table
            html_content += "<table class='overview-table'>\n"
            html_content += "<tr><th>Drug Class</th><th>Total Drugs</th><th>Resistant Drugs</th><th>Max Score</th><th>Resistance Profile</th></tr>\n"

            for drug_class, overview in sorted(class_overview.items()):
                resistant_percent = (
                    (overview["resistant_drugs"] / overview["total_drugs"] * 100)
                    if overview["total_drugs"] > 0
                    else 0
                )

                html_content += f"<tr>\n"
                html_content += f"  <td>{drug_class}</td>\n"
                html_content += f"  <td>{overview['total_drugs']}</td>\n"
                html_content += f"  <td>{overview['resistant_drugs']} ({resistant_percent:.1f}%)</td>\n"
                html_content += f"  <td>{overview['max_score']}</td>\n"
                html_content += "  <td>\n"

                # Create resistance meter
                html_content += "    <div class='resistance-meter'>\n"

                # Calculate percentages for each level
                total = overview["total_drugs"]
                if total > 0:
                    high_percent = overview["high_resistance"] / total * 100
                    int_percent = overview["intermediate"] / total * 100
                    low_percent = overview["low_resistance"] / total * 100
                    pot_percent = overview["potential_low"] / total * 100
                    sus_percent = overview["susceptible"] / total * 100

                    # Add segments if they have width
                    if high_percent > 0:
                        html_content += f"      <div class='meter-segment pill high' style='width: {high_percent}%;'>{overview['high_resistance']}</div>\n"
                    if int_percent > 0:
                        html_content += f"      <div class='meter-segment pill int' style='width: {int_percent}%;'>{overview['intermediate']}</div>\n"
                    if low_percent > 0:
                        html_content += f"      <div class='meter-segment pill low' style='width: {low_percent}%;'>{overview['low_resistance']}</div>\n"
                    if pot_percent > 0:
                        html_content += f"      <div class='meter-segment pill pot' style='width: {pot_percent}%;'>{overview['potential_low']}</div>\n"
                    if sus_percent > 0:
                        html_content += f"      <div class='meter-segment pill sus' style='width: {sus_percent}%;'>{overview['susceptible']}</div>\n"

                html_content += "    </div>\n"

                # Add resistance pills
                html_content += "    <div class='overview-pills'>\n"
                if overview["high_resistance"] > 0:
                    html_content += f"      <span class='pill high'>High: {overview['high_resistance']}</span>\n"
                if overview["intermediate"] > 0:
                    html_content += f"      <span class='pill int'>Int: {overview['intermediate']}</span>\n"
                if overview["low_resistance"] > 0:
                    html_content += f"      <span class='pill low'>Low: {overview['low_resistance']}</span>\n"
                if overview["potential_low"] > 0:
                    html_content += f"      <span class='pill pot'>Pot: {overview['potential_low']}</span>\n"
                if overview["susceptible"] > 0:
                    html_content += f"      <span class='pill sus'>Sus: {overview['susceptible']}</span>\n"
                html_content += "    </div>\n"

                html_content += "  </td>\n"
                html_content += "</tr>\n"

            html_content += "</table>\n"

            html_content += create_html_footer()

            # Write to file
            output_file = os.path.join(
                output_dir, f"drug_class_overview_{gene_name.lower()}_mqc.html"
            )
            with open(output_file, "w") as f:
                f.write(html_content)
