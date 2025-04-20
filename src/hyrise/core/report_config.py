"""
MultiQC report configuration generation for HyRISE package
"""

import os
import yaml
from datetime import datetime
from hyrise import __version__


def generate_multiqc_config(output_dir, sample_name=None, output_file=None):
    """
    Generate an improved MultiQC configuration file for HyRISE reports

    Args:
        output_dir (str): Directory where the config file will be created
        sample_name (str, optional): Sample name to include in the report header
        output_file (str, optional): Custom filename for the config. If None, uses 'multiqc_config.yml'

    Returns:
        str: Path to the generated config file
    """
    # Set default sample name if not provided
    if not sample_name:
        sample_name = "HIV Sample"

    # Get formatted date for the report
    formatted_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create MultiQC config dictionary
    config = {
        # Report title and subtitle
        "title": "HyRISE: Resistance Interpretation & Scoring Engine",
        "subtitle": "HIV Drug Resistance Sequencing Analysis Report",
        "report_comment": "A comprehensive analysis of HIV drug resistance mutations based on sequencing data. "
        "This report leverages Sierra-Local with HyRISE visualization and provides detailed insights "
        "into drug resistance patterns, mutation profiles, and treatment implications.",
        # Whether to show the analysis paths and analysis time
        "show_analysis_paths": False,
        "show_analysis_time": True,
        # Project level information
        "report_header_info": [
            {"Sample Name": sample_name},
            {"Analysis Date": formatted_datetime},
            {"Sequencing Platform": "Next Generation Sequencing"},
            {"Sierra Version": "9.4"},
            {"Database Date": "2022-12-07"},
            {"HyRISE Version": __version__},
            {
                "Contact E-mail": "<a href='mailto:your.email@example.com'>your.email@example.com</a>"
            },
        ],
        "skip_generalstats": True,
        # Custom plot configurations for better visualization
        "custom_plot_config": {
            # Drug resistance tables and plots
            "drug_resistance_table_config": {"title": "HIV Drug Resistance Profile"},
            "mutations_table_config": {"title": "Significant Resistance Mutations"},
            "resistance_level_distribution_plot": {
                "title": "Distribution of Resistance Levels Across Drug Classes"
            },
            "mutation_position_map_plot": {
                "title": "Genomic Distribution of Resistance Mutations"
            },
            "partial_score_analysis_plot": {
                "title": "Mutation Contribution to Resistance Scores"
            },
        },
        # Control which columns are visible in tables by default
        "table_columns_visible": {
            "drug_resistance_table": {
                "Drug": True,
                "Class": True,
                "Score": True,
                "Interpretation": True,
            },
            "significant_mutations": {
                "Mutation": True,
                "Type": True,
                "Position": True,
                "Is SDRM": True,
            },
        },
        "custom_content": {
            "order": [
                "version_information",
            ]
        },
        # Define the order and custom names for top-level modules - REORGANIZED FOR BETTER FLOW
        # "top_modules": [
        # # 1. Executive Summary Section
        # {
        #     "sample_overview": {
        #         "name": "Executive Summary",
        #         "info": "High-level overview of resistance findings and recommendations."
        #     }
        # },
        # # 2. Analysis Information
        # {
        #     "version_information": {
        #         "name": "Analysis Information",
        #         "info": "Version information for the HIV drug resistance database and analysis tools."
        #     }
        # },
        # # 3. Drug Resistance Profiles by Gene (Integrase)
        # {
        #     "drug_class_overview_in": {
        #         "name": "IN Resistance Overview",
        #         "info": "High-level overview of integrase inhibitor resistance patterns."
        #     }
        # },
        # {
        #     "drug_resistance_in_table": {
        #         "name": "IN Drug Resistance Profile",
        #         "info": "Detailed analysis of resistance to Integrase Strand Transfer Inhibitors (INSTIs)."
        #     }
        # },
        # {
        #     "drug_resistance_in_insti_table": {
        #         "name": "IN INSTI Resistance Details",
        #         "info": "INSTI-specific resistance scores and interpretations."
        #     }
        # },
        # {
        #     "resistance_level_distribution_in": {
        #         "name": "IN Resistance Distribution",
        #         "info": "Distribution of resistance levels across integrase inhibitor drugs."
        #     }
        # },
        # # 4. Drug Resistance Profiles by Gene (Reverse Transcriptase)
        # {
        #     "drug_class_overview_rt": {
        #         "name": "RT Resistance Overview",
        #         "info": "High-level overview of reverse transcriptase inhibitor resistance patterns."
        #     }
        # },
        # {
        #     "drug_resistance_rt_table": {
        #         "name": "RT Drug Resistance Profile",
        #         "info": "Comprehensive analysis of resistance to Reverse Transcriptase Inhibitors (NRTIs and NNRTIs)."
        #     }
        # },
        # {
        #     "drug_resistance_rt_nrti_table": {
        #         "name": "RT NRTI Resistance Details",
        #         "info": "NRTI-specific resistance scores and interpretations."
        #     }
        # },
        # {
        #     "drug_resistance_rt_nnrti_table": {
        #         "name": "RT NNRTI Resistance Details",
        #         "info": "NNRTI-specific resistance scores and interpretations."
        #     }
        # },
        # {
        #     "resistance_level_distribution_rt": {
        #         "name": "RT Resistance Distribution",
        #         "info": "Distribution of resistance levels across RT inhibitor drugs."
        #     }
        # },
        # # 5. Drug Resistance Profiles by Gene (Protease)
        # {
        #     "drug_class_overview_pr": {
        #         "name": "PR Resistance Overview",
        #         "info": "High-level overview of protease inhibitor resistance patterns."
        #     }
        # },
        # {
        #     "drug_resistance_pr_table": {
        #         "name": "PR Drug Resistance Profile",
        #         "info": "Detailed analysis of resistance to Protease Inhibitors (PIs)."
        #     }
        # },
        # {
        #     "drug_resistance_pr_pi_table": {
        #         "name": "PR PI Resistance Details",
        #         "info": "PI-specific resistance scores and interpretations."
        #     }
        # },
        # {
        #     "resistance_level_distribution_pr": {
        #         "name": "PR Resistance Distribution",
        #         "info": "Distribution of resistance levels across protease inhibitor drugs."
        #     }
        # },
        # # 6. Mutation Contribution Analysis by Gene
        # {
        #     "partial_score_analysis_in": {
        #         "name": "IN Mutation Contribution Analysis",
        #         "info": "Analysis of how specific mutations contribute to integrase inhibitor resistance."
        #     }
        # },
        # {
        #     "partial_score_analysis_rt": {
        #         "name": "RT Mutation Contribution Analysis",
        #         "info": "Analysis of how specific mutations contribute to RT inhibitor resistance."
        #     }
        # },
        # {
        #     "partial_score_analysis_pr": {
        #         "name": "PR Mutation Contribution Analysis",
        #         "info": "Analysis of how specific mutations contribute to protease inhibitor resistance."
        #     }
        # },
        # # 7. Clinical Significance by Gene
        # {
        #     "drug_commentary_in": {
        #         "name": "IN Clinical Significance",
        #         "info": "Clinical implications of integrase mutations organized by mutation type."
        #     }
        # },
        # {
        #     "drug_commentary_rt": {
        #         "name": "RT Clinical Significance",
        #         "info": "Clinical implications of RT mutations organized by mutation type."
        #     }
        # },
        # {
        #     "drug_commentary_pr": {
        #         "name": "PR Clinical Significance",
        #         "info": "Clinical implications of protease mutations organized by mutation type."
        #     }
        # },
        # # 8. Mutation Details by Gene
        # {
        #     "all_mutations_in": {
        #         "name": "IN All Mutations",
        #         "info": "Complete list of all integrase mutations detected."
        #     }
        # },
        # {
        #     "major_mutations_in": {
        #         "name": "IN Major Mutations",
        #         "info": "Major mutations in the integrase gene that directly cause resistance."
        #     }
        # },
        # {
        #     "accessory_mutations_in": {
        #         "name": "IN Accessory Mutations",
        #         "info": "Accessory mutations in the integrase gene that enhance resistance."
        #     }
        # },
        # {
        #     "mutation_summary_in": {
        #         "name": "IN Mutation Summary",
        #         "info": "Summary of mutation types found in the integrase gene."
        #     }
        # },
        # {
        #     "mutation_position_map_in": {
        #         "name": "IN Mutation Position Map",
        #         "info": "Map of mutation positions along the integrase gene sequence."
        #     }
        # },
        # {
        #     "all_mutations_rt": {
        #         "name": "RT All Mutations",
        #         "info": "Complete list of all RT mutations detected."
        #     }
        # },
        # {
        #     "major_mutations_rt": {
        #         "name": "RT Major Mutations",
        #         "info": "Major mutations in the RT gene that directly cause resistance."
        #     }
        # },
        # {
        #     "accessory_mutations_rt": {
        #         "name": "RT Accessory Mutations",
        #         "info": "Accessory mutations in the RT gene that enhance resistance."
        #     }
        # },
        # {
        #     "mutation_summary_rt": {
        #         "name": "RT Mutation Summary",
        #         "info": "Summary of mutation types found in the RT gene."
        #     }
        # },
        # {
        #     "mutation_position_map_rt": {
        #         "name": "RT Mutation Position Map",
        #         "info": "Map of mutation positions along the RT gene sequence."
        #     }
        # },
        # {
        #     "all_mutations_pr": {
        #         "name": "PR All Mutations",
        #         "info": "Complete list of all protease mutations detected."
        #     }
        # },
        # {
        #     "major_mutations_pr": {
        #         "name": "PR Major Mutations",
        #         "info": "Major mutations in the protease gene that directly cause resistance."
        #     }
        # },
        # {
        #     "accessory_mutations_pr": {
        #         "name": "PR Accessory Mutations",
        #         "info": "Accessory mutations in the protease gene that enhance resistance."
        #     }
        # },
        # {
        #     "mutation_summary_pr": {
        #         "name": "PR Mutation Summary",
        #         "info": "Summary of mutation types found in the protease gene."
        #     }
        # },
        # {
        #     "mutation_position_map_pr": {
        #         "name": "PR Mutation Position Map",
        #         "info": "Map of mutation positions along the protease gene sequence."
        #     }
        # },
        # # 9. Interpretation Guides (moved to the end as reference material)
        # {
        #     "resistance_interpretation_section": {
        #         "name": "Resistance Score Interpretation",
        #         "info": "Guide to interpreting drug resistance scores in this report."
        #     }
        # },
        # {
        #     "mutation_type_definitions_section": {
        #         "name": "Mutation Type Definitions",
        #         "info": "Definitions of the different mutation types in this report."
        #     }
        # },
        # {
        #     "general_resistance_concepts": {
        #         "name": "HIV Resistance Concepts",
        #         "info": "General concepts for understanding HIV drug resistance interpretation."
        #     }
        # },
        # # 10. Any other custom sections
        # "custom_data"
        # ],
        # Section ordering to ensure logical flow
        # "report_section_order": {
        #     "sample_overview": {
        #         "order": -10000  # Executive summary always first
        #     },
        #     "version_information": {
        #         "order": -9000
        #     },
        #     # Gene-specific ordering
        #     "drug_class_overview_in": {
        #         "order": -8000
        #     },
        #     "drug_resistance_in_table": {
        #         "after": "drug_class_overview_in"
        #     },
        #     "drug_class_overview_rt": {
        #         "after": "resistance_level_distribution_in"
        #     },
        #     "drug_class_overview_pr": {
        #         "after": "resistance_level_distribution_rt"
        #     },
        #     "mutation_summary_in": {
        #         "after": "partial_score_analysis_pr"
        #     },
        #     "mutation_summary_rt": {
        #         "after": "mutation_position_map_in"
        #     },
        #     "mutation_summary_pr": {
        #         "after": "mutation_position_map_rt"
        #     },
        #     "resistance_interpretation_section": {
        #         "order": 9000  # Reference material toward the end
        #     },
        #     "mutation_type_definitions_section": {
        #         "order": 9500
        #     },
        #     "general_resistance_concepts": {
        #         "order": 10000
        #     }
        # },
        # Custom section comments to enhance understanding
        "section_comments": {
            "sample_overview": "High-level **executive summary** of the HIV resistance findings for this sample, including key resistance patterns and potential clinical implications.",
            "version_information": "Provides details about the **HIV drug resistance database** version and analysis tools used for this report.",
            # IN sections
            "drug_class_overview_in": "Overview of **integrase inhibitor resistance** patterns detected in this sample.",
            "drug_resistance_in_table": "Analyzes **INSTI resistance patterns** with detailed scoring and interpretation, essential for guiding treatment decisions involving integrase inhibitors.",
            "resistance_level_distribution_in": "Visualizes the **distribution of resistance levels** across INSTI drugs, allowing quick assessment of overall resistance patterns.",
            "partial_score_analysis_in": "Shows how individual **mutations contribute** to the total resistance score for each INSTI drug, highlighting key resistance drivers.",
            "drug_commentary_in": "Provides **detailed interpretation** of INSTI resistance mutations, explaining their clinical significance and impact on treatment efficacy.",
            "mutation_position_map_in": "Maps the **genomic locations** of INSTI resistance mutations, revealing patterns and clusters of mutations along the integrase gene.",
            "mutation_summary_in": "Summarizes **mutation types** found in the integrase gene, categorizing by clinical significance and resistance impact.",
            # RT sections
            "drug_class_overview_rt": "Overview of **RT inhibitor resistance** patterns detected in this sample.",
            "drug_resistance_rt_table": "Examines **RT inhibitor resistance** with comprehensive scoring for NRTIs and NNRTIs, critical for evaluating backbone therapy options.",
            "resistance_level_distribution_rt": "Visualizes the **distribution of resistance levels** across RT inhibitor drugs, showing patterns across both NRTI and NNRTI classes.",
            "partial_score_analysis_rt": "Shows how individual **mutations contribute** to the total resistance score for each RT inhibitor, highlighting key resistance drivers.",
            "drug_commentary_rt": "Offers **comprehensive explanation** of RT mutations, their mechanisms of resistance, and implications for therapy selection.",
            "mutation_position_map_rt": "Maps the **genomic locations** of RT mutations, revealing patterns and clusters of mutations along the reverse transcriptase gene.",
            "mutation_summary_rt": "Summarizes **mutation types** found in the RT gene, categorizing by clinical significance and resistance impact.",
            # PR sections
            "drug_class_overview_pr": "Overview of **protease inhibitor resistance** patterns detected in this sample.",
            "drug_resistance_pr_table": "Details **protease inhibitor resistance** with thorough analysis of PI susceptibility, important for PI-based regimen selection.",
            "resistance_level_distribution_pr": "Visualizes the **distribution of resistance levels** across protease inhibitor drugs, allowing assessment of overall PI resistance patterns.",
            "partial_score_analysis_pr": "Shows how individual **mutations contribute** to the total resistance score for each protease inhibitor, highlighting key resistance drivers.",
            "drug_commentary_pr": "Gives **in-depth analysis** of protease mutations, their resistance pathways, and clinical relevance for treatment planning.",
            "mutation_position_map_pr": "Maps the **genomic locations** of protease mutations, revealing patterns and clusters of mutations along the protease gene.",
            "mutation_summary_pr": "Summarizes **mutation types** found in the protease gene, categorizing by clinical significance and resistance impact.",
            # Interpretation guides
            "resistance_interpretation_section": "**Reference guide** for interpreting the drug resistance scores and levels presented throughout this report.",
            "mutation_type_definitions_section": "**Reference guide** for understanding the different mutation types and their significance in HIV resistance.",
            "general_resistance_concepts": "**Educational reference** about general HIV resistance concepts and mechanisms.",
        },
        # Whether to disable version detection
        "disable_version_detection": False,
        # Software versions to display
        "software_versions": {
            "1. Analysis Tools": {
                "HyRISE": "1.0.0",
                "Sierra": "9.4",
                "Sierra-Local": "1.0.1",
            },
            "2. Reference Database": {"HIVDB": "9.4 (2022-12-07)"},
        },
        # Disable default intro text
        "intro_text": False,
        # Custom color scheme for the report
        "colours": {
            "plain_content": {
                "info": "#0d6efd",
                "warning": "#ff9800",
                "danger": "#dc3545",
            },
            "status": {"pass": "#28a745", "warn": "#ff9800", "fail": "#dc3545"},
        },
    }

    # Determine output filename
    if not output_file:
        output_file = os.path.join(output_dir, "multiqc_config.yml")
    else:
        output_file = os.path.join(output_dir, output_file)

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Write config to file
    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return output_file


def generate_multiqc_command(config_path, output_dir, report_dir=None):
    """
    Generate a shell command to run MultiQC with the appropriate configuration

    Args:
        config_path (str): Path to the MultiQC config file
        output_dir (str): Directory containing the visualization files
        report_dir (str, optional): Directory where the report should be saved.
            If None, uses 'multiqc_report' inside output_dir

    Returns:
        str: Shell command to run MultiQC
    """
    # Set default report directory if not provided
    if not report_dir:
        report_dir = os.path.join(output_dir, "multiqc_report")

    # Build the MultiQC command
    command = f"multiqc {output_dir} -o {report_dir} --config {config_path}"

    return command
