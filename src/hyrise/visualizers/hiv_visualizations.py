# hyrise/visualizers/hiv_visualizations.py
"""
Comprehensive visualization module for HyRISE package

This module provides a consolidated set of visualization functions for HIV drug
resistance data, organized into logical categories:
1. Mutation-based visualizations
2. Resistance-based visualizations
3. Mutation-resistance impact visualizations
"""
import os
import json
from collections import defaultdict

from ..utils.html_utils import create_html_header, create_html_footer


# ===== MUTATION-BASED VISUALIZATIONS =====


def create_mutation_details_table(data, sample_id, output_dir):
    """
    Creates a comprehensive table of all detected mutations with their properties.

    This visualization includes mutation positions, types, SDRM status, and other
    properties in a filterable table format.

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
                "Position": position,
                "Type": mutation_type,
                "Is SDRM": "Yes" if is_sdrm else "No",
                "Is APOBEC": "Yes" if is_apobec else "No",
                "Is Unusual": "Yes" if is_unusual else "No",
            }

    # Create consolidated table for each gene
    for gene_name, mutations in gene_mutations.items():
        if mutations:
            # Calculate min and max positions for proper scaling
            positions = [
                val["Position"]
                for val in mutations.values()
                if isinstance(val["Position"], (int, float))
            ]
            min_position = min(positions) if positions else 1
            max_position = max(positions) if positions else 300

            # Enhanced table configuration with professional styling
            table_output = {
                "id": f"mutation_details_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Mutations",
                "description": f"Comprehensive listing of all mutations detected in the {gene_name} gene with their positions and properties. This table includes major resistance mutations, accessory mutations, surveillance drug resistance mutations (SDRMs), APOBEC-mediated mutations, and unusual mutations.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"mutation_details_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Mutation Details",
                    "namespace": "Mutation Analysis",
                    "save_file": True,
                    "col1_header": "Mutation",
                    "sort_rows": True,
                    # Default sorting by position for logical genomic order
                    "defaultsort": [{"column": "Position", "direction": "asc"}],
                    # Enable table filtering capabilities
                    "filters": True,
                    # Enable conditional formatting with subtle styling
                    "conditional_formatting": True,
                    # Configure a reasonable max number of columns
                    "max_configurable_table_columns": 300,
                },
                "headers": {
                    "Mutation": {
                        "title": "Mutation",
                        "description": "Mutation code",
                        "namespace": "Mutation Details",
                        "filterable": True,
                    },
                    "Position": {
                        "title": "Position",
                        "description": "Position in gene sequence",
                        "namespace": "Mutation Details",
                        # Format position as integer without decimal places
                        "format": "{:,.0f}",
                        # Scale for coloring based on position
                        "scale": "Blues",
                        "min": min_position,
                        "max": max_position,
                        "bars": True,
                    },
                    "Type": {
                        "title": "Type",
                        "description": "Mutation type (Major, Accessory, or Other)",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        # Use subtle background colors for different mutation types
                        "bgcols": {
                            "Major": "#f5e6e6",  # Very subtle red
                            "Accessory": "#faf0e1",  # Very subtle orange
                            "Other": "#f8f9fa",  # Light gray
                        },
                    },
                    "Is SDRM": {
                        "title": "SDRM",
                        "description": "Surveillance Drug Resistance Mutation",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        # Subtle highlighting for SDRMs
                        "bgcols": {"Yes": "#f5f9f5", "No": ""},  # Very subtle green
                    },
                    "Is APOBEC": {
                        "title": "APOBEC",
                        "description": "APOBEC-mediated G-to-A hypermutation",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        "bgcols": {"Yes": "#f9f5fc", "No": ""},  # Very subtle purple
                    },
                    "Is Unusual": {
                        "title": "Unusual",
                        "description": "Mutation that is rarely observed in untreated patients",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        "bgcols": {"Yes": "#f9f7f7", "No": ""},  # Very subtle pink
                    },
                },
                "data": mutations,
            }

            # Write the consolidated table to file
            output_file = os.path.join(
                output_dir, f"mutation_details_{gene_name.lower()}_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(table_output, f, indent=2)


def create_mutation_position_visualization(data, sample_id, output_dir):
    """
    Creates an interactive visualization of mutations along the gene sequence.

    This HTML-based visualization shows the position of mutations along the gene,
    color-coded by type with interactive tooltips showing details.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Create a data structure to store mutation details by position and type
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

                # Store by mutation type
                if mutation_type == "Major":
                    gene_mutations[gene_name]["major_positions"].append(position)
                elif mutation_type == "Accessory":
                    gene_mutations[gene_name]["accessory_positions"].append(position)
                else:
                    gene_mutations[gene_name]["other_positions"].append(position)

                if is_sdrm:
                    gene_mutations[gene_name]["sdrm_positions"].append(position)

                if is_apobec:
                    gene_mutations[gene_name]["apobec_positions"].append(position)

                # Store detailed mutation information for the tooltip
                gene_mutations[gene_name]["mutation_details"][position].append(
                    {
                        "text": mutation_text,
                        "type": mutation_type,
                        "is_sdrm": is_sdrm,
                        "is_apobec": is_apobec,
                    }
                )

    # Create visualization for each gene
    for gene_name, mutation_data in gene_mutations.items():
        if mutation_data["positions"]:
            # Create HTML visualization
            html_content = create_html_header(
                f"mutation_position_map_{gene_name.lower()}",
                f"{gene_name} Mutation Position Map",
                f"Interactive visualization of mutations along the {gene_name} gene sequence, highlighting positions of major, accessory, and other mutations with surveillance drug resistance mutations (SDRMs) and APOBEC-mediated mutations specially marked.",
            )

            html_content += f"<h3>{gene_name} Mutation Position Map</h3>\n"

            # Brief introduction
            total_mutations = len(mutation_data["positions"])
            html_content += f"<p>This visualization shows {total_mutations} mutations detected in the {gene_name} gene (positions {mutation_data['first_aa']}-{mutation_data['last_aa']}). Hover over colored positions for details.</p>\n"

            # Create a professional position map with subtle styling
            html_content += "<style>\n"
            # Position map styling - using professional, subtle styling
            html_content += ".position-map { display: flex; flex-wrap: wrap; margin: 20px 0; background-color: #f9f9f9; padding: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }\n"
            html_content += ".position-cell { width: 22px; height: 22px; margin: 1px; text-align: center; font-size: 10px; line-height: 22px; background-color: #f2f2f2; position: relative; border-radius: 2px; }\n"
            # Using more professional, less saturated colors
            html_content += (
                ".position-major { background-color: #e57373; color: white; }\n"
            )
            html_content += (
                ".position-accessory { background-color: #ffb74d; color: white; }\n"
            )
            html_content += (
                ".position-other { background-color: #64b5f6; color: white; }\n"
            )
            html_content += ".position-sdrm { border: 2px solid #81c784; }\n"
            html_content += ".position-apobec { border: 2px dashed #9575cd; }\n"

            # Tooltip styling - more professional look
            html_content += ".position-tooltip { display: none; position: absolute; background-color: #424242; color: white; padding: 10px; border-radius: 4px; font-size: 12px; z-index: 100; min-width: 200px; max-width: 250px; top: -5px; left: 100%; transform: translateY(-50%); text-align: left; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }\n"
            html_content += (
                ".position-cell:hover .position-tooltip { display: block; }\n"
            )
            html_content += ".position-tooltip ul { margin: 0; padding-left: 15px; }\n"
            html_content += ".position-tooltip li { margin: 5px 0; }\n"

            # Legend and summary styling
            html_content += ".position-legend { margin: 20px 0; background-color: #f9f9f9; padding: 15px; border-radius: 5px; display: flex; flex-wrap: wrap; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }\n"
            html_content += ".legend-item { margin-right: 25px; margin-bottom: 10px; display: flex; align-items: center; font-size: 13px; }\n"
            html_content += ".legend-box { width: 15px; height: 15px; margin-right: 8px; border-radius: 2px; }\n"
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

            html_content += create_html_footer()

            # Write the HTML position map to file
            output_file = os.path.join(
                output_dir, f"mutation_position_map_{gene_name.lower()}_mqc.html"
            )
            with open(output_file, "w") as f:
                f.write(html_content)


def create_mutation_type_summary(data, sample_id, output_dir):
    """
    Creates a summary table and chart showing distribution of mutation types.

    This visualization includes counts and percentages of major, accessory,
    and other mutations, with representative examples.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize mutations by gene and type
    gene_mutations = defaultdict(
        lambda: {
            "major_mutations": [],
            "accessory_mutations": [],
            "other_mutations": [],
            "sdrm_mutations": [],
            "apobec_mutations": [],
            "total_mutations": 0,
            "positions": [],
        }
    )

    for gene_seq in data.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]
        first_aa = gene_seq.get("firstAA", 1)
        last_aa = gene_seq.get("lastAA", 300)

        # Get SDRMs
        sdrm_texts = [sdrm.get("text", "") for sdrm in gene_seq.get("SDRMs", [])]

        for mutation in gene_seq.get("mutations", []):
            position = mutation.get("position")
            if position:
                mutation_text = mutation.get("text", "")
                mutation_type = mutation.get("primaryType", "Other")
                is_apobec = mutation.get("isApobecMutation", False)
                is_sdrm = mutation_text in sdrm_texts

                # Add position to list of unique positions
                if position not in gene_mutations[gene_name]["positions"]:
                    gene_mutations[gene_name]["positions"].append(position)

                # Store mutation texts by type
                if mutation_type == "Major":
                    gene_mutations[gene_name]["major_mutations"].append(mutation_text)
                elif mutation_type == "Accessory":
                    gene_mutations[gene_name]["accessory_mutations"].append(
                        mutation_text
                    )
                else:
                    gene_mutations[gene_name]["other_mutations"].append(mutation_text)

                if is_sdrm:
                    gene_mutations[gene_name]["sdrm_mutations"].append(mutation_text)

                if is_apobec:
                    gene_mutations[gene_name]["apobec_mutations"].append(mutation_text)

            # Process each gene
            for gene_name, mutation_data in gene_mutations.items():
                if mutation_data["positions"]:
                    # Update total mutations count
                    total_positions = len(mutation_data["positions"])
                    mutation_data["total_mutations"] = total_positions

                    # -----------------------------------------------------------------
                    # 1. Create a MultiQC-native table for mutation summary
                    # -----------------------------------------------------------------
                    mutation_table_data = {}

                    # Prepare table data for Major mutations
                    major_count = len(set(mutation_data["major_mutations"]))
                    if major_count > 0:
                        percentage = (
                            (major_count / total_positions * 100)
                            if total_positions > 0
                            else 0
                        )
                        mutation_table_data["Major"] = {
                            "Count": major_count,
                            "Percentage": round(percentage, 1),
                            "Examples": ", ".join(
                                sorted(set(mutation_data["major_mutations"]))
                            ),
                        }

                    # Prepare table data for Accessory mutations
                    accessory_count = len(set(mutation_data["accessory_mutations"]))
                    if accessory_count > 0:
                        percentage = (
                            (accessory_count / total_positions * 100)
                            if total_positions > 0
                            else 0
                        )
                        mutation_table_data["Accessory"] = {
                            "Count": accessory_count,
                            "Percentage": round(percentage, 1),
                            "Examples": ", ".join(
                                sorted(set(mutation_data["accessory_mutations"]))
                            ),
                        }

                    # Prepare table data for SDRM mutations
                    sdrm_count = len(set(mutation_data["sdrm_mutations"]))
                    if sdrm_count > 0:
                        percentage = (
                            (sdrm_count / total_positions * 100)
                            if total_positions > 0
                            else 0
                        )
                        mutation_table_data["SDRM"] = {
                            "Count": sdrm_count,
                            "Percentage": round(percentage, 1),
                            "Examples": ", ".join(
                                sorted(set(mutation_data["sdrm_mutations"]))
                            ),
                        }

                    # Prepare table data for Other mutations
                    other_count = len(set(mutation_data["other_mutations"]))
                    if other_count > 0:
                        percentage = (
                            (other_count / total_positions * 100)
                            if total_positions > 0
                            else 0
                        )
                        mutation_table_data["Other"] = {
                            "Count": other_count,
                            "Percentage": round(percentage, 1),
                            "Examples": ", ".join(
                                sorted(set(mutation_data["other_mutations"]))
                            ),
                        }

                    # Create the MultiQC table
                    mutation_summary_table = {
                        "id": f"mutation_summary_{gene_name.lower()}_table",
                        "section_name": f"{gene_name} Mutation Summary",
                        "description": f"Summary of mutation types detected in the {gene_name} gene, including counts, percentages, and complete lists of mutations by type.",
                        "plot_type": "table",
                        "pconfig": {
                            "id": f"mutation_summary_{gene_name.lower()}_table_config",
                            "title": f"{gene_name} Mutation Type Distribution",
                            "namespace": "Mutation Analysis",
                            "save_file": True,
                            "col1_header": "Mutation Type",
                            "sortRows": False,  # Preserve the order of rows as defined
                        },
                        "headers": {
                            "Count": {
                                "title": "Count",
                                "description": "Number of unique mutations of this type",
                                "format": "{:,.0f}",
                                "scale": "Blues",
                                "min": 0,
                                "bars": True,
                            },
                            "Percentage": {
                                "title": "Percentage",
                                "description": "Percentage of all mutations",
                                "suffix": "%",
                                "format": "{:,.1f}",
                                "scale": "Blues",
                                "min": 0,
                                "max": 100,
                                "bars": True,
                            },
                            "Examples": {
                                "title": "Mutations",
                                "description": "Complete list of mutations of this type",
                                "scale": False,
                            },
                        },
                        "data": mutation_table_data,
                    }

                    # Write the mutation summary table to file
                    output_file = os.path.join(
                        output_dir, f"mutation_summary_{gene_name.lower()}_mqc.json"
                    )
                    with open(output_file, "w") as f:
                        json.dump(mutation_summary_table, f, indent=2)
            # # -----------------------------------------------------------------
            # # 2. Create a MultiQC-native bargraph for mutation type distribution
            # # -----------------------------------------------------------------
            # # Prepare data for bargraph - CORRECT FORMAT for MultiQC
            # bargraph_data = {
            #     # Sample name as the first key
            #     sample_id: {
            #         # Category keys with values
            #         "Major": len(set(mutation_data["major_mutations"])),
            #         "Accessory": len(set(mutation_data["accessory_mutations"])),
            #         "Other": len(set(mutation_data["other_mutations"]))
            #     }
            # }

            # mutation_bargraph = {
            #     "id": f"mutation_distribution_{gene_name.lower()}_bargraph",
            #     "section_name": f"{gene_name} Mutation Distribution",
            #     "description": f"Distribution of mutation types in the {gene_name} gene, showing the count of major, accessory, and other mutations.",
            #     "plot_type": "bargraph",
            #     "pconfig": {
            #         "id": f"mutation_distribution_{gene_name.lower()}_bargraph_config",
            #         "title": f"{gene_name} Mutation Type Distribution",
            #         "ylab": "Number of Mutations",
            #         "cpswitch": False,  # Disable counts/percentages switch
            #         "tt_percentages": True,  # Show percentages in tooltip
            #         "ymin": 0,  # Start y-axis at 0
            #         "colors": {
            #             "Major": "#e57373",  # Match the position map colors
            #             "Accessory": "#ffb74d",
            #             "Other": "#64b5f6"
            #         }
            #     },
            #     "data": bargraph_data
            # }

            # # Write the bargraph to file
            # output_file = os.path.join(
            #     output_dir, f"mutation_distribution_{gene_name.lower()}_bargraph_mqc.json"
            # )
            # with open(output_file, "w") as f:
            #     json.dump(mutation_bargraph, f, indent=2)


# ===== RESISTANCE-BASED VISUALIZATIONS =====


def create_drug_resistance_profile(data, sample_id, output_dir):
    """
    Creates a comprehensive table of drug resistance scores and interpretations.

    This visualization includes drugs, their classes, resistance scores and levels
    with clinical interpretations in a filterable, sortable table.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize data by gene
    gene_drug_data = defaultdict(dict)

    # Create more subtle color mapping for resistance levels suitable for professional contexts
    resistance_colors = {
        "Susceptible": "#eaf5ea",  # Very subtle green
        "Potential Low-Level": "#e6f2f7",  # Very subtle blue
        "Low-Level": "#faf0e1",  # Very subtle orange
        "Intermediate": "#f9ece0",  # Very subtle darker orange
        "High-Level": "#f5e9e9",  # Very subtle red
    }

    # Define drug classes based on WHO standards
    drug_classes = {
        "NRTI": ["ABC", "AZT", "D4T", "DDI", "FTC", "3TC", "TDF"],
        "NNRTI": ["DOR", "EFV", "ETR", "NVP", "RPV", "DPV"],
        "PI": ["ATV/r", "DRV/r", "FPV/r", "IDV/r", "LPV/r", "NFV", "SQV/r", "TPV/r"],
        "INSTI": ["BIC", "CAB", "DTG", "EVG", "RAL"],
        "CAI": ["LEN"],
    }

    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            resistance_level = drug_score["text"]
            score = drug_score["score"]
            level = drug_score.get("level", 0)

            # Map SIR classification (Susceptible, Intermediate, Resistant)
            sir_classification = "S"  # Default to Susceptible
            if level >= 5:
                sir_classification = "R"  # High-Level Resistance = Resistant
            elif level >= 3:
                sir_classification = "I"  # Low-Level/Intermediate = Intermediate

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
                "SIR": sir_classification,
            }

    # Create a single table for each gene
    for gene_name, drugs_data in gene_drug_data.items():
        if drugs_data:
            # Enhanced table configuration with professional styling
            table_data = {
                "id": f"drug_resistance_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Drug Resistance Profile",
                "description": f"Comprehensive analysis of antiretroviral drug susceptibility and resistance patterns based on genetic mutations, with quantitative resistance scores and clinical interpretations for {gene_name} gene.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"drug_resistance_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Drug Resistance Profile",
                    "namespace": "Resistance Analysis",
                    "save_file": True,
                    "col1_header": "Drug",
                    "sort_rows": True,
                    # Default sorting by resistance level (high to low)
                    "defaultsort": [
                        {"column": "Level", "direction": "desc"},
                        {"column": "Drug Class", "direction": "asc"},
                    ],
                    # Enable filtering for research flexibility
                    "filters": True,
                    # Enable conditional formatting but with more subtle styling
                    "conditional_formatting": True,
                    # Configure a reasonable max for columns
                    "max_configurable_table_columns": 300,
                },
                "headers": {
                    "Drug": {
                        "title": "Drug",
                        "description": "Antiretroviral drug",
                        "namespace": "Drug Information",
                        "filterable": True,
                    },
                    "Drug Class": {
                        "title": "Class",
                        "description": "Drug class (e.g., NRTI, NNRTI, PI, INSTI, CAI)",
                        "namespace": "Drug Information",
                        "filterable": True,
                        # Use very subtle background colors for drug classes
                        "bgcols": {
                            "NRTI": "#f5f9fc",  # Very subtle blue
                            "NNRTI": "#f5fcf9",  # Very subtle green-blue
                            "PI": "#fcf9f5",  # Very subtle orange
                            "INSTI": "#f9f5fc",  # Very subtle purple
                            "CAI": "#f5f5f5",  # Very subtle gray
                            "Unknown": "#ffffff",
                        },
                    },
                    "Score": {
                        "title": "Score",
                        "description": "Drug resistance score (0-60+): Higher scores indicate greater resistance",
                        "namespace": "Resistance Metrics",
                        "min": 0,
                        "max": 60,
                        # Professional color scale - blues is more neutral and professional
                        "scale": "Blues",
                        "format": "{:,.0f}",  # No decimal places for scores
                        # Bar formatting for clear visualization
                        "bars": True,
                        "bars_zero_centrepoint": False,
                    },
                    "SIR": {
                        "title": "SIR",
                        "description": "Susceptible (S), Intermediate (I), or Resistant (R) classification",
                        "namespace": "Resistance Metrics",
                        "filterable": True,
                        # Subtle background colors for SIR classification
                        "bgcols": {
                            "S": "#eaf5ea",  # Very subtle green
                            "I": "#faf0e1",  # Very subtle orange
                            "R": "#f5e9e9",  # Very subtle red
                        },
                    },
                    "Level": {
                        "title": "Level",
                        "description": "Numeric resistance level (1-5)",
                        "namespace": "Resistance Metrics",
                        "hidden": True,  # Hidden by default but available for sorting
                        "format": "{:,.0f}",
                    },
                    "Resistance Level": {
                        "title": "Interpretation",
                        "description": "Clinical interpretation of resistance level",
                        "namespace": "Resistance Metrics",
                        "filterable": True,
                        # Very subtle background colors based on resistance level
                        "bgcols": resistance_colors,
                        # Professional conditional formatting with subtle visual cues
                        "cond_formatting_rules": {
                            "custom1": [{"s_eq": "Susceptible"}],
                            "custom2": [{"s_eq": "Potential Low-Level"}],
                            "custom3": [{"s_eq": "Low-Level"}],
                            "custom4": [{"s_eq": "Intermediate"}],
                            "custom5": [{"s_eq": "High-Level"}],
                        },
                        "cond_formatting_colours": [
                            {
                                "custom1": "#2e7d32",  # Dark green text
                                "custom2": "#1976d2",  # Dark blue text
                                "custom3": "#ed6c02",  # Dark orange text
                                "custom4": "#d32f2f",  # Dark red text
                                "custom5": "#9c27b0",  # Dark purple text
                            }
                        ],
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


def create_drug_class_resistance_summary(data, sample_id, output_dir):
    """
    Creates a summary table and visualization of resistance by drug class.

    This visualization shows resistance patterns across drug classes,
    with counts and percentages of resistant drugs.

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

    # Process each gene
    for gene_name, class_overview in gene_class_overview.items():
        if class_overview:
            # Create MultiQC-native table for drug class overview
            table_data = {}

            # Calculate total drugs and resistant percentage across all classes
            total_drugs = sum(cls["total_drugs"] for cls in class_overview.values())
            total_resistant = sum(
                cls["resistant_drugs"] for cls in class_overview.values()
            )
            overall_resistant_percent = (
                (total_resistant / total_drugs * 100) if total_drugs > 0 else 0
            )

            # Add a row for each drug class
            for drug_class, overview in sorted(class_overview.items()):
                resistant_percent = (
                    (overview["resistant_drugs"] / overview["total_drugs"] * 100)
                    if overview["total_drugs"] > 0
                    else 0
                )

                # Create a row ID for the drug class
                row_id = f"{gene_name}_{drug_class.replace(' ', '_')}"

                # Determine resistance status based on percentage
                resistance_status = "No significant resistance"
                if resistant_percent >= 66:
                    resistance_status = "High-level resistance"
                elif resistant_percent >= 33:
                    resistance_status = "Moderate resistance"
                elif resistant_percent > 0:
                    resistance_status = "Low-level resistance"

                # Store the data
                table_data[row_id] = {
                    "Drug Class": drug_class,
                    "Total Drugs": overview["total_drugs"],
                    "Resistant Drugs": overview["resistant_drugs"],
                    "Resistant (%)": round(resistant_percent, 1),
                    "Max Score": overview["max_score"],
                    "Status": resistance_status,
                    "High-Level": overview["high_resistance"],
                    "Intermediate": overview["intermediate"],
                    "Low-Level": overview["low_resistance"],
                    "Potential Low": overview["potential_low"],
                    "Susceptible": overview["susceptible"],
                }

            # Create a professional summary table
            summary_table = {
                "id": f"drug_class_overview_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Drug Class Overview",
                "description": f"Summary of drug resistance patterns by drug class for {gene_name}. This table shows the proportion of drugs in each class with resistance, categorized by resistance level. Overall resistance: {round(overall_resistant_percent, 1)}% of drugs show resistance.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"drug_class_overview_{gene_name.lower()}_table_config",
                    "title": f"{gene_name} Drug Class Resistance Summary",
                    "namespace": "Resistance Analysis",
                    "save_file": True,
                    "col1_header": "Drug Class",
                    "sort_rows": True,
                    # Default sorting by resistant percentage (high to low)
                    "defaultsort": [{"column": "Resistant (%)", "direction": "desc"}],
                    # Enable filtering
                    "filters": True,
                },
                "headers": {
                    "Drug Class": {
                        "title": "Drug Class",
                        "description": "Antiretroviral drug class",
                        "namespace": "Classes",
                    },
                    "Total Drugs": {
                        "title": "Total Drugs",
                        "description": "Total number of drugs in this class",
                        "namespace": "Classes",
                        "format": "{:,.0f}",
                        "scale": False,
                    },
                    "Resistant Drugs": {
                        "title": "Resistant",
                        "description": "Number of drugs showing resistance (Low-level or higher)",
                        "namespace": "Classes",
                        "format": "{:,.0f}",
                        "scale": "Blues",
                        "min": 0,
                        "bars": True,
                    },
                    "Resistant (%)": {
                        "title": "% Resistant",
                        "description": "Percentage of drugs in this class showing resistance",
                        "namespace": "Classes",
                        "suffix": "%",
                        "format": "{:,.1f}",
                        "scale": "Blues",
                        "min": 0,
                        "max": 100,
                        "bars": True,
                    },
                    "Max Score": {
                        "title": "Max Score",
                        "description": "Highest resistance score in this drug class",
                        "namespace": "Classes",
                        "format": "{:,.0f}",
                        "scale": "Blues",
                        "min": 0,
                        "max": 60,
                    },
                    "Status": {
                        "title": "Status",
                        "description": "Overall resistance status for this drug class",
                        "namespace": "Classes",
                        "filterable": True,
                        "bgcols": {
                            "High-level resistance": "#f5e6e6",  # Very subtle red
                            "Moderate resistance": "#faf0e1",  # Very subtle orange
                            "Low-level resistance": "#f5f9f5",  # Very subtle green
                            "No significant resistance": "#f8f9fa",  # Very subtle gray
                        },
                    },
                    "High-Level": {
                        "title": "High",
                        "description": "Number of drugs with high-level resistance",
                        "namespace": "Resistance Levels",
                        "format": "{:,.0f}",
                        "scale": "Reds",
                        "min": 0,
                        "bars": True,
                    },
                    "Intermediate": {
                        "title": "Int",
                        "description": "Number of drugs with intermediate resistance",
                        "namespace": "Resistance Levels",
                        "format": "{:,.0f}",
                        "scale": "Oranges",
                        "min": 0,
                        "bars": True,
                    },
                    "Low-Level": {
                        "title": "Low",
                        "description": "Number of drugs with low-level resistance",
                        "namespace": "Resistance Levels",
                        "format": "{:,.0f}",
                        "scale": "YlOrBr",
                        "min": 0,
                        "bars": True,
                    },
                    "Potential Low": {
                        "title": "Pot",
                        "description": "Number of drugs with potential low-level resistance",
                        "namespace": "Resistance Levels",
                        "format": "{:,.0f}",
                        "scale": "Blues",
                        "min": 0,
                        "bars": True,
                    },
                    "Susceptible": {
                        "title": "Sus",
                        "description": "Number of drugs that are susceptible",
                        "namespace": "Resistance Levels",
                        "format": "{:,.0f}",
                        "scale": "Greens",
                        "min": 0,
                        "bars": True,
                    },
                },
                "data": table_data,
            }

            # Write the class overview table to file
            output_file = os.path.join(
                output_dir, f"drug_class_overview_{gene_name.lower()}_table_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(summary_table, f, indent=2)


# ===== MUTATION-RESISTANCE IMPACT VISUALIZATIONS =====


def create_mutation_resistance_contribution(data, sample_id, output_dir):
    """
    Creates a table showing how specific mutations contribute to resistance scores.

    This visualization details the impact of individual mutations or mutation
    patterns on drug resistance, with contribution scores and percentages.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Organize data by gene
    gene_mutation_contribution = defaultdict(lambda: defaultdict(dict))

    # Define subtle color mapping for mutation types - using less saturated colors
    mutation_type_colors = {
        "Major": "#f8e6e6",  # Very subtle light red for major mutations
        "Accessory": "#fafaeb",  # Very subtle light yellow for accessory mutations
        "Other": "#f8f9fa",  # Light gray for other mutations
    }

    # Define drug classes based on WHO standards
    drug_classes = {
        "NRTI": ["ABC", "AZT", "D4T", "DDI", "FTC", "3TC", "TDF"],
        "NNRTI": ["DOR", "EFV", "ETR", "NVP", "RPV", "DPV"],
        "PI": ["ATV/r", "DRV/r", "FPV/r", "IDV/r", "LPV/r", "NFV", "SQV/r", "TPV/r"],
        "INSTI": ["BIC", "CAB", "DTG", "EVG", "RAL"],
        "CAI": ["LEN"],
    }

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

                # Track if any mutations are SDRMs
                is_sdrm = False

                for mutation in partial.get("mutations", []):
                    mutation_text = mutation.get("text", "")
                    mutation_texts.append(mutation_text)
                    mutation_types.append(mutation.get("primaryType", "Other"))

                    # Check if this is a SDRM
                    if mutation.get("isSDRM", False):
                        is_sdrm = True

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

                    # Create a unique row ID
                    safe_drug_name = (
                        drug_name.replace("/", "_").replace(" ", "_").replace("-", "_")
                    )
                    safe_mutation_name = (
                        mutation_key.replace(" ", "_")
                        .replace("/", "_")
                        .replace("-", "_")
                    )
                    row_id = f"{safe_drug_name}_{safe_mutation_name}"

                    # Calculate contribution significance level (for categorization)
                    significance = ""
                    if contribution >= 75:
                        significance = "Dominant"
                    elif contribution >= 50:
                        significance = "Major"
                    elif contribution >= 25:
                        significance = "Significant"
                    else:
                        significance = "Minor"

                    # Store the data with additional fields
                    gene_mutation_contribution[gene_name][row_id] = {
                        "Drug": drug_name,
                        "Drug Class": drug_class,
                        "Mutations": mutation_key,
                        "Mutation Type": primary_type,
                        "Is SDRM": "Yes" if is_sdrm else "No",
                        "Score": score,
                        "Total Score": total_score,
                        "Contribution (%)": round(contribution, 1),
                        "Impact": significance,
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
                    "namespace": "Resistance Analysis",
                    "save_file": True,
                    "col1_header": "Drug",
                    "sort_rows": True,
                    # Default sorting by contribution percentage (highest first)
                    "defaultsort": [
                        {"column": "Contribution (%)", "direction": "desc"}
                    ],
                    # Enable filtering for research flexibility
                    "filters": True,
                    # Enable conditional formatting but with more subtle styling
                    "conditional_formatting": True,
                    # Configure a reasonable max for columns
                    "max_configurable_table_columns": 300,
                },
                "headers": {
                    "Drug": {
                        "title": "Drug",
                        "description": "Antiretroviral drug",
                        "namespace": "Drug Information",
                        "filterable": True,
                    },
                    "Drug Class": {
                        "title": "Class",
                        "description": "Drug class category",
                        "namespace": "Drug Information",
                        "filterable": True,
                        # Use very subtle background colors for drug classes
                        "bgcols": {
                            "NRTI": "#f5f9fc",
                            "NNRTI": "#f5fcf9",
                            "PI": "#fcf9f5",
                            "INSTI": "#f9f5fc",
                            "CAI": "#f5f5f5",
                            "Unknown": "#ffffff",
                        },
                    },
                    "Mutations": {
                        "title": "Mutations",
                        "description": "Specific mutation or combination of mutations",
                        "namespace": "Mutation Details",
                        "filterable": True,
                    },
                    "Mutation Type": {
                        "title": "Type",
                        "description": "Primary type of mutation",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        # Use very subtle background colors for mutation types
                        "bgcols": mutation_type_colors,
                    },
                    "Is SDRM": {
                        "title": "SDRM",
                        "description": "Contains Surveillance Drug Resistance Mutation",
                        "namespace": "Mutation Details",
                        "filterable": True,
                        # Subtle highlighting for SDRMs
                        "bgcols": {"Yes": "#f5f9f5", "No": ""},
                    },
                    "Score": {
                        "title": "Contribution",
                        "description": "Points contributed to resistance score",
                        "namespace": "Resistance Impact",
                        "scale": "Blues",
                        "min": 0,
                        "max": 60,
                        "format": "{:,.0f}",
                        # Add bars to visualize the score
                        "bars": True,
                    },
                    "Total Score": {
                        "title": "Total Score",
                        "description": "Total resistance score for the drug",
                        "namespace": "Resistance Impact",
                        "format": "{:,.0f}",
                    },
                    "Contribution (%)": {
                        "title": "% of Total",
                        "description": "Percentage contribution to total resistance",
                        "namespace": "Resistance Impact",
                        "scale": "Blues",
                        "min": 0,
                        "max": 100,
                        "format": "{:,.1f}%",
                        # Add bars to visualize the percentage
                        "bars": True,
                    },
                    "Impact": {
                        "title": "Impact Category",
                        "description": "Categorization of the contribution significance",
                        "namespace": "Resistance Impact",
                        "filterable": True,
                        # No background colors for Impact column as requested
                        # Using conditional text formatting only for professionalism
                        "cond_formatting_rules": {
                            # Using text-only formatting that's more subtle and professional
                            "custom1": [{"s_eq": "Dominant"}],
                            "custom2": [{"s_eq": "Major"}],
                            "custom3": [{"s_eq": "Significant"}],
                            "custom4": [{"s_eq": "Minor"}],
                        },
                        "cond_formatting_colours": [
                            {
                                "custom1": "#666666",
                                "custom2": "#666666",
                                "custom3": "#666666",
                                "custom4": "#666666",
                            }
                        ],
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


def create_mutation_clinical_commentary(data, sample_id, output_dir):
    """
    Creates a MultiQC-native table showing clinical implications of mutations.

    This function generates a consolidated tabular visualization of mutation clinical
    significance, grouping by mutations and eliminating redundant clinical commentary.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """

    # Collection structure for mutation commentary - organized by mutation
    gene_mutation_data = defaultdict(
        lambda: defaultdict(
            lambda: {
                "mutation_type": "",
                "clinical_implication": "",
                "affected_drugs": [],
                "max_score": 0,
            }
        )
    )

    # Collect clinical commentary for all mutations
    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            # Only include drugs with at least some resistance (score ≥ 5)
            # if drug_score["score"] < 5:
            #     continue

            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            drug_display = f"{drug_name} ({drug_class})"

            # Process each partial score contribution
            for partial in drug_score.get("partialScores", []):
                score = partial.get("score", 0)

                for mutation in partial.get("mutations", []):
                    mutation_text = mutation.get("text", "")
                    mutation_type = mutation.get("primaryType", "Other")

                    # Store mutation type
                    gene_mutation_data[gene_name][mutation_text][
                        "mutation_type"
                    ] = mutation_type

                    # Add drug to affected drugs with its score
                    gene_mutation_data[gene_name][mutation_text][
                        "affected_drugs"
                    ].append({"drug": drug_display, "score": score})

                    # Track maximum score
                    if (
                        score
                        > gene_mutation_data[gene_name][mutation_text]["max_score"]
                    ):
                        gene_mutation_data[gene_name][mutation_text][
                            "max_score"
                        ] = score

                    # Process clinical comments - we only need to store one unique comment per mutation
                    if "comments" in mutation and mutation.get("comments"):
                        for comment in mutation.get("comments", []):
                            comment_text = comment.get("text", "")
                            if (
                                comment_text
                                and not gene_mutation_data[gene_name][mutation_text][
                                    "clinical_implication"
                                ]
                            ):
                                gene_mutation_data[gene_name][mutation_text][
                                    "clinical_implication"
                                ] = comment_text

    # Create a MultiQC table for each gene
    for gene_name, mutations in gene_mutation_data.items():
        if mutations:
            # Prepare data structure for MultiQC table
            table_data = {}

            # Create consolidated table entries
            for mutation_text, mutation_info in mutations.items():
                # Skip if missing critical information
                if (
                    not mutation_info["clinical_implication"]
                    or not mutation_info["affected_drugs"]
                ):
                    continue

                # Sort affected drugs by score (highest first)
                sorted_drugs = sorted(
                    mutation_info["affected_drugs"],
                    key=lambda x: x["score"],
                    reverse=True,
                )

                # Create a formatted affected drugs string
                affected_drugs_text = []
                for drug_info in sorted_drugs:
                    affected_drugs_text.append(
                        f"{drug_info['drug']} ({drug_info['score']})"
                    )

                # Create a row for this mutation
                row_id = f"{mutation_info["mutation_type"]}_{mutation_text}"
                table_data[row_id] = {
                    "Mutation Type": mutation_info["mutation_type"],
                    "Mutation": mutation_text,
                    "Affected Drugs": ", ".join(affected_drugs_text),
                    "Max Score": mutation_info["max_score"],
                    "Clinical Implication": mutation_info["clinical_implication"],
                }

            # Create the MultiQC table configuration
            clinical_table = {
                "id": f"mutation_clinical_{gene_name.lower()}_table",
                "section_name": f"{gene_name} Mutation Clinical Significance",
                "description": f"Consolidated analysis of {gene_name} mutations and their clinical implications for HIV drug resistance. This table groups information by mutation, showing affected drugs and their resistance scores.",
                "plot_type": "table",
                "pconfig": {
                    "id": f"mutation_clinical_{gene_name.lower()}_table_config",
                    "title": f"HyRISE: {gene_name} Mutation Clinical Significance",
                    "namespace": "Clinical Interpretation",
                    "save_file": True,
                    "col1_header": "Mutation Type",
                    "sortRows": True,
                    "use_datatables": True,
                    "searchable": True,
                },
                "headers": {
                    "Mutation Type": {
                        "title": "Type",
                        "description": "Mutation classification (Major, Accessory, Other)",
                        "scale": False,
                        "filterable": True,
                    },
                    "Mutation": {
                        "title": "Mutation",
                        "description": "Mutation identifier",
                        "scale": False,
                        "filterable": True,
                    },
                    "Affected Drugs": {
                        "title": "Affected Drugs",
                        "description": "Drugs affected by this mutation with resistance scores",
                        "scale": False,
                        "filterable": True,
                    },
                    "Max Score": {
                        "title": "Max Impact",
                        "description": "Maximum resistance score contribution across all drugs",
                        "format": "{:,.0f}",
                        "scale": "RdYlGn-rev",
                        "min": 0,
                        "bars": True,
                    },
                    "Clinical Implication": {
                        "title": "Clinical Implication",
                        "description": "Detailed commentary on clinical significance",
                        "scale": False,
                        "width": "50%",
                    },
                },
                "data": table_data,
            }

            # Write the table to file
            output_file = os.path.join(
                output_dir, f"mutation_clinical_{gene_name.lower()}_table_mqc.json"
            )
            with open(output_file, "w") as f:
                json.dump(clinical_table, f, indent=2)
