# hyrise/visualizers/mutations.py
"""
Mutation-related visualizations for HyRISE package
"""
import os
import json
from collections import defaultdict

from ..utils.html_utils import create_html_header, create_html_footer


def create_mutation_table(data, sample_id, output_dir):
    """
    Create a consolidated table of mutations organized by gene

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize mutations by gene
    gene_mutations = defaultdict(dict)

    for gene_seq in data.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]

        # Get SDRMs (Surveillance Drug Resistance Mutations)
        sdrm_list = [m["text"] for m in gene_seq.get("SDRMs", [])]

        # Process all mutations
        for mutation in gene_seq.get("mutations", []):
            mutation_text = mutation.get("text", "")
            mutation_type = mutation.get("primaryType", "Unknown")
            position = mutation.get("position", "")
            is_sdrm = mutation_text in sdrm_list
            is_apobec = mutation.get("isApobecMutation", False)
            is_unusual = mutation.get("isUnusual", False)

            # Create unique row ID
            row_id = f"{sample_id}_{mutation_text}"

            # Store mutation data
            gene_mutations[gene_name][row_id] = {
                "Mutation": mutation_text,
                "Type": mutation_type,
                "Position": position,
                "Is SDRM": "Yes" if is_sdrm else "No",
                "Is APOBEC": "Yes" if is_apobec else "No",
                "Is Unusual": "Yes" if is_unusual else "No",
            }

    # Create consolidated table for each gene
    for gene_name, mutations in gene_mutations.items():
        if mutations:
            table_output = {
                "id": f"significant_mutations_{gene_name.lower()}",
                "section_name": f"{gene_name} Mutations",
                "description": f"All detected mutations in the {gene_name} gene.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"mutations_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Mutations",
                    "save_file": True,
                    "col1_header": "Mutation",
                    # Enable table filtering capabilities
                    "filters": True,
                    # Enable row highlighting based on mutation type
                    "conditional_formatting": True,
                    "conditional_formatting_rules": [
                        {"field": "Type", "equals": "Major", "bg_color": "#ffdddd"},
                        {"field": "Type", "equals": "Accessory", "bg_color": "#ffffcc"},
                    ],
                },
                "headers": {
                    "Mutation": {"title": "Mutation", "description": "Mutation code"},
                    "Type": {
                        "title": "Type",
                        "description": "Mutation type (Major, Accessory, or Other)",
                        "filterable": True,
                    },
                    "Position": {
                        "title": "Position",
                        "description": "Position in gene sequence",
                    },
                    "Is SDRM": {
                        "title": "SDRM",
                        "description": "Surveillance Drug Resistance Mutation",
                        "filterable": True,
                    },
                    "Is APOBEC": {
                        "title": "APOBEC",
                        "description": "APOBEC-mediated G-to-A hypermutation",
                        "filterable": True,
                    },
                    "Is Unusual": {
                        "title": "Unusual",
                        "description": "Mutation that is rarely observed in untreated patients",
                        "filterable": True,
                    },
                },
                "data": mutations,
            }

            # Write the consolidated table to file
            output_file = os.path.join(
                output_dir, f"significant_mutations_{gene_name.lower()}_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(table_output, f, indent=2)


def create_mutation_position_map(data, sample_id, output_dir):
    """
    Create an enhanced visualization of mutation positions along the gene sequence
    with integrated mutation type summary information

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """

    # Create a more comprehensive structure to store mutation details by position and type
    gene_mutations = defaultdict(
        lambda: {
            "positions": [],
            "major_positions": [],
            "accessory_positions": [],
            "other_positions": [],
            "sdrm_positions": [],
            "apobec_positions": [],
            "first_aa": 1,
            "last_aa": 300,
            "mutation_details": defaultdict(list),
            # Lists to store actual mutation texts by type
            "major_mutations": [],
            "accessory_mutations": [],
            "other_mutations": [],
            "sdrm_mutations": [],
            "apobec_mutations": [],
            # Add counters for mutation types
            "type_counts": defaultdict(int),
        }
    )

    for gene_seq in data.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]
        first_aa = gene_seq.get("firstAA", 1)
        last_aa = gene_seq.get("lastAA", 300)

        gene_mutations[gene_name]["first_aa"] = first_aa
        gene_mutations[gene_name]["last_aa"] = last_aa

        # Get SDRMs
        sdrm_texts = [sdrm.get("text", "") for sdrm in gene_seq.get("SDRMs", [])]

        for mutation in gene_seq.get("mutations", []):
            position = mutation.get("position")
            if position:
                mutation_text = mutation.get("text", "")
                mutation_type = mutation.get("primaryType", "Other")
                is_apobec = mutation.get("isApobecMutation", False)
                is_sdrm = mutation_text in sdrm_texts

                # Store the position in the appropriate lists
                gene_mutations[gene_name]["positions"].append(position)

                # Increment type counter
                gene_mutations[gene_name]["type_counts"][mutation_type] += 1

                # Store mutation texts by type
                if mutation_type == "Major":
                    gene_mutations[gene_name]["major_positions"].append(position)
                    gene_mutations[gene_name]["major_mutations"].append(mutation_text)
                elif mutation_type == "Accessory":
                    gene_mutations[gene_name]["accessory_positions"].append(position)
                    gene_mutations[gene_name]["accessory_mutations"].append(
                        mutation_text
                    )
                else:
                    gene_mutations[gene_name]["other_positions"].append(position)
                    gene_mutations[gene_name]["other_mutations"].append(mutation_text)

                if is_sdrm:
                    gene_mutations[gene_name]["sdrm_positions"].append(position)
                    gene_mutations[gene_name]["sdrm_mutations"].append(mutation_text)

                if is_apobec:
                    gene_mutations[gene_name]["apobec_positions"].append(position)
                    gene_mutations[gene_name]["apobec_mutations"].append(mutation_text)

                # Store detailed mutation information for the tooltip
                gene_mutations[gene_name]["mutation_details"][position].append(
                    {
                        "text": mutation_text,
                        "type": mutation_type,
                        "is_sdrm": is_sdrm,
                        "is_apobec": is_apobec,
                    }
                )

    # Create enhanced visualization for each gene
    for gene_name, mutation_data in gene_mutations.items():
        if mutation_data["positions"]:
            # Create HTML visualization
            html_content = create_html_header(
                f"mutation_position_map_{gene_name.lower()}",
                f"{gene_name} Mutation Position Map",
                f"Map of mutation positions along the {gene_name} gene sequence with detailed mutation information.",
            )

            html_content += f"<h3>{gene_name} Mutation Position Map</h3>\n"

            # Brief introduction
            total_mutations = len(mutation_data["positions"])
            html_content += f"<p>This visualization shows {total_mutations} mutations detected in the {gene_name} gene (positions {mutation_data['first_aa']}-{mutation_data['last_aa']}). Hover over colored positions for details.</p>\n"

            # Create a more informative position map with detailed tooltips
            html_content += "<style>\n"
            # Position map styling - using MultiQC-compatible styling
            html_content += ".position-map { display: flex; flex-wrap: wrap; margin: 20px 0; background-color: #f8f9fa; padding: 15px; border-radius: 5px; }\n"
            html_content += ".position-cell { width: 22px; height: 22px; margin: 1px; text-align: center; font-size: 10px; line-height: 22px; background-color: #eee; position: relative; }\n"
            html_content += (
                ".position-major { background-color: #d9534f; color: white; }\n"
            )
            html_content += (
                ".position-accessory { background-color: #f0ad4e; color: white; }\n"
            )
            html_content += (
                ".position-other { background-color: #5bc0de; color: white; }\n"
            )
            html_content += ".position-sdrm { border: 2px solid #5cb85c; }\n"
            html_content += ".position-apobec { border: 2px dashed #337ab7; }\n"

            # Tooltip styling - made more MultiQC-like
            html_content += ".position-tooltip { display: none; position: absolute; background-color: #333; color: white; padding: 8px; border-radius: 4px; font-size: 12px; z-index: 100; min-width: 200px; max-width: 250px; top: -5px; left: 100%; transform: translateY(-50%); text-align: left; box-shadow: 0 2px 4px rgba(0,0,0,.2); }\n"
            html_content += (
                ".position-cell:hover .position-tooltip { display: block; }\n"
            )
            html_content += ".position-tooltip ul { margin: 0; padding-left: 15px; }\n"
            html_content += ".position-tooltip li { margin: 3px 0; }\n"

            # Legend and summary styling
            html_content += ".position-legend { margin: 20px 0; background-color: #f8f9fa; padding: 15px; border-radius: 5px; display: flex; flex-wrap: wrap; }\n"
            html_content += ".legend-item { margin-right: 20px; margin-bottom: 10px; display: flex; align-items: center; }\n"
            html_content += (
                ".legend-box { width: 15px; height: 15px; margin-right: 5px; }\n"
            )

            # Mutation list styling
            html_content += ".mutation-details { margin-top: 30px; }\n"
            html_content += ".mqc-section { margin-bottom: 30px; }\n"
            html_content += ".mqc-table { width: 100%; margin-bottom: 20px; }\n"
            html_content += ".table-secondary { background-color: #f2f2f2; }\n"
            html_content += ".mutation-chunk { background-color: #f8f9fa; border-radius: 5px; padding: 8px; margin: 5px 0; }\n"
            html_content += "details summary { cursor: pointer; color: #337ab7; margin-bottom: 8px; }\n"
            html_content += "details summary:hover { text-decoration: underline; }\n"
            html_content += "</style>\n"

            # Position map is at the top of the content
            first_pos = mutation_data["first_aa"]
            last_pos = mutation_data["last_aa"]

            html_content += "<div class='position-map'>\n"
            for pos in range(first_pos, last_pos + 1):
                cell_class = "position-cell"

                # Determine cell class based on mutation type
                if pos in mutation_data["major_positions"]:
                    cell_class += " position-major"
                elif pos in mutation_data["accessory_positions"]:
                    cell_class += " position-accessory"
                elif pos in mutation_data["other_positions"]:
                    cell_class += " position-other"

                # Add SDRM and APOBEC indicators
                if pos in mutation_data["sdrm_positions"]:
                    cell_class += " position-sdrm"

                if pos in mutation_data["apobec_positions"]:
                    cell_class += " position-apobec"

                # Only show position number for positions divisible by 10 or positions with mutations
                display_pos = (
                    str(pos)
                    if pos % 10 == 0 or pos in mutation_data["positions"]
                    else "&nbsp;"
                )

                # Create the tooltip content with detailed mutation information
                tooltip_html = (
                    f"<span class='position-tooltip'><strong>Position {pos}</strong>"
                )

                # Add mutation details if this position has mutations
                if pos in mutation_data["mutation_details"]:
                    tooltip_html += "<ul>"
                    for mutation in mutation_data["mutation_details"][pos]:
                        mutation_text = mutation["text"]
                        mutation_type = mutation["type"]
                        tags = []

                        if mutation["is_sdrm"]:
                            tags.append("SDRM")
                        if mutation["is_apobec"]:
                            tags.append("APOBEC")

                        tag_text = f" ({', '.join(tags)})" if tags else ""
                        tooltip_html += f"<li><strong>{mutation_text}</strong> - {mutation_type}{tag_text}</li>"
                    tooltip_html += "</ul>"

                tooltip_html += "</span>"

                html_content += f"<div class='{cell_class}' title='Position {pos}'>{display_pos}{tooltip_html}</div>\n"

            html_content += "</div>\n"

            # Add enhanced legend with better descriptions
            html_content += "<div class='position-legend'>\n"
            html_content += "  <div class='legend-item'><div class='legend-box position-major'></div> Major Mutation (Directly confers resistance)</div>\n"
            html_content += "  <div class='legend-item'><div class='legend-box position-accessory'></div> Accessory Mutation (Enhances resistance)</div>\n"
            html_content += "  <div class='legend-item'><div class='legend-box position-other'></div> Other Mutation (Polymorphism or unknown effect)</div>\n"
            html_content += "  <div class='legend-item'><div class='legend-box position-sdrm' style='background-color: white;'></div> Surveillance Drug Resistance Mutation (SDRM)</div>\n"
            html_content += "  <div class='legend-item'><div class='legend-box position-apobec' style='background-color: white;'></div> APOBEC-mediated mutation</div>\n"
            html_content += "</div>\n"

            # Add the mutation lists organized by type in a MultiQC-style format
            html_content += "<div class='mqc-section mutation-details'>\n"
            html_content += "<h4>Mutation Lists by Type</h4>\n"

            # Create a table with mutation type counts and percentages
            html_content += (
                "<table class='table table-bordered table-hover mqc-table'>\n"
            )
            html_content += "<thead>\n"
            html_content += "<tr>\n"
            html_content += "<th>Mutation Type</th>\n"
            html_content += "<th>Count</th>\n"
            html_content += "<th>Percentage</th>\n"
            html_content += "<th>Mutations</th>\n"
            html_content += "</tr>\n"
            html_content += "</thead>\n"
            html_content += "<tbody>\n"

            # Sort mutation types in a logical order
            type_order = ["Major", "Accessory"]
            sorted_types = sorted(
                mutation_data["type_counts"].items(),
                key=lambda x: (
                    type_order.index(x[0]) if x[0] in type_order else 999,
                    -x[1],
                ),
            )

            total_mutations = len(mutation_data["positions"])

            # Process Major mutations
            major_count = len(set(mutation_data["major_mutations"]))
            if major_count > 0:
                percentage = (
                    (major_count / total_mutations * 100) if total_mutations > 0 else 0
                )
                major_list = ", ".join(sorted(set(mutation_data["major_mutations"])))
                html_content += f"<tr>\n"
                html_content += f"<td><strong>Major</strong></td>\n"
                html_content += f"<td>{major_count}</td>\n"
                html_content += f"<td>{percentage:.1f}%</td>\n"
                html_content += f"<td>{major_list}</td>\n"
                html_content += f"</tr>\n"

            # Process Accessory mutations
            accessory_count = len(set(mutation_data["accessory_mutations"]))
            if accessory_count > 0:
                percentage = (
                    (accessory_count / total_mutations * 100)
                    if total_mutations > 0
                    else 0
                )
                accessory_list = ", ".join(
                    sorted(set(mutation_data["accessory_mutations"]))
                )
                html_content += f"<tr>\n"
                html_content += f"<td><strong>Accessory</strong></td>\n"
                html_content += f"<td>{accessory_count}</td>\n"
                html_content += f"<td>{percentage:.1f}%</td>\n"
                html_content += f"<td>{accessory_list}</td>\n"
                html_content += f"</tr>\n"

            # Process SDRM mutations
            sdrm_count = len(set(mutation_data["sdrm_mutations"]))
            if sdrm_count > 0:
                percentage = (
                    (sdrm_count / total_mutations * 100) if total_mutations > 0 else 0
                )
                sdrm_list = ", ".join(sorted(set(mutation_data["sdrm_mutations"])))
                html_content += f"<tr>\n"
                html_content += f"<td><strong>SDRM</strong></td>\n"
                html_content += f"<td>{sdrm_count}</td>\n"
                html_content += f"<td>{percentage:.1f}%</td>\n"
                html_content += f"<td>{sdrm_list}</td>\n"
                html_content += f"</tr>\n"

            # Process other mutations
            other_count = len(set(mutation_data["other_mutations"]))
            if other_count > 0:
                percentage = (
                    (other_count / total_mutations * 100) if total_mutations > 0 else 0
                )

                # For other mutations, create a condensed display with expandable content
                other_mutations = sorted(set(mutation_data["other_mutations"]))

                # For small numbers, just show directly
                if other_count <= 10:
                    other_list = ", ".join(other_mutations)
                    html_content += f"<tr>\n"
                    html_content += f"<td><strong>Other</strong></td>\n"
                    html_content += f"<td>{other_count}</td>\n"
                    html_content += f"<td>{percentage:.1f}%</td>\n"
                    html_content += f"<td>{other_list}</td>\n"
                    html_content += f"</tr>\n"
                else:
                    # For larger lists, create a collapsible display
                    html_content += f"<tr>\n"
                    html_content += f"<td><strong>Other</strong></td>\n"
                    html_content += f"<td>{other_count}</td>\n"
                    html_content += f"<td>{percentage:.1f}%</td>\n"
                    html_content += (
                        f"<td><details><summary>Show all other mutations</summary>\n"
                    )

                    # Split into chunks for better readability
                    chunks = [
                        other_mutations[i : i + 10]
                        for i in range(0, len(other_mutations), 10)
                    ]
                    for chunk in chunks:
                        html_content += (
                            f"<div class='mutation-chunk'>{', '.join(chunk)}</div>\n"
                        )

                    html_content += f"</details></td>\n"
                    html_content += f"</tr>\n"

            # Add a total row
            html_content += f"<tr class='table-secondary'>\n"
            html_content += f"<td><strong>Total</strong></td>\n"
            html_content += f"<td><strong>{total_mutations}</strong></td>\n"
            html_content += f"<td>100.0%</td>\n"
            html_content += f"<td>All positions: {mutation_data['first_aa']}-{mutation_data['last_aa']}</td>\n"
            html_content += f"</tr>\n"

            html_content += "</tbody>\n"
            html_content += "</table>\n"
            html_content += "</div>\n"

            html_content += create_html_footer()

            # Write to file
            output_file = os.path.join(
                output_dir, f"mutation_position_map_{gene_name.lower()}_mqc.html"
            )
            with open(output_file, "w") as f:
                f.write(html_content)
