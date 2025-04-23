# hyrise/visualizers/hiv_visualizations.py
"""
Comprehensive visualization module for HyRISE package

This module provides a consolidated set of visualization functions for HIV drug
resistance data, organized into logical categories:
1. Mutation-based visualizations
2. Resistance-based visualizations
3. Mutation-resistance impact visualizations

The module supports multiple HIV genes including PR, RT, IN, and CA (Capsid).
"""
import os
import json
import logging
from collections import defaultdict

from hyrise.utils.html_utils import create_html_header, create_html_footer

# Set up logging
logger = logging.getLogger("hyrise.visualizers")

# Define all supported HIV genes and their typical lengths
# This helps with properly scaling visualizations
int_seq = "TTTTTAGATGGAATAGATAAGGCCCAAGATGAACATGAGAAATATCACAGTAATTGGAGAGCAATGGCTAGTGATTTTAACCTGCCACCTGTAGTAGCAAAAGAAATAGTAGCCAGCTGTGATAAATGTCAGCTAAAAGGAGAAGCCATGCATGGACAAGTAGACTGTAGTCCAGGAATATGGCAACTAGATTGTACACATTTAGAAGGAAAAGTTATCATGGTAGCAGTTCATGTAGCCAGTGGATATATAGAAGCAGAAGTTATTCCAGCAGAAACAGGGCAGGAAACAGCATATTTTCTTTTAAAATTAGCAGGAAGATGGCCGGTAAAAACAATACATACAGACAATGGCAGCAATTACACCAGTGCTACGGTTAAGGCCGCCTGTTGGTGGGCGGGAATCAAGCAGGAATTTGGAATTCCCTACAATCCCCAAAGTCAAGGAGTAATAGAATCTATGAATAAAGAATTAAAGAAAATTATAAGACAGGTAAGAGATCAGGCTGAACATCTTAAGACAGCAGTACAAATGGCAGTATTCATCCACAATTTTAAAAGAAAAGGGGGGATTGGGGGGTACAGTGCAGGGGAAAGAATAGTAGACATAATAGCAACAGACATACAAACTAAAGAATTACAAAAACAAATTACAAAAATTCAAAATTTTCGGGTTTATTACAGGGACAGCAGAAATCCACTTTGGAAAGGACCAGCAAAGCTCCTCTGGAAAGGTGAAGGGGCAGTAGTAATACAAGATAATAGTRACATAAAAGTAGTGCCAAGAAGAAAAGCAAAGATCATTAGGGATTATGGAAAACAGATGGCAGGTGATGATTGTGTGGCAAGTAGACAGGATGAGGAT"
pr_seq = "CCTCAAATCACTCTTTGGCAACGACCCCTCGTCACAATAAAGATAGGRGGGCAGCTAAMGGAAGCTCTATTAGATACAGGAGCAGATGATACAGTATTAGAAGACATGGARTTGCCAGGAAGATGGAAACCAAAAATGATAGGGGGAATTGGAGGTTTTATCAAAGTAAGACAGTATGATCAGRTACCCATAGAAATTTGTGGACAYAAAACTATAGGTWCAGTATTAATAGGACCTACACCWGTTAACATAATTGGAAGAAATCTGATGAYTCAGCTTGGTTGCACTTTAAATTTT"
cap_seq = "CCTATAGTGCAGAACATCCAGGGGCAAATGGTACATCAGGCCATATCACCTAGAACTTTAAATGCATGGGTAAAAGTAGTAGAAGAGAAGGCTTTCAGCCCAGAAGTGATACCCATGTTTTCAGCATTATCAGAAGGAGCCACCCCACAAGATTTAAACACCATGCTAAACACAGTGGGGGGACATCAAGCAGCCATGCAAATGTTAAAAGAGACCATCAATGAGGAAGCTGCAGAATGGGATAGAGTGCATCCAGTGCATGCAGGGCCTATTGCACCAGGCCAGATGAGAGAACCAAGGGGAAGTGACATAGCAGGAACTACTAGTACCCTTCAGGAACAAATAGGATGGATGACAAATAATCCACCTATCCCAGTAGGAGAAATTTATAAAAGATGGATAATCCTGGGATTAAATAAAATAGTAAGAATGTATAGCCCTACCAGCATTCTGGACATAAGACAAGGACCAAAGGAACCCTTTAGAGACTATGTAGACCGGTTCTATAAAACTCTAAGAGCCGAGCAAGCTTCACAGGAGGTAAAAAATTGGATGACAGAAACCTTGTTGGTCCAAAATGCGAACCCAGATTGTAAGACTATTTTAAAAGCATTGGGACCAGCGGCTACACTAGAAGAAATGATGACAGCATGTCAGGGAGTAGGAGGACCCGGCCATAAGGCAAGAGTTTTG"
rt_seq = "CCCATTAGTCCTATTGAAACTGTACCAGTAAAATTAAAGCCAGGAATGGATGGCCCAAAGGTYAARCAATGGCCATTGACAGAAGAAAAAATAAAAGCATTAGTAGAAATTTGTACAGAAATGGAAAAGGAAGGRAAGATTTCAAAAATTGGACCTGAAAATCCATACAATACTCCAGTATTTGCCATAAAGAAAAAAGACAGTACTAAATGGAGAAAATTAGTAGATTTCAGAGAACTTAATAARAGAACTCAAGACTTCTGGGAAGTTCAATTAGGAATACCACATCCYGCAGGGTTAAAAAAGAAMAAGTCAGTAACAGTACTRGATGTGGGTGATGCATATTTTTCAGTTCCCTTATATGAAGACTTCAGGAAGTATACTGCATTCACCATACCTAGYACAAACAATGAGACACCAGGGATTAGATATCAGTACAATGTGCTGCCACAAGGATGGAAAGGATCACCAGCAATATTCCAAAGTAGCATGATAAAAATCTTAGAGCCTTTCAGAAAACAAAATCCAGARATAGTCATCTATCAATACGTGGATGATTTGTATGTAGSATCTGACTTAGAAATAGGGCAGCATAGAACAAAGATAGAGGAACTGAGAGCACATCTRTTRAAGTGGGGATTTACCACACCAGACAAAAAACATCAGAAAGAGCCTCCATTCCTTTGGATGGGTTATGAACTCCATCCTGATAAATGGACR"

GENE_TYPICAL_LENGTHS = {
    "PR": len(pr_seq) // 3,  # Protease
    "RT": len(rt_seq) // 3,  # Reverse Transcriptase
    "IN": len(int_seq) // 3,  # Integrase
    "CA": len(cap_seq) // 3,  # Capsid
}


# Define drug classes and their clinical priority (1-5, 5 being highest)
# This helps prioritize the most clinically relevant drugs in visualizations
DRUG_CLASSES = {
    "NRTI": {"priority": 5, "drugs": ["ABC", "AZT", "D4T", "DDI", "FTC", "3TC", "TDF"]},
    "NNRTI": {"priority": 4, "drugs": ["DOR", "EFV", "ETR", "NVP", "RPV", "DPV"]},
    "PI": {
        "priority": 5,
        "drugs": ["ATV/r", "DRV/r", "FPV/r", "IDV/r", "LPV/r", "NFV", "SQV/r", "TPV/r"],
    },
    "INSTI": {"priority": 5, "drugs": ["BIC", "CAB", "DTG", "EVG", "RAL"]},
    "CAI": {"priority": 4, "drugs": ["LEN"]},  # Capsid inhibitors
}

# Define drugs with highest clinical importance
HIGH_PRIORITY_DRUGS = {
    "DRV/r": 5,  # High genetic barrier to resistance
    "DTG": 5,  # High genetic barrier to resistance
    "BIC": 5,  # High genetic barrier to resistance
    "TDF": 4,  # Commonly used in first-line regimens
    "FTC": 4,  # Commonly used in first-line regimens
    "3TC": 4,  # Commonly used in first-line regimens
    "TAF": 4,  # Newer, less toxic form of tenofovir
    "LEN": 4,  # New long-acting capsid inhibitor
}

# Color mapping for resistance levels (subtle professional colors)
RESISTANCE_COLORS = {
    "Susceptible": "#eaf5ea",  # Very subtle green
    "Potential Low-Level": "#e6f2f7",  # Very subtle blue
    "Low-Level": "#faf0e1",  # Very subtle orange
    "Intermediate": "#f9ece0",  # Very subtle darker orange
    "High-Level": "#f5e9e9",  # Very subtle red
}

# Color mapping for mutation types (subtle professional colors)
MUTATION_TYPE_COLORS = {
    "Major": "#f8e6e6",  # Very subtle light red for major mutations
    "Accessory": "#fafaeb",  # Very subtle light yellow for accessory mutations
    "Other": "#f8f9fa",  # Light gray for other mutations
}

# ===== MUTATION-BASED VISUALIZATIONS =====


def create_mutation_details_table(data, sample_id, output_dir):
    """
    Creates a comprehensive table of all detected mutations with their properties.

    This visualization includes mutation positions, types, SDRM status, and other
    properties in a filterable table format. Supports all gene types including
    future additions like Capsid (CA).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
    """
    # Organize mutations by gene
    gene_mutations = defaultdict(dict)
    created_files = {}

    # Process all aligned gene sequences
    for gene_seq in data.get("alignedGeneSequences", []):
        if not gene_seq or not gene_seq.get("gene"):
            continue

        gene_name = gene_seq["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            logger.warning(f"Skipping gene sequence with unknown gene name")
            continue

        # Get SDRMs (Surveillance Drug Resistance Mutations)
        sdrm_list = (
            [m["text"] for m in gene_seq.get("SDRMs", [])]
            if gene_seq.get("SDRMs")
            else []
        )

        # Process all mutations
        for mutation in gene_seq.get("mutations", []):
            if not mutation:
                continue

            mutation_text = mutation.get("text", "")
            mutation_type = mutation.get("primaryType", "Unknown")
            position = mutation.get("position", "")
            is_sdrm = mutation_text in sdrm_list
            is_apobec = mutation.get("isApobecMutation", False)
            is_unusual = mutation.get("isUnusual", False)
            is_insertion = mutation.get("isInsertion", False)
            is_deletion = mutation.get("isDeletion", False)

            # Create unique row ID
            row_id = f"{sample_id}_{mutation_text}"

            # Store mutation data with enhanced properties
            gene_mutations[gene_name][row_id] = {
                "Mutation": mutation_text,
                "Position": position,
                "Type": mutation_type,
                "Is SDRM": "Yes" if is_sdrm else "No",
                "Is APOBEC": "Yes" if is_apobec else "No",
                "Is Unusual": "Yes" if is_unusual else "No",
                "Structure": (
                    "Insertion"
                    if is_insertion
                    else "Deletion" if is_deletion else "Substitution"
                ),
            }

    # Create consolidated table for each gene
    for gene_name, mutations in gene_mutations.items():
        if not mutations:
            logger.info(
                f"No mutations found for {gene_name} gene, skipping visualization"
            )
            continue

        # Calculate min and max positions for proper scaling based on actual data
        positions = [
            val["Position"]
            for val in mutations.values()
            if isinstance(val["Position"], (int, float))
        ]
        min_position = min(positions) if positions else 1
        max_position = (
            max(positions) if positions else GENE_TYPICAL_LENGTHS.get(gene_name, 300)
        )

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
                # Enable conditional formatting with subtle styling
                # Configure a reasonable max number of columns
            },
            "headers": {
                "Mutation": {
                    "title": "Mutation",
                    "description": "Mutation code",
                    "namespace": "Mutation Details",
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
                },
                "Type": {
                    "title": "Type",
                    "description": "Mutation type (Major, Accessory, or Other)",
                    "namespace": "Mutation Details",
                    # Use subtle background colors for different mutation types
                    "bgcols": MUTATION_TYPE_COLORS,
                },
                "Is SDRM": {
                    "title": "SDRM",
                    "description": "Surveillance Drug Resistance Mutation",
                    "namespace": "Mutation Details",
                    # Subtle highlighting for SDRMs
                    "bgcols": {"Yes": "#f5f9f5", "No": ""},  # Very subtle green
                },
                "Is APOBEC": {
                    "title": "APOBEC",
                    "description": "APOBEC-mediated G-to-A hypermutation",
                    "namespace": "Mutation Details",
                    "bgcols": {"Yes": "#f9f5fc", "No": ""},  # Very subtle purple
                },
                "Is Unusual": {
                    "title": "Unusual",
                    "description": "Mutation that is rarely observed in untreated patients",
                    "namespace": "Mutation Details",
                    "bgcols": {"Yes": "#f9f7f7", "No": ""},  # Very subtle pink
                },
                "Structure": {
                    "title": "Structure",
                    "description": "Type of structural change (substitution, insertion, deletion)",
                    "namespace": "Mutation Details",
                    "bgcols": {
                        "Insertion": "#e6f7f5",  # Very subtle teal
                        "Deletion": "#f7e6f5",  # Very subtle purple
                        "Substitution": "",  # No background
                    },
                },
            },
            "data": mutations,
        }

        # Write the consolidated table to file
        output_file = os.path.join(
            output_dir, f"mutation_details_{gene_name.lower()}_mqc.json"
        )
        try:
            with open(output_file, "w") as f:
                json.dump(table_output, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created mutation details table for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating mutation details table for {gene_name}: {str(e)}"
            )

    return created_files


def create_mutation_position_visualization(data, sample_id, output_dir):
    """
    Creates an interactive visualization of mutations along the gene sequence.

    This HTML-based visualization shows the position of mutations along the gene,
    color-coded by type with interactive tooltips showing details. The visualization
    adapts to the actual gene length for accurate representation.

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
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
            "last_aa": 1,  # Will be updated with actual data
            "mutation_details": defaultdict(list),
        }
    )

    created_files = {}

    for gene_seq in data.get("alignedGeneSequences", []):
        if not gene_seq or not gene_seq.get("gene"):
            continue

        gene_name = gene_seq["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        # Use actual sequence range if available, otherwise use typical length
        first_aa = gene_seq.get("firstAA", 1)
        last_aa = gene_seq.get("lastAA", GENE_TYPICAL_LENGTHS.get(gene_name, 300))

        gene_mutations[gene_name]["first_aa"] = first_aa
        gene_mutations[gene_name]["last_aa"] = last_aa

        # Get SDRMs
        sdrm_texts = (
            [sdrm.get("text", "") for sdrm in gene_seq.get("SDRMs", [])]
            if gene_seq.get("SDRMs")
            else []
        )

        for mutation in gene_seq.get("mutations", []):
            if not mutation:
                continue

            position = mutation.get("position")
            if position:
                mutation_text = mutation.get("text", "")
                mutation_type = mutation.get("primaryType", "Other")
                is_apobec = mutation.get("isApobecMutation", False)
                is_sdrm = mutation_text in sdrm_texts
                consensus = mutation.get("consensus", "")
                aas = mutation.get("AAs", "")

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
                        "consensus": consensus,
                        "aas": aas,
                    }
                )

    # Create visualization for each gene
    for gene_name, mutation_data in gene_mutations.items():
        if not mutation_data["positions"]:
            logger.info(
                f"No mutations found for {gene_name} gene, skipping position visualization"
            )
            continue

        # Create HTML visualization
        html_content = create_html_header(
            f"mutation_position_map_{gene_name.lower()}",
            f"{gene_name} Mutation Position Map",
            f"Interactive visualization of mutations along the {gene_name} gene sequence, highlighting positions of major, accessory, and other mutations with surveillance drug resistance mutations (SDRMs) and APOBEC-mediated mutations specially marked.",
        )

        html_content += f"<h3>{gene_name} Mutation Position Map</h3>\n"

        # Brief introduction with enhanced information
        total_mutations = len(mutation_data["positions"])
        total_major = len(mutation_data["major_positions"])
        total_sdrm = len(mutation_data["sdrm_positions"])

        html_content += f"<p>This visualization shows {total_mutations} mutations detected in the {gene_name} gene "
        html_content += (
            f"(positions {mutation_data['first_aa']}-{mutation_data['last_aa']}), "
        )
        html_content += f"including {total_major} major resistance mutations"

        if total_sdrm > 0:
            html_content += (
                f" and {total_sdrm} surveillance drug resistance mutations (SDRMs)"
            )

        html_content += f". Hover over colored positions for details.</p>\n"

        # Add visual division for long genes
        gene_length = mutation_data["last_aa"] - mutation_data["first_aa"] + 1
        use_divisions = gene_length > 200
        division_size = 100 if use_divisions else gene_length

        # Create a professional position map with subtle styling
        html_content += "<style>\n"
        # Position map styling - using professional, subtle styling
        html_content += ".position-map { display: flex; flex-wrap: wrap; margin: 20px 0; background-color: #f9f9f9; padding: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }\n"
        html_content += ".position-row { display: flex; flex-wrap: wrap; width: 100%; margin-bottom: 10px; }\n"
        html_content += ".position-label { width: 50px; text-align: right; font-size: 12px; color: #666; margin-right: 10px; padding-top: 5px; }\n"
        html_content += ".position-cells { display: flex; flex-wrap: wrap; flex: 1; }\n"
        html_content += ".position-cell { width: 22px; height: 22px; margin: 1px; text-align: center; font-size: 10px; line-height: 22px; background-color: #f2f2f2; position: relative; border-radius: 2px; user-select: none; }\n"
        # Using more professional, less saturated colors
        html_content += ".position-major { background-color: #e57373; color: white; }\n"
        html_content += (
            ".position-accessory { background-color: #ffb74d; color: white; }\n"
        )
        html_content += ".position-other { background-color: #64b5f6; color: white; }\n"
        html_content += ".position-sdrm { border: 2px solid #81c784; }\n"
        html_content += ".position-apobec { border: 2px dashed #9575cd; }\n"

        # Tooltip styling - more professional look
        html_content += ".position-tooltip { display: none; position: absolute; background-color: #424242; color: white; padding: 10px; border-radius: 4px; font-size: 12px; z-index: 100; min-width: 200px; max-width: 250px; top: -5px; left: 100%; transform: translateY(-50%); text-align: left; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }\n"
        html_content += ".position-cell:hover .position-tooltip { display: block; }\n"
        html_content += ".position-tooltip ul { margin: 0; padding-left: 15px; }\n"
        html_content += ".position-tooltip li { margin: 5px 0; }\n"
        html_content += ".position-tooltip .mutation-details { font-size: 11px; color: #ccc; margin-top: 2px; }\n"

        # Legend and summary styling
        html_content += ".position-legend { margin: 20px 0; background-color: #f9f9f9; padding: 15px; border-radius: 5px; display: flex; flex-wrap: wrap; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }\n"
        html_content += ".legend-item { margin-right: 25px; margin-bottom: 10px; display: flex; align-items: center; font-size: 13px; }\n"
        html_content += ".legend-box { width: 15px; height: 15px; margin-right: 8px; border-radius: 2px; }\n"
        html_content += "</style>\n"

        # Position map with organized rows for better visualization
        html_content += "<div class='position-map'>\n"

        first_pos = mutation_data["first_aa"]
        last_pos = mutation_data["last_aa"]

        if use_divisions:
            # Create rows of positions for better visualization of long genes
            for start_pos in range(first_pos, last_pos + 1, division_size):
                end_pos = min(start_pos + division_size - 1, last_pos)

                html_content += "<div class='position-row'>\n"
                html_content += (
                    f"<div class='position-label'>{start_pos}-{end_pos}</div>\n"
                )
                html_content += "<div class='position-cells'>\n"

                for pos in range(start_pos, end_pos + 1):
                    # FIX: Capture the returned HTML content
                    html_content = _add_position_cell(html_content, pos, mutation_data)

                html_content += "</div>\n"  # End position-cells
                html_content += "</div>\n"  # End position-row
        else:
            # For shorter genes, use single row
            html_content += "<div class='position-row'>\n"
            html_content += (
                f"<div class='position-label'>{first_pos}-{last_pos}</div>\n"
            )
            html_content += "<div class='position-cells'>\n"

            for pos in range(first_pos, last_pos + 1):
                # FIX: Capture the returned HTML content
                html_content = _add_position_cell(html_content, pos, mutation_data)

            html_content += "</div>\n"  # End position-cells
            html_content += "</div>\n"  # End position-row

        html_content += "</div>\n"  # End position-map

        # Add enhanced legend with better descriptions
        html_content += "<div class='position-legend'>\n"
        html_content += "  <div class='legend-item'><div class='legend-box position-major'></div> Major Mutation (Directly confers resistance)</div>\n"
        html_content += "  <div class='legend-item'><div class='legend-box position-accessory'></div> Accessory Mutation (Enhances resistance)</div>\n"
        html_content += "  <div class='legend-item'><div class='legend-box position-other'></div> Other Mutation (Polymorphism or unknown effect)</div>\n"
        html_content += "  <div class='legend-item'><div class='legend-box position-sdrm' style='background-color: white;'></div> Surveillance Drug Resistance Mutation (SDRM)</div>\n"
        html_content += "  <div class='legend-item'><div class='legend-box position-apobec' style='background-color: white;'></div> APOBEC-mediated mutation</div>\n"
        html_content += "</div>\n"

        # Add summary of mutation distribution if there are mutations
        if mutation_data["positions"]:
            html_content += "<div class='mutation-summary' style='background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px;'>\n"
            html_content += (
                "<h4 style='margin-top: 0;'>Mutation Distribution Summary</h4>\n"
            )
            html_content += "<table style='width: 100%; border-collapse: collapse;'>\n"
            html_content += "<tr style='border-bottom: 1px solid #ddd;'><th style='text-align: left; padding: 8px; width: 50%;'>Mutation Type</th><th style='text-align: right; padding: 8px;'>Count</th><th style='text-align: right; padding: 8px;'>Percentage</th></tr>\n"

            total_mutations = len(set(mutation_data["positions"]))

            # Major mutations
            major_count = len(set(mutation_data["major_positions"]))
            major_pct = (
                (major_count / total_mutations * 100) if total_mutations > 0 else 0
            )
            html_content += f"<tr style='border-bottom: 1px solid #ddd;'><td style='padding: 8px;'>Major Mutations</td><td style='text-align: right; padding: 8px;'>{major_count}</td><td style='text-align: right; padding: 8px;'>{major_pct:.1f}%</td></tr>\n"

            # Accessory mutations
            accessory_count = len(set(mutation_data["accessory_positions"]))
            accessory_pct = (
                (accessory_count / total_mutations * 100) if total_mutations > 0 else 0
            )
            html_content += f"<tr style='border-bottom: 1px solid #ddd;'><td style='padding: 8px;'>Accessory Mutations</td><td style='text-align: right; padding: 8px;'>{accessory_count}</td><td style='text-align: right; padding: 8px;'>{accessory_pct:.1f}%</td></tr>\n"

            # Other mutations
            other_count = len(set(mutation_data["other_positions"]))
            other_pct = (
                (other_count / total_mutations * 100) if total_mutations > 0 else 0
            )
            html_content += f"<tr style='border-bottom: 1px solid #ddd;'><td style='padding: 8px;'>Other Mutations</td><td style='text-align: right; padding: 8px;'>{other_count}</td><td style='text-align: right; padding: 8px;'>{other_pct:.1f}%</td></tr>\n"

            # Special categories
            sdrm_count = len(set(mutation_data["sdrm_positions"]))
            if sdrm_count > 0:
                sdrm_pct = (
                    (sdrm_count / total_mutations * 100) if total_mutations > 0 else 0
                )
                html_content += f"<tr style='border-bottom: 1px solid #ddd;'><td style='padding: 8px;'>SDRM Mutations</td><td style='text-align: right; padding: 8px;'>{sdrm_count}</td><td style='text-align: right; padding: 8px;'>{sdrm_pct:.1f}%</td></tr>\n"

            apobec_count = len(set(mutation_data["apobec_positions"]))
            if apobec_count > 0:
                apobec_pct = (
                    (apobec_count / total_mutations * 100) if total_mutations > 0 else 0
                )
                html_content += f"<tr style='border-bottom: 1px solid #ddd;'><td style='padding: 8px;'>APOBEC-Mediated Mutations</td><td style='text-align: right; padding: 8px;'>{apobec_count}</td><td style='text-align: right; padding: 8px;'>{apobec_pct:.1f}%</td></tr>\n"

            # Total row
            html_content += f"<tr style='font-weight: bold;'><td style='padding: 8px;'>Total Mutations</td><td style='text-align: right; padding: 8px;'>{total_mutations}</td><td style='text-align: right; padding: 8px;'>100.0%</td></tr>\n"

            html_content += "</table>\n"
            html_content += "</div>\n"

        html_content += create_html_footer()

        # Write the HTML position map to file
        output_file = os.path.join(
            output_dir, f"mutation_position_map_{gene_name.lower()}_mqc.html"
        )
        try:
            with open(output_file, "w") as f:
                f.write(html_content)
            created_files[gene_name] = output_file
            logger.info(
                f"Created mutation position map for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating mutation position map for {gene_name}: {str(e)}"
            )

    return created_files


def _add_position_cell(html_content, pos, mutation_data):
    """
    Helper function to add a position cell to the HTML content.

    Args:
        html_content (str): The HTML content string to append to
        pos (int): Position number
        mutation_data (dict): Mutation data for the current gene

    Returns:
        str: The updated HTML content string
    """
    cell_class = "position-cell"

    # Determine cell class based on mutation type
    if pos in mutation_data["major_positions"]:
        cell_class += " position-major"
    elif pos in mutation_data["accessory_positions"]:
        cell_class += " position-accessory"
    elif pos in mutation_data["other_positions"]:
        cell_class += " position-other"
    else:
        # No mutation at this position, just the base cell style
        pass

    # Add SDRM and APOBEC indicators if this position has those special types
    if pos in mutation_data["sdrm_positions"]:
        cell_class += " position-sdrm"

    if pos in mutation_data["apobec_positions"]:
        cell_class += " position-apobec"

    # Only show position number for positions divisible by 10 or positions with mutations
    display_pos = (
        str(pos) if pos % 10 == 0 or pos in mutation_data["positions"] else "&nbsp;"
    )

    # Create tooltip content with detailed mutation information if applicable
    tooltip_html = ""
    if pos in mutation_data["mutation_details"]:
        tooltip_html = f"<span class='position-tooltip'><strong>Position {pos}</strong>"
        tooltip_html += "<ul>"

        for mutation in mutation_data["mutation_details"][pos]:
            mutation_text = mutation["text"]
            mutation_type = mutation["type"]
            tags = []

            if mutation.get("is_sdrm", False):
                tags.append("SDRM")
            if mutation.get("is_apobec", False):
                tags.append("APOBEC")

            tag_text = f" ({', '.join(tags)})" if tags else ""

            # Add mutation details including original and mutated amino acids
            consensus = mutation.get("consensus", "")
            aas = mutation.get("aas", "")
            mutation_details = ""
            if consensus and aas:
                mutation_details = f"<div class='mutation-details'>Changed from {consensus} to {aas}</div>"

            tooltip_html += f"<li><strong>{mutation_text}</strong> - {mutation_type}{tag_text}{mutation_details}</li>"

        tooltip_html += "</ul></span>"

    # Construct the full cell HTML and append it to the existing content
    cell_html = f"<div class='{cell_class}' title='Position {pos}'>{display_pos}{tooltip_html}</div>\n"

    return html_content + cell_html


def create_mutation_type_summary(data, sample_id, output_dir):
    """
    Creates a summary table showing distribution of mutation types.

    This visualization includes counts and percentages of major, accessory,
    and other mutations, with representative examples. Supports all gene types
    including future additions like Capsid (CA).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
    """
    # Organize mutations by gene and type
    gene_mutations = defaultdict(
        lambda: {
            "major_mutations": [],
            "accessory_mutations": [],
            "other_mutations": [],
            "sdrm_mutations": [],
            "apobec_mutations": [],
            "unusual_mutations": [],
            "total_mutations": 0,
            "positions": [],
        }
    )

    created_files = {}

    for gene_seq in data.get("alignedGeneSequences", []):
        if not gene_seq or not gene_seq.get("gene"):
            continue

        gene_name = gene_seq["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        # Get SDRMs
        sdrm_texts = (
            [sdrm.get("text", "") for sdrm in gene_seq.get("SDRMs", [])]
            if gene_seq.get("SDRMs")
            else []
        )

        for mutation in gene_seq.get("mutations", []):
            if not mutation:
                continue

            position = mutation.get("position")
            if position:
                mutation_text = mutation.get("text", "")
                mutation_type = mutation.get("primaryType", "Other")
                is_apobec = mutation.get("isApobecMutation", False)
                is_sdrm = mutation_text in sdrm_texts
                is_unusual = mutation.get("isUnusual", False)

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

                if is_unusual:
                    gene_mutations[gene_name]["unusual_mutations"].append(mutation_text)

    # Process each gene
    for gene_name, mutation_data in gene_mutations.items():
        if not mutation_data["positions"]:
            logger.info(
                f"No mutations found for {gene_name} gene, skipping mutation type summary"
            )
            continue

        # Update total mutations count
        total_positions = len(mutation_data["positions"])
        mutation_data["total_mutations"] = total_positions

        # Create a MultiQC-native table for mutation summary
        mutation_table_data = {}

        # Prepare table data for Major mutations
        major_count = len(set(mutation_data["major_mutations"]))
        if major_count > 0:
            percentage = (
                (major_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["Major"] = {
                "Count": major_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(sorted(set(mutation_data["major_mutations"]))),
                "Clinical Implication": "Direct resistance to one or more drugs",
            }

        # Prepare table data for Accessory mutations
        accessory_count = len(set(mutation_data["accessory_mutations"]))
        if accessory_count > 0:
            percentage = (
                (accessory_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["Accessory"] = {
                "Count": accessory_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(
                    sorted(set(mutation_data["accessory_mutations"]))
                ),
                "Clinical Implication": "Enhance resistance when present with major mutations",
            }

        # Prepare table data for SDRM mutations
        sdrm_count = len(set(mutation_data["sdrm_mutations"]))
        if sdrm_count > 0:
            percentage = (
                (sdrm_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["SDRM"] = {
                "Count": sdrm_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(sorted(set(mutation_data["sdrm_mutations"]))),
                "Clinical Implication": "Used for surveillance of transmitted resistance",
            }

        # Prepare table data for APOBEC mutations
        apobec_count = len(set(mutation_data["apobec_mutations"]))
        if apobec_count > 0:
            percentage = (
                (apobec_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["APOBEC"] = {
                "Count": apobec_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(sorted(set(mutation_data["apobec_mutations"]))),
                "Clinical Implication": "Artifacts of APOBEC-mediated hypermutation",
            }

        # Prepare table data for Unusual mutations
        unusual_count = len(set(mutation_data["unusual_mutations"]))
        if unusual_count > 0:
            percentage = (
                (unusual_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["Unusual"] = {
                "Count": unusual_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(sorted(set(mutation_data["unusual_mutations"]))),
                "Clinical Implication": "Rarely observed in untreated patients",
            }

        # Prepare table data for Other mutations
        other_count = len(set(mutation_data["other_mutations"]))
        if other_count > 0:
            percentage = (
                (other_count / total_positions * 100) if total_positions > 0 else 0
            )
            mutation_table_data["Other"] = {
                "Count": other_count,
                "Percentage": round(percentage, 1),
                "Examples": ", ".join(sorted(set(mutation_data["other_mutations"]))),
                "Clinical Implication": "Polymorphisms or mutations with minimal impact on drug resistance",
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
                },
                "Percentage": {
                    "title": "Percentage",
                    "description": "Percentage of all mutations",
                    "suffix": "%",
                    "format": "{:,.1f}",
                    "scale": "Blues",
                    "min": 0,
                    "max": 100,
                },
                "Examples": {
                    "title": "Mutations",
                    "description": "Complete list of mutations of this type",
                    "scale": False,
                },
                "Clinical Implication": {
                    "title": "Clinical Implication",
                    "description": "Typical impact on drug resistance",
                    "scale": False,
                },
            },
            "data": mutation_table_data,
        }

        # Write the mutation summary table to file
        output_file = os.path.join(
            output_dir, f"mutation_summary_{gene_name.lower()}_mqc.json"
        )
        try:
            with open(output_file, "w") as f:
                json.dump(mutation_summary_table, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created mutation type summary for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating mutation type summary for {gene_name}: {str(e)}"
            )

    return created_files


# ===== RESISTANCE-BASED VISUALIZATIONS =====


def create_drug_resistance_profile(data, sample_id, output_dir):
    """
    Creates a comprehensive table of drug resistance scores and interpretations.

    This visualization includes drugs, their classes, resistance scores and levels
    with clinical interpretations in a filterable, sortable table. Supports all
    drug classes including future additions like CAI (Capsid Inhibitors).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
    """
    # Organize data by gene
    gene_drug_data = defaultdict(dict)
    created_files = {}

    # Process all drug resistance data
    for dr_entry in data.get("drugResistance", []):
        if not dr_entry or not dr_entry.get("gene"):
            continue

        gene_name = dr_entry["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        for drug_score in dr_entry.get("drugScores", []):
            if not drug_score:
                continue

            drug_name = drug_score["drug"].get("displayAbbr", "Unknown")
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            resistance_level = drug_score.get("text", "Unknown")
            score = drug_score.get("score", 0)
            level = drug_score.get("level", 0)

            # Map SIR classification (Susceptible, Intermediate, Resistant)
            sir_classification = "S"  # Default to Susceptible
            if level >= 5:
                sir_classification = "R"  # High-Level Resistance = Resistant
            elif level >= 3:
                sir_classification = "I"  # Low-Level/Intermediate = Intermediate

            # Clinical priority based on drug importance
            clinical_priority = HIGH_PRIORITY_DRUGS.get(drug_name, 3)

            # Calculate a weighted score that considers drug importance
            weighted_score = score * (clinical_priority / 3.0)

            # Create unique row ID using safe name transformations
            safe_drug_name = (
                drug_name.replace("/", "_").replace(" ", "_").replace("-", "_")
            )
            row_id = f"{sample_id}_{safe_drug_name}"

            gene_drug_data[gene_name][row_id] = {
                "Drug": drug_name,
                "Drug Class": drug_class,
                "Score": score,
                "Level": level,
                "Weighted Score": round(weighted_score, 1),
                "Clinical Priority": clinical_priority,
                "Resistance Level": resistance_level,
                "SIR": sir_classification,
            }

    # Create a single table for each gene
    for gene_name, drugs_data in gene_drug_data.items():
        if not drugs_data:
            logger.info(
                f"No drug resistance data found for {gene_name} gene, skipping resistance profile"
            )
            continue

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
                    {"column": "Clinical Priority", "direction": "desc"},
                    {"column": "Drug Class", "direction": "asc"},
                ],
                # Enable filtering for research flexibility
                # Enable conditional formatting but with more subtle styling
                # Configure a reasonable max for columns
            },
            "headers": {
                "Drug": {
                    "title": "Drug",
                    "description": "Antiretroviral drug",
                    "namespace": "Drug Information",
                },
                "Drug Class": {
                    "title": "Class",
                    "description": "Drug class (e.g., NRTI, NNRTI, PI, INSTI, CAI)",
                    "namespace": "Drug Information",
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
                    "bars_zero_centrepoint": False,
                },
                "Weighted Score": {
                    "title": "Weighted Score",
                    "description": "Score adjusted for drug importance in current treatment paradigms",
                    "namespace": "Resistance Metrics",
                    "min": 0,
                    "max": 100,
                    "scale": "RdYlGn-rev",
                    "format": "{:,.1f}",
                    "hidden": True,  # Hidden by default but available for sorting
                },
                "Clinical Priority": {
                    "title": "Priority",
                    "description": "Clinical importance rating (1-5, with 5 being highest)",
                    "namespace": "Drug Information",
                    "format": "{:,.0f}",
                    "scale": "Greens",
                    "min": 1,
                    "max": 5,
                    "hidden": True,  # Hidden by default but available for sorting
                },
                "SIR": {
                    "title": "SIR",
                    "description": "Susceptible (S), Intermediate (I), or Resistant (R) classification",
                    "namespace": "Resistance Metrics",
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
                    # Very subtle background colors based on resistance level
                    "bgcols": RESISTANCE_COLORS,
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
        try:
            with open(output_file, "w") as f:
                json.dump(table_data, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created drug resistance profile for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating drug resistance profile for {gene_name}: {str(e)}"
            )

    return created_files


def create_drug_class_resistance_summary(data, sample_id, output_dir):
    """
    Creates a summary table and visualization of resistance by drug class.

    This visualization shows resistance patterns across drug classes,
    with counts and percentages of resistant drugs. Supports all drug classes
    including future additions like CAI (Capsid Inhibitors).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
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
                "priority_drugs_affected": 0,  # Track high-priority drugs affected
                "weighted_score_sum": 0,  # Sum of weighted scores
                "drugs": [],
            }
        )
    )

    created_files = {}

    # Process all drug resistance data
    for dr_entry in data.get("drugResistance", []):
        if not dr_entry or not dr_entry.get("gene"):
            continue

        gene_name = dr_entry["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        for drug_score in dr_entry.get("drugScores", []):
            if not drug_score:
                continue

            drug_name = drug_score["drug"].get("displayAbbr", "Unknown")
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            score = drug_score.get("score", 0)
            level = drug_score.get("level", 0)

            # Get drug clinical priority
            clinical_priority = HIGH_PRIORITY_DRUGS.get(drug_name, 3)

            # Calculate weighted score
            weighted_score = score * (clinical_priority / 3.0)

            # Update counts
            overview = gene_class_overview[gene_name][drug_class]
            overview["total_drugs"] += 1
            overview["weighted_score_sum"] += weighted_score

            # Track if high priority drug is affected (priority 4-5 and score ≥ 15)
            if clinical_priority >= 4 and score >= 15:
                overview["priority_drugs_affected"] += 1

            overview["drugs"].append(
                {
                    "name": drug_name,
                    "score": score,
                    "level": level,
                    "priority": clinical_priority,
                    "weighted_score": weighted_score,
                }
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
        if not class_overview:
            logger.info(
                f"No drug class data found for {gene_name} gene, skipping drug class summary"
            )
            continue

        # Create MultiQC-native table for drug class overview
        table_data = {}

        # Calculate total drugs and resistant percentage across all classes
        total_drugs = sum(cls["total_drugs"] for cls in class_overview.values())
        total_resistant = sum(cls["resistant_drugs"] for cls in class_overview.values())
        total_priority_affected = sum(
            cls["priority_drugs_affected"] for cls in class_overview.values()
        )
        overall_resistant_percent = (
            (total_resistant / total_drugs * 100) if total_drugs > 0 else 0
        )

        # Add a row for each drug class
        for drug_class, overview in sorted(class_overview.items()):
            if overview["total_drugs"] == 0:
                continue

            resistant_percent = (
                (overview["resistant_drugs"] / overview["total_drugs"] * 100)
                if overview["total_drugs"] > 0
                else 0
            )

            # Calculate average weighted score
            avg_weighted_score = (
                overview["weighted_score_sum"] / overview["total_drugs"]
                if overview["total_drugs"] > 0
                else 0
            )

            # Create a row ID for the drug class
            row_id = f"{gene_name}_{drug_class.replace(' ', '_')}"

            # Determine resistance status based on percentage and clinical impact
            resistance_status = "No significant resistance"
            if resistant_percent >= 66 or overview["high_resistance"] > 0:
                resistance_status = "High-level resistance"
            elif resistant_percent >= 33 or overview["intermediate"] > 0:
                resistance_status = "Moderate resistance"
            elif resistant_percent > 0 or overview["low_resistance"] > 0:
                resistance_status = "Low-level resistance"

            # Enhance status if high-priority drugs are affected
            if (
                overview["priority_drugs_affected"] > 0
                and resistance_status == "Low-level resistance"
            ):
                resistance_status = "Moderate resistance (priority drugs affected)"
            elif (
                overview["priority_drugs_affected"] > 0
                and resistance_status == "Moderate resistance"
            ):
                resistance_status = "High-level resistance (priority drugs affected)"

            # Store the data with enhanced metrics
            table_data[row_id] = {
                "Drug Class": drug_class,
                "Total Drugs": overview["total_drugs"],
                "Resistant Drugs": overview["resistant_drugs"],
                "Resistant (%)": round(resistant_percent, 1),
                "Avg Weighted Score": round(avg_weighted_score, 1),
                "Priority Drugs Affected": overview["priority_drugs_affected"],
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
            "description": f"Summary of drug resistance patterns by drug class for {gene_name}. This table shows the proportion of drugs in each class with resistance, categorized by resistance level. Overall resistance: {round(overall_resistant_percent, 1)}% of drugs show resistance, with {total_priority_affected} high-priority drugs affected.",
            "plot_type": "table",
            "pconfig": {
                "id": f"drug_class_overview_{gene_name.lower()}_table_config",
                "title": f"{gene_name} Drug Class Resistance Summary",
                "namespace": "Resistance Analysis",
                "save_file": True,
                "col1_header": "Drug Class",
                "sort_rows": True,
                # Default sorting by resistant percentage (high to low)
                "defaultsort": [
                    {"column": "Resistant (%)", "direction": "desc"},
                    {"column": "Priority Drugs Affected", "direction": "desc"},
                ],
                # Enable filtering
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
                },
                "Avg Weighted Score": {
                    "title": "Weighted Score",
                    "description": "Average resistance score weighted by drug importance",
                    "namespace": "Classes",
                    "format": "{:,.1f}",
                    "scale": "RdYlGn-rev",
                    "min": 0,
                    "max": 60,
                },
                "Priority Drugs Affected": {
                    "title": "High-Priority",
                    "description": "Number of high-priority drugs affected by resistance",
                    "namespace": "Classes",
                    "format": "{:,.0f}",
                    "scale": "Reds",
                    "min": 0,
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
                    "bgcols": {
                        "High-level resistance": "#f5e6e6",  # Very subtle red
                        "High-level resistance (priority drugs affected)": "#f5e6e6",  # Same subtle red
                        "Moderate resistance": "#faf0e1",  # Very subtle orange
                        "Moderate resistance (priority drugs affected)": "#faf0e1",  # Same subtle orange
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
                },
                "Intermediate": {
                    "title": "Int",
                    "description": "Number of drugs with intermediate resistance",
                    "namespace": "Resistance Levels",
                    "format": "{:,.0f}",
                    "scale": "Oranges",
                    "min": 0,
                },
                "Low-Level": {
                    "title": "Low",
                    "description": "Number of drugs with low-level resistance",
                    "namespace": "Resistance Levels",
                    "format": "{:,.0f}",
                    "scale": "YlOrBr",
                    "min": 0,
                },
                "Potential Low": {
                    "title": "Pot",
                    "description": "Number of drugs with potential low-level resistance",
                    "namespace": "Resistance Levels",
                    "format": "{:,.0f}",
                    "scale": "Blues",
                    "min": 0,
                },
                "Susceptible": {
                    "title": "Sus",
                    "description": "Number of drugs that are susceptible",
                    "namespace": "Resistance Levels",
                    "format": "{:,.0f}",
                    "scale": "Greens",
                    "min": 0,
                },
            },
            "data": table_data,
        }

        # Write the class overview table to file
        output_file = os.path.join(
            output_dir, f"drug_class_overview_{gene_name.lower()}_table_mqc.json"
        )
        try:
            with open(output_file, "w") as f:
                json.dump(summary_table, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created drug class overview for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating drug class overview for {gene_name}: {str(e)}"
            )

    return created_files


# ===== MUTATION-RESISTANCE IMPACT VISUALIZATIONS =====


def create_mutation_resistance_contribution(data, sample_id, output_dir):
    """
    Creates a table showing how specific mutations contribute to resistance scores.

    This visualization details the impact of individual mutations or mutation
    patterns on drug resistance, with contribution scores and percentages.
    Supports all gene types including future additions like Capsid (CA).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
    """
    # Organize data by gene
    gene_mutation_contribution = defaultdict(lambda: defaultdict(dict))
    created_files = {}

    # Process all drug resistance data
    for dr_entry in data.get("drugResistance", []):
        if not dr_entry or not dr_entry.get("gene"):
            continue

        gene_name = dr_entry["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        for drug_score in dr_entry.get("drugScores", []):
            # Only include drugs with significant resistance (score ≥ 15)
            if not drug_score or drug_score.get("score", 0) < 15:
                continue

            drug_name = drug_score["drug"].get("displayAbbr", "Unknown")
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            total_score = drug_score.get("score", 0)

            # Get drug clinical priority
            clinical_priority = HIGH_PRIORITY_DRUGS.get(drug_name, 3)

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
                has_clinical_comments = False
                clinical_comment = ""

                for mutation in partial.get("mutations", []):
                    if not mutation:
                        continue

                    mutation_text = mutation.get("text", "")
                    mutation_texts.append(mutation_text)
                    mutation_types.append(mutation.get("primaryType", "Other"))

                    # Check if this is a SDRM
                    if mutation.get("isSDRM", False):
                        is_sdrm = True

                    # Get clinical comments if available
                    if mutation.get("comments") and len(mutation["comments"]) > 0:
                        for comment in mutation["comments"]:
                            if comment.get("text"):
                                has_clinical_comments = True
                                clinical_comment = comment["text"]
                                break

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

                    # Calculate weighted contribution based on drug importance
                    weighted_contribution = score * (clinical_priority / 3.0)

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

                    # Enhance significance for high-priority drugs
                    if clinical_priority >= 4 and significance in [
                        "Significant",
                        "Minor",
                    ]:
                        significance = f"{significance} (High-Priority Drug)"

                    # Store the data with additional fields
                    gene_mutation_contribution[gene_name][row_id] = {
                        "Drug": drug_name,
                        "Drug Class": drug_class,
                        "Drug Priority": clinical_priority,
                        "Mutations": mutation_key,
                        "Mutation Type": primary_type,
                        "Is SDRM": "Yes" if is_sdrm else "No",
                        "Score": score,
                        "Total Score": total_score,
                        "Weighted Contribution": round(weighted_contribution, 1),
                        "Contribution (%)": round(contribution, 1),
                        "Impact": significance,
                        "Clinical Comment": (
                            clinical_comment if has_clinical_comments else ""
                        ),
                    }

    # Create a table for each gene
    for gene_name, contribution_data in gene_mutation_contribution.items():
        if not contribution_data:
            logger.info(
                f"No mutation contribution data found for {gene_name} gene, skipping contribution visualization"
            )
            continue

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
                # Default sorting by weighted contribution (highest first)
                "defaultsort": [
                    {"column": "Weighted Contribution", "direction": "desc"}
                ],
            },
            "headers": {
                "Drug": {
                    "title": "Drug",
                    "description": "Antiretroviral drug",
                    "namespace": "Drug Information",
                },
                "Drug Class": {
                    "title": "Class",
                    "description": "Drug class category",
                    "namespace": "Drug Information",
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
                "Drug Priority": {
                    "title": "Drug Priority",
                    "description": "Clinical importance rating (1-5, with 5 being highest)",
                    "namespace": "Drug Information",
                    "format": "{:,.0f}",
                    "scale": "Greens",
                    "min": 1,
                    "max": 5,
                    "hidden": True,  # Hidden by default
                },
                "Mutations": {
                    "title": "Mutations",
                    "description": "Specific mutation or combination of mutations",
                    "namespace": "Mutation Details",
                },
                "Mutation Type": {
                    "title": "Type",
                    "description": "Primary type of mutation",
                    "namespace": "Mutation Details",
                    # Use very subtle background colors for mutation types
                    "bgcols": MUTATION_TYPE_COLORS,
                },
                "Is SDRM": {
                    "title": "SDRM",
                    "description": "Contains Surveillance Drug Resistance Mutation",
                    "namespace": "Mutation Details",
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
                },
                "Weighted Contribution": {
                    "title": "Weighted",
                    "description": "Contribution score weighted by drug importance",
                    "namespace": "Resistance Impact",
                    "format": "{:,.1f}",
                    "scale": "RdYlGn-rev",
                    "min": 0,
                    "max": 100,
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
                },
                "Impact": {
                    "title": "Impact Category",
                    "description": "Categorization of the contribution significance",
                    "namespace": "Resistance Impact",
                    # No background colors for Impact column as requested
                    # Using conditional text formatting only for professionalism
                    "cond_formatting_rules": {
                        # Using text-only formatting that's more subtle and professional
                        "custom1": [{"s_eq": "Dominant"}],
                        "custom2": [{"s_eq": "Major"}],
                        "custom3": [{"s_eq": "Significant"}],
                        "custom4": [{"s_eq": "Minor"}],
                        "custom5": [{"s_eq": "Significant (High-Priority Drug)"}],
                        "custom6": [{"s_eq": "Minor (High-Priority Drug)"}],
                    },
                    "cond_formatting_colours": [
                        {
                            "custom1": "#666666",
                            "custom2": "#666666",
                            "custom3": "#666666",
                            "custom4": "#666666",
                            "custom5": "#666666",
                            "custom6": "#666666",
                        }
                    ],
                },
                "Clinical Comment": {
                    "title": "Clinical Comment",
                    "description": "Clinical commentary on mutation significance",
                    "namespace": "Resistance Impact",
                    "scale": False,
                    "hidden": True,  # Hidden by default as it can be lengthy
                },
            },
            "data": contribution_data,
        }

        # Write to file
        output_file = os.path.join(
            output_dir, f"mutation_contribution_{gene_name.lower()}_mqc.json"
        )
        try:
            with open(output_file, "w") as f:
                json.dump(table_data, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created mutation resistance contribution for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating mutation resistance contribution for {gene_name}: {str(e)}"
            )
    return created_files


def create_mutation_clinical_commentary(data, sample_id, output_dir):
    """
    Creates a MultiQC-native table showing clinical implications of mutations.

    This function generates a consolidated tabular visualization of mutation clinical
    significance, grouping by mutations and eliminating redundant clinical commentary.
    Supports all gene types including future additions like Capsid (CA).

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        dict: Mapping of created files by gene
    """
    # Collection structure for mutation commentary - organized by mutation
    gene_mutation_data = defaultdict(
        lambda: defaultdict(
            lambda: {
                "mutation_type": "",
                "clinical_implication": "",
                "affected_drugs": [],
                "max_score": 0,
                "is_sdrm": False,
                "is_apobec": False,
                "has_clinical_comments": False,
            }
        )
    )
    created_files = {}
    # Process all drug resistance data with genes
    for gene_seq in data.get("alignedGeneSequences", []):
        if not gene_seq or not gene_seq.get("gene"):
            continue

        gene_name = gene_seq["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        # Get SDRMs for this gene
        sdrm_texts = (
            [sdrm.get("text", "") for sdrm in gene_seq.get("SDRMs", [])]
            if gene_seq.get("SDRMs")
            else []
        )
        # Process mutations directly from gene data
        for mutation in gene_seq.get("mutations", []):
            if not mutation:
                continue

            mutation_text = mutation.get("text", "")
            mutation_type = mutation.get("primaryType", "Other")
            is_apobec = mutation.get("isApobecMutation", False)
            is_sdrm = mutation_text in sdrm_texts

            # Store basic mutation information
            gene_mutation_data[gene_name][mutation_text][
                "mutation_type"
            ] = mutation_type
            gene_mutation_data[gene_name][mutation_text]["is_sdrm"] = is_sdrm
            gene_mutation_data[gene_name][mutation_text]["is_apobec"] = is_apobec

    # Process all drug resistance data for impact and comments
    for dr_entry in data.get("drugResistance", []):
        if not dr_entry or not dr_entry.get("gene"):
            continue

        gene_name = dr_entry["gene"].get("name", "Unknown")

        # Skip if gene name is unknown or missing
        if gene_name == "Unknown":
            continue

        for drug_score in dr_entry.get("drugScores", []):
            if not drug_score:
                continue

            drug_name = drug_score["drug"].get("displayAbbr", "Unknown")
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            drug_display = f"{drug_name} ({drug_class})"
            score = drug_score.get("score", 0)

            # Process each partial score contribution
            for partial in drug_score.get("partialScores", []):
                partial_score = partial.get("score", 0)

                for mutation in partial.get("mutations", []):
                    if not mutation:
                        continue

                    mutation_text = mutation.get("text", "")
                    mutation_type = mutation.get("primaryType", "Other")

                    # Store mutation type
                    gene_mutation_data[gene_name][mutation_text][
                        "mutation_type"
                    ] = mutation_type

                    # Add drug to affected drugs with its score
                    gene_mutation_data[gene_name][mutation_text][
                        "affected_drugs"
                    ].append({"drug": drug_display, "score": partial_score})

                    # Track maximum score
                    if (
                        partial_score
                        > gene_mutation_data[gene_name][mutation_text]["max_score"]
                    ):
                        gene_mutation_data[gene_name][mutation_text][
                            "max_score"
                        ] = partial_score

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
                                gene_mutation_data[gene_name][mutation_text][
                                    "has_clinical_comments"
                                ] = True

    # Create a MultiQC table for each gene
    for gene_name, mutations in gene_mutation_data.items():
        if not mutations:
            logger.info(
                f"No mutation clinical data found for {gene_name} gene, skipping clinical commentary"
            )
            continue

        # Prepare data structure for MultiQC table
        table_data = {}

        # Create consolidated table entries
        for mutation_text, mutation_info in mutations.items():
            # Skip if missing critical information or no impact on any drugs
            if not mutation_info["affected_drugs"]:
                continue

            # Sort affected drugs by score (highest first)
            sorted_drugs = sorted(
                mutation_info["affected_drugs"],
                key=lambda x: x["score"],
                reverse=True,
            )

            # Create a formatted affected drugs string
            affected_drugs_text = []
            for drug_info in sorted_drugs[:5]:  # Limit to top 5 for readability
                affected_drugs_text.append(
                    f"{drug_info['drug']} ({drug_info['score']})"
                )

            # Add "and more" if there are additional drugs
            if len(sorted_drugs) > 5:
                affected_drugs_text.append(f"and {len(sorted_drugs) - 5} more")

            # Create a clinical significance description if no explicit comment
            clinical_implication = mutation_info["clinical_implication"]
            if not clinical_implication:
                mutation_type = mutation_info["mutation_type"]
                max_score = mutation_info["max_score"]

                if mutation_type == "Major":
                    if max_score >= 30:
                        clinical_implication = f"Major resistance mutation causing significant reductions in drug susceptibility (score {max_score})"
                    else:
                        clinical_implication = f"Major resistance mutation causing reduced drug susceptibility (score {max_score})"
                elif mutation_type == "Accessory":
                    clinical_implication = f"Accessory mutation that enhances resistance when present with major mutations (contributes {max_score} points)"
                else:
                    clinical_implication = f"Mutation with limited effect on drug susceptibility (contributes {max_score} points)"

                # Add SDRM note if applicable
                if mutation_info["is_sdrm"]:
                    clinical_implication += ". This is a surveillance drug resistance mutation (SDRM) used for epidemiological tracking."

                # Add APOBEC note if applicable
                if mutation_info["is_apobec"]:
                    clinical_implication += ". This mutation may result from APOBEC-mediated G-to-A hypermutation."

            # Create a row for this mutation using mutation type to influence sorting
            row_id = f"{mutation_info['mutation_type']}_{mutation_text}"
            table_data[row_id] = {
                "Mutation Type": mutation_info["mutation_type"],
                "Mutation": mutation_text,
                "SDRM": "Yes" if mutation_info["is_sdrm"] else "No",
                "APOBEC": "Yes" if mutation_info["is_apobec"] else "No",
                "Affected Drugs": ", ".join(affected_drugs_text),
                "Max Score": mutation_info["max_score"],
                "Clinical Implication": clinical_implication,
            }

        # Create the MultiQC table configuration
        clinical_table = {
            "id": f"mutation_clinical_{gene_name.lower()}_table",
            "section_name": f"{gene_name} Mutation Clinical Significance",
            "description": f"Consolidated analysis of {gene_name} mutations and their clinical implications for HIV drug resistance. This table groups information by mutation, showing affected drugs and their resistance scores, with detailed clinical commentary.",
            "plot_type": "table",
            "pconfig": {
                "id": f"mutation_clinical_{gene_name.lower()}_table_config",
                "title": f"{gene_name} Mutation Clinical Significance",
                "namespace": "Clinical Interpretation",
                "save_file": True,
                "col1_header": "Mutation Type",
                "sortRows": True,
                # Default sorting by mutation type with Major first
                "defaultsort": [
                    {"column": "Mutation Type", "direction": "asc"},
                    {"column": "Max Score", "direction": "desc"},
                ],
            },
            "headers": {
                "Mutation Type": {
                    "title": "Type",
                    "description": "Mutation classification (Major, Accessory, Other)",
                    "scale": False,
                    # Use subtle background colors for mutation types
                    "bgcols": MUTATION_TYPE_COLORS,
                },
                "Mutation": {
                    "title": "Mutation",
                    "description": "Mutation identifier",
                    "scale": False,
                },
                "SDRM": {
                    "title": "SDRM",
                    "description": "Surveillance Drug Resistance Mutation",
                    "bgcols": {"Yes": "#f5f9f5", "No": ""},  # Very subtle green
                },
                "APOBEC": {
                    "title": "APOBEC",
                    "description": "APOBEC-mediated G-to-A hypermutation",
                    "bgcols": {"Yes": "#f9f5fc", "No": ""},  # Very subtle purple
                    "hidden": True,  # Hide by default to reduce visual clutter
                },
                "Affected Drugs": {
                    "title": "Affected Drugs",
                    "description": "Drugs affected by this mutation with resistance scores",
                    "scale": False,
                },
                "Max Score": {
                    "title": "Max Impact",
                    "description": "Maximum resistance score contribution across all drugs",
                    "format": "{:,.0f}",
                    "scale": "RdYlGn-rev",
                    "min": 0,
                },
                "Clinical Implication": {
                    "title": "Clinical Implication",
                    "description": "Detailed commentary on clinical significance",
                    "scale": False,
                },
            },
            "data": table_data,
        }
        # Write the table to file
        output_file = os.path.join(
            output_dir, f"mutation_clinical_{gene_name.lower()}_table_mqc.json"
        )
        try:
            with open(output_file, "w") as f:
                json.dump(clinical_table, f, indent=2)
            created_files[gene_name] = output_file
            logger.info(
                f"Created mutation clinical commentary for {gene_name} gene: {output_file}"
            )
        except Exception as e:
            logger.error(
                f"Error creating mutation clinical commentary for {gene_name}: {str(e)}"
            )

    return created_files
