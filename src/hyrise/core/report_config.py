"""
Enhanced HyRISE MultiQC Report Generator with robust HTML modifications
and integrated command-line interface.
"""

import os
import sys
import shutil
import argparse
import subprocess
import yaml
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Union
from bs4 import BeautifulSoup


class HyRISEReportGenerator:
    """Class to handle the generation and customization of MultiQC reports for HyRISE."""

    def __init__(
        self,
        output_dir: str,
        version: str = "0.1.0",
        sample_name: Optional[str] = None,
        metadata_info: Optional[Dict[str, Any]] = None,
        contact_email: Optional[str] = None,
    ):
        """
        Initialize the report generator.

        Args:
            output_dir: Directory where the report will be created
            version: HyRISE version string
            sample_name: Sample name to include in the report
            metadata_info: Metadata information extracted from Sierra JSON
            contact_email: Contact email to include in the report
        """
        self.output_dir = os.path.abspath(output_dir)
        self.version = version
        self.sample_name = sample_name
        self.metadata_info = metadata_info or {}
        self.contact_email = contact_email
        self.report_dir = os.path.join(output_dir, "multiqc_report")
        self.config_path = None
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a basic logger."""
        import logging

        logger = logging.getLogger("hyrise-report")
        logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(ch)

        return logger

    def embed_logo(self, logo_path: Optional[str] = None) -> str:
        """
        Encode a logo file as base64 for embedding in HTML.

        Args:
            logo_path: Path to logo file (PNG or SVG)

        Returns:
            str: Data URI for the logo
        """
        # Resolve image path
        if logo_path:
            resolved_path = Path(logo_path)
        else:
            # Look in multiple locations for a default logo
            possible_paths = [
                Path(__file__).parent / "assets" / "hyrise_logo.svg",
                Path(__file__).parent / "assets" / "hyrise_logo.png",
                Path(os.path.dirname(os.path.abspath(__file__)))
                / "assets"
                / "hyrise_logo.svg",
                Path(os.path.dirname(os.path.abspath(__file__)))
                / "assets"
                / "hyrise_logo.png",
            ]

            resolved_path = next((p for p in possible_paths if p.exists()), None)

        self.logger.info(f"Looking for logo at: {resolved_path}")

        # Validate file exists
        if not resolved_path or not resolved_path.exists():
            self.logger.warning(
                f"Logo file not found at {resolved_path}, using fallback"
            )
            # Return an empty string if no logo is found
            return ""

        # Log file details
        self.logger.info(
            f"Found logo file: {resolved_path} ({resolved_path.stat().st_size} bytes)"
        )

        # Validate file extension
        if resolved_path.suffix.lower() not in [".svg", ".png", ".jpg", ".jpeg"]:
            self.logger.warning(
                f"Unsupported file format: {resolved_path.suffix}. Only .svg, .png, .jpg, .jpeg files are supported."
            )
            return ""

        try:
            # Encode image as base64
            with open(resolved_path, "rb") as image_file:
                file_content = image_file.read()
                self.logger.info(f"Read {len(file_content)} bytes from logo file")
                encoded_string = base64.b64encode(file_content).decode("utf-8")

            # Create data URI for embedding
            if resolved_path.suffix.lower() == ".svg":
                mime_type = "image/svg+xml"
            elif resolved_path.suffix.lower() in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            else:
                mime_type = "image/png"

            data_uri = f"data:{mime_type};base64,{encoded_string}"
            self.logger.info(f"Created data URI with length {len(data_uri)}")
            return data_uri
        except Exception as e:
            self.logger.error(f"Error embedding logo: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
            return ""

    def create_metadata_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from Sierra JSON for use in the report.

        Args:
            data: Sierra JSON data

        Returns:
            Dict containing structured metadata
        """
        # Extract database version information
        db_version = None
        db_publish_date = None
        gene_versions: Dict[str, Dict[str, str]] = {}

        for dr in data.get("drugResistance", []):
            gene_name = dr["gene"]["name"]
            version = dr["version"].get("text", "Unknown")
            publish_date = dr["version"].get("publishDate", "Unknown")

            # Capture first seen version as the sample-level reference
            db_version = db_version or version
            db_publish_date = db_publish_date or publish_date

            gene_versions[gene_name] = {
                "version": version,
                "publish_date": publish_date,
            }

        # Extract sequence information
        genes: Dict[str, Dict[str, Any]] = {}

        for gene_seq in data.get("alignedGeneSequences", []):
            gene_name = gene_seq["gene"]["name"]
            first_aa = gene_seq.get("firstAA", 0)
            last_aa = gene_seq.get("lastAA", 0)
            length = (last_aa - first_aa + 1) if first_aa and last_aa else 0

            genes[gene_name] = {
                **gene_versions.get(gene_name, {}),
                "first_aa": first_aa,
                "last_aa": last_aa,
                "length": length,
                "mutations_count": len(gene_seq.get("mutations", [])),
                "sdrm_count": len(gene_seq.get("SDRMs", [])),
            }

        # Create summary structure
        return {
            "sample_id": self.sample_name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subtype": data.get("subtypeText", "Unknown"),
            "database": {
                "version": db_version or "Unknown",
                "publish_date": db_publish_date or "Unknown",
            },
            "genes": genes,
            "validation": data.get("validationResults", []),
        }

    def generate_config(self, use_custom_template=False) -> str:
        """
        Generate the MultiQC configuration file.

        Args:
            use_custom_template: Whether to use a custom MultiQC template

        Returns:
            str: Path to the generated config file
        """
        # Debug logging to check if metadata is available
        if self.metadata_info:
            self.logger.info(
                f"Using extracted metadata: {self.metadata_info.get('sample_id', 'Unknown')} with {len(self.metadata_info.get('genes', {}))} genes"
            )
        else:
            self.logger.warning(
                "No metadata information available. Using default values."
            )

        # Ensure we have metadata info available - if not, use default values
        if not self.metadata_info:
            self.logger.warning(
                "No metadata information available. Using default values."
            )
            metadata_info = {
                "sample_id": self.sample_name or "HIV Sample",
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "subtype": "Unknown",
                "database": {
                    "version": "Unknown",
                    "publish_date": "Unknown",
                },
                "genes": {},
                "validation": [],
            }
        else:
            metadata_info = self.metadata_info

        # Prepare metadata for report header
        sample_name = metadata_info.get("sample_id") or self.sample_name or "HIV Sample"
        analysis_date = metadata_info.get("analysis_date") or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        db_info = metadata_info.get("database", {})
        database_version = db_info.get("version", "Unknown")
        database_date = db_info.get("publish_date", "Unknown")

        genes_present = sorted(metadata_info.get("genes", {}).keys())
        genes_analyzed = ", ".join(genes_present) if genes_present else "None"

        # Build the header info
        header = [
            {"Sample Name": sample_name},
            {"Analysis Date": analysis_date},
            {"Genes Analyzed": genes_analyzed},
            {"Stanford DB Version": database_version},
            {"Stanford DB Date": database_date},
        ]

        # Add per-gene mutation/SDRM count lines
        for g in genes_present:
            info = metadata_info["genes"][g]
            header.append(
                {f"{g} Mut / SDRM": f"{info['mutations_count']} / {info['sdrm_count']}"}
            )

        # Always add HyRISE version
        header.append({"HyRISE Version": self.version})

        # Only add email if provided
        if self.contact_email:
            header.append(
                {
                    "Contact E-mail": f"<a href='mailto:{self.contact_email}'>{self.contact_email}</a>"
                }
            )

        # Create the configuration dictionary
        config = {
            # Report title and subtitle
            "title": "HyRISE: Resistance Interpretation & Scoring Engine",
            "subtitle": "HIV Drug Resistance Sequencing Analysis Report",
            "report_comment": "A comprehensive analysis of HIV drug resistance mutations based on sequencing data. "
            "This report leverages Sierra-Local with HyRISE visualization and provides detailed insights "
            "into drug resistance patterns, mutation profiles, and treatment implications.",
            # Output file configuration
            "output_fn_name": "hyrise_resistance_report.html",  # Custom filename for better identification
            "data_dir_name": "hyrise_data",  # Custom data directory name
            "plots_dir_name": "hyrise_plots",  # Custom plots directory name
            "data_format": "tsv",  # TSV format for data exports
            # Data handling options
            "make_data_dir": True,  # Create a data directory for report data
            "zip_data_dir": True,  # Zip the data directory for easy sharing
            "data_dump_file": True,  # Create a data dump file for further analysis
            "export_plots": True,  # Export plots as standalone files for publications
            # Performance options
            "profile_runtime": False,  # Profile runtime for optimization
            # Built-in MultiQC customization options
            "show_analysis_paths": False,
            "show_analysis_time": True,
            "skip_generalstats": True,
            "collapse_tables": False,  # Keep tables expanded for better visibility
            # Table display options
            "max_table_rows": 1000,  # Increase from default 500 for larger HIV datasets
            "max_configurable_table_columns": 250,  # Increase from default for complex resistance tables
            "decimalPoint_format": ".",  # Ensure consistent decimal formatting
            "thousandsSep_format": ",",  # Ensure consistent thousands separator
            # Use built-in multiQC features for branding
            "custom_logo_url": "https://pypi.org/project/hyrise/",
            "custom_logo_title": "HyRISE - HIV Resistance Interpretation & Scoring Engine",
            "introduction": "This report was generated by HyRISE, the HIV Resistance Interpretation & Scoring Engine.",
            # Report header info
            "report_header_info": header,
            # Visualization options
            "plots_force_interactive": True,  # Force interactive plots for better analysis
            "plots_flat_numseries": 5000,  # Support more data series for complex HIV analysis
            "plots_defer_loading_numseries": 200,  # Improve loading performance for large datasets
            "lineplot_number_of_points_to_hide_markers": 25,  # Hide markers on dense line plots
            "barplot_legend_on_bottom": True,  # Place legend at bottom for better space usage
            "plots_export_font_scale": 1.25,  # Slightly larger fonts for better readability in exported plots
            # Section ordering
            "report_section_order": {
                # Main sections that will act as dropdown parent headers
                "pr_gene_section": {
                    "order": 4000,
                    "section_name": "Protease (PR) Gene Analysis",
                },
                "rt_gene_section": {
                    "order": 3000,
                    "section_name": "Reverse Transcriptase (RT) Gene Analysis",
                },
                "in_gene_section": {
                    "order": 2000,
                    "section_name": "Integrase (IN) Gene Analysis",
                },
                "ca_gene_section": {
                    "order": 1000,
                    "section_name": "Capsid (CA) Gene Analysis",
                },
                "interpretation_section": {
                    "order": 500,
                    "section_name": "Interpretation Guides",
                },
                # ===== PROTEASE (PR) SUBSECTIONS - notice they reference the parent =====
                "drug_class_overview_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_pr_table",
                },
                "mutation_clinical_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_pr_table",
                },
                "mutation_summary_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_pr_table",
                },
                "mutation_details_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_pr_table",
                },
                "mutation_contribution_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_pr_table",
                },
                "mutation_position_map_pr": {
                    "parent": "pr_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_pr_table",
                },
                # ===== REVERSE TRANSCRIPTASE (RT) SUBSECTIONS =====
                "drug_class_overview_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_rt_table",
                },
                "mutation_clinical_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_rt_table",
                },
                "mutation_summary_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_rt_table",
                },
                "mutation_details_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_rt_table",
                },
                "mutation_contribution_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_rt_table",
                },
                "mutation_position_map_rt": {
                    "parent": "rt_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_rt_table",
                },
                # ===== INTEGRASE (IN) SUBSECTIONS =====
                "drug_class_overview_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_in_table",
                },
                "mutation_clinical_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_in_table",
                },
                "mutation_summary_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_in_table",
                },
                "mutation_details_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_in_table",
                },
                "mutation_contribution_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_in_table",
                },
                "mutation_position_map_in": {
                    "parent": "in_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_in_table",
                },
                # ===== CAPSID (CA) SUBSECTIONS =====
                "drug_class_overview_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_ca_table",
                },
                "mutation_clinical_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_ca_table",
                },
                "mutation_summary_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_ca_table",
                },
                "mutation_details_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_ca_table",
                },
                "mutation_contribution_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_ca_table",
                },
                "mutation_position_map_ca": {
                    "parent": "ca_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_ca_table",
                },
                # ===== INTERPRETATION GUIDES SUBSECTIONS =====
                "version_information": {
                    "parent": "interpretation_section",
                    "section_name": "Analysis Information",
                },
                "resistance_interpretation_table": {
                    "parent": "interpretation_section",
                    "section_name": "Resistance Levels Guide",
                    "after": "version_information",
                },
                "mutation_type_table": {
                    "parent": "interpretation_section",
                    "section_name": "Mutation Types Guide",
                    "after": "resistance_interpretation_table",
                },
                "drug_class_info_table": {
                    "parent": "interpretation_section",
                    "section_name": "Drug Classes Guide",
                    "after": "mutation_type_table",
                },
            },
            # Custom plot configuration
            "custom_plot_config": {
                "drug_resistance_table_config": {
                    "title": "HIV Drug Resistance Profile"
                },
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
            # Additional table configuration
            "table_columns_placement": {
                # Ensure important columns are always visible by placing them first
                "drug_resistance_table": [
                    "Drug",
                    "Class",
                    "Score",
                    "Interpretation",
                    "SIR",
                ],
                "mutation_details_table": [
                    "Mutation",
                    "Type",
                    "Position",
                    "Is SDRM",
                    "Clinical Implication",
                ],
            },
            "table_columns_name": {
                # Rename columns for clarity
                "drug_resistance_table": {
                    "Resistance Level": "Interpretation",
                    "SIR": "Clinical Status",
                },
                "significant_mutations": {"Is SDRM": "Surveillance DRM"},
            },
            # Custom content ordering
            "custom_content": {
                "order": [
                    "version_information",
                ]
            },
            # Section comments
            "section_comments": {
                # ===== PROTEASE (PR) SECTIONS =====
                "drug_class_overview_pr_table": "Overview of **protease inhibitor (PI) drug class resistance**, highlighting percentages of affected drugs and resistance severity distribution. This section quantifies resistance across the PI class with priority drug indicators.",
                "drug_resistance_pr_table": "Detailed analysis of **resistance to specific protease inhibitors** with quantitative scoring, clinical interpretations, and weighted scores based on drug importance. Essential for optimizing PI-based regimen selection.",
                "mutation_clinical_pr_table": "Clinical implications of **protease mutations** organized by importance (Major, Accessory, Other), showing specific impacts on drug efficacy with evidence-based commentary extracted from Stanford HIV database.",
                "mutation_summary_pr_table": "Statistical breakdown of **mutation types in protease** with counts, percentages, and representative examples. Includes SDRM and APOBEC-mediated mutation categorization with clinical context.",
                "mutation_details_pr_table": "Comprehensive catalog of all detected **protease mutations** with position information, mutation characteristics, and special classifications (SDRM, APOBEC, unusual variants) in a filterable format.",
                "mutation_contribution_pr_table": "Quantitative analysis showing how individual **protease mutations contribute** to resistance scores for each PI, identifying key resistance drivers and their relative impact percentages.",
                "mutation_position_map_pr": "Interactive visualization mapping **mutations along the protease gene sequence** with color-coding by type, special border indicators for SDRMs, and detailed tooltips for each mutation position.",
                # ===== REVERSE TRANSCRIPTASE (RT) SECTIONS =====
                "drug_class_overview_rt_table": "Overview of **RT inhibitor resistance patterns** across both NRTI and NNRTI drug classes, with resistance metrics for backbone therapy evaluation and priority drug indicators.",
                "drug_resistance_rt_table": "Comprehensive analysis of **RT inhibitor susceptibility** with detailed scoring for NRTIs and NNRTIs, highlighting both standard and weighted resistance scores based on clinical importance.",
                "mutation_clinical_rt_table": "Clinical significance of **RT mutations** showing their impact on drug efficacy and viral fitness, organized by mutation category with linked drug-specific effects and Stanford database commentary.",
                "mutation_summary_rt_table": "Statistical summary of **RT mutation types** with distribution of Major, Accessory, and polymorphic mutations, including special categories for TAMs, NNRTI-specific, and APOBEC-mediated mutations.",
                "mutation_details_rt_table": "Detailed inventory of all **reverse transcriptase mutations** with position information, mutation properties, and special classifications in a searchable, filterable format designed for research use.",
                "mutation_contribution_rt_table": "Mutation-specific analysis showing **how RT mutations contribute** to resistance against individual NRTI and NNRTI drugs, quantifying percentage contributions to total resistance scores.",
                "mutation_position_map_rt": "Interactive genomic visualization of **mutation locations across the RT gene**, revealing mutation hotspots and clinically significant regions with detailed position-specific information.",
                # ===== INTEGRASE (IN) SECTIONS =====
                "drug_class_overview_in_table": "Overview of **integrase inhibitor resistance patterns** with metrics assessing impact on both first-generation (RAL, EVG) and second-generation (DTG, BIC, CAB) integrase inhibitors.",
                "drug_resistance_in_table": "Analysis of **INSTI drug resistance** with detailed scoring and interpretation, providing essential metrics for evaluating efficacy of individual integrase inhibitors with clinical priority weighting.",
                "mutation_clinical_in_table": "Clinical implications of **integrase mutations** demonstrating effects on drug binding and enzyme function, with drug-specific impact analysis and pathway resistance patterns.",
                "mutation_summary_in_table": "Statistical breakdown of **integrase mutation types** by clinical importance, showing distribution of major pathway mutations (Y143, Q148, N155) and accessory resistance mutations.",
                "mutation_details_in_table": "Comprehensive catalog of all **integrase mutations** with position information, resistance characteristics, and special classifications organized for efficient clinical interpretation.",
                "mutation_contribution_in_table": "Quantitative assessment of **how specific integrase mutations** contribute to INSTI resistance, highlighting primary and accessory resistance pathways with their relative contributions.",
                "mutation_position_map_in": "Interactive mapping of **mutations along the integrase gene sequence**, visualizing the distribution of resistance-associated positions with functional domain context and tooltips.",
                # ===== CAPSID (CA) SECTIONS =====
                "drug_class_overview_ca_table": "Overview of **capsid inhibitor resistance patterns**, examining susceptibility to this emerging drug class targeting HIV capsid assembly, with metrics focused on lenacapavir (LEN) and future capsid inhibitors.",
                "drug_resistance_ca_table": "Analysis of **resistance to capsid-targeting drugs** with quantitative scoring and clinical interpretation, important for evaluating these newer long-acting treatment options.",
                "mutation_clinical_ca_table": "Clinical significance of **capsid mutations** showing impact on drug binding sites and capsid protein function, with detailed commentary on structural and functional consequences.",
                "mutation_summary_ca_table": "Statistical overview of **capsid mutation types** categorized by impact on drug resistance and viral fitness, showing distribution across capsid functional domains.",
                "mutation_details_ca_table": "Comprehensive inventory of all detected **capsid mutations** with position information, structural implications, and relationship to known resistance pathways in a research-grade format.",
                "mutation_contribution_ca_table": "Quantitative analysis of **how specific capsid mutations** contribute to resistance against individual capsid inhibitor drugs, with percentage contributions to total resistance scores.",
                "mutation_position_map_ca": "Interactive visualization of **mutation positions along the capsid gene sequence**, highlighting key structural and functional domains with protein structure context where available.",
                # ===== GENERAL SECTIONS =====
                "version_information": "Provides **analysis metadata** including Stanford HIV database version, algorithm parameters, sequence quality metrics, and processing details for reproducibility and reference.",
                "resistance_interpretation_section": "Comprehensive guide to **interpreting drug resistance scores** and levels throughout this report, explaining clinical significance of resistance categories with evidence-based interpretation guidelines.",
            },
            # Disable version detection
            "disable_version_detection": False,
            # Disable default intro text
            "intro_text": False,
            # Enhanced color scheme with more professional clinical colors
            "colours": {
                "plain_content": {
                    "info": "#0d6efd",
                    "warning": "#ff9800",
                    "danger": "#dc3545",
                },
                "status": {"pass": "#28a745", "warn": "#ff9800", "fail": "#dc3545"},
            },
            # Enhanced conditional formatting colors
            "table_cond_formatting_colours": [
                {
                    "blue": "#337ab7",
                    "lbue": "#5bc0de",
                    "pass": "#28a745",
                    "warn": "#f0ad4e",
                    "fail": "#d9534f",
                    "susceptible": "#28a745",
                    "potential": "#5bc0de",
                    "low": "#ffcc00",
                    "intermediate": "#ff9900",
                    "high": "#dc3545",
                }
            ],
            # Additional conditional formatting rules
            "table_cond_formatting_rules": {
                "all_columns": {
                    "pass": [
                        {"s_eq": "pass"},
                        {"s_eq": "true"},
                        {"s_eq": "yes"},
                        {"s_eq": "ok"},
                        {"s_eq": "Susceptible"},
                    ],
                    "warn": [
                        {"s_eq": "warn"},
                        {"s_eq": "unknown"},
                        {"s_eq": "Low-Level"},
                        {"s_eq": "Potential Low-Level"},
                    ],
                    "fail": [
                        {"s_eq": "fail"},
                        {"s_eq": "false"},
                        {"s_eq": "no"},
                        {"s_eq": "High-Level"},
                        {"s_eq": "Intermediate"},
                    ],
                },
                "Resistance Level": {
                    "susceptible": [{"s_eq": "Susceptible"}],
                    "potential": [{"s_eq": "Potential Low-Level"}],
                    "low": [{"s_eq": "Low-Level"}],
                    "intermediate": [{"s_eq": "Intermediate"}],
                    "high": [{"s_eq": "High-Level"}],
                },
            },
            # File patterns to ignore
            "fn_ignore_files": [
                "*.bam",
                "*.bai",
                "*.fq.gz",
                "*.fastq.gz",
                "*.fa",
                "*.pdf",
                "*.parquet",
            ],
            # Add highlight patterns to emphasize important values
            "highlight_patterns": ["High-Level", "Intermediate", "SDRM"],
            "highlight_colors": ["#f8d7da", "#fff3cd", "#d1e7dd"],
        }

        # Use custom template if requested
        if use_custom_template:
            template_dir = os.path.join(
                os.path.dirname(__file__), "templates", "hyrise"
            )
            if os.path.exists(template_dir):
                self.logger.info(f"Using custom template from: {template_dir}")
                config["template"] = template_dir

        # Create assets directory for any additional files
        assets_dir = os.path.join(self.output_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        # Create custom CSS file
        custom_css_path = os.path.join(assets_dir, "hyrise_custom.css")
        with open(custom_css_path, "w") as f:
            f.write(
                """/* HyRISE - Professional Report Styling
    * Custom CSS for MultiQC reports
    * Public Health Agency of Canada
    */

    /* Global Typography and Colors */
    body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    }

    /* Report Header and Navigation */
    .navbar-brand {
    font-weight: 600;
    letter-spacing: 0.2px;
    }

    /* Section Headers and Content */
    .mqc-section {
    margin-bottom: 30px;
    border-bottom: 1px solid #e9ecef;
    padding-bottom: 10px;
    }

    h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    margin-top: 1.5em;
    margin-bottom: 0.7em;
    color: #2a5a8c;
    }

    .mqc-section h3 {
    font-size: 22px;
    border-bottom: 1px solid #e9ecef;
    padding-bottom: 8px;
    }

    .report_comment, 
    .mqc-section-comment {
    border-left: 5px solid #3c8dbc;
    background-color: #ecf5fc;
    padding: 15px;
    margin: 15px 0;
    font-size: 14px;
    }

    /* Tables */
    .table {
    margin-bottom: 25px;
    border: 1px solid #dee2e6;
    }

    .table thead th {
    background-color: #f8f9fa;
    border-bottom: 2px solid #3c8dbc;
    color: #2a5a8c;
    font-weight: 600;
    }

    .table-bordered>tbody>tr>td, 
    .table-bordered>tbody>tr>th, 
    .table-bordered>tfoot>tr>td, 
    .table-bordered>tfoot>tr>th, 
    .table-bordered>thead>tr>td, 
    .table-bordered>thead>tr>th {
    border: 1px solid #dee2e6;
    }

    .table-hover>tbody>tr:hover {
    background-color: #f1f6fb;
    }

    /* Color Scheme for HyRISE Drug Resistance Levels */
    .high-resistance {
    background-color: #d9534f;
    color: white;
    }

    .intermediate {
    background-color: #f0ad4e;
    color: white;
    }

    .low-resistance {
    background-color: #5cb85c;
    color: white;
    }

    .potential {
    background-color: #5bc0de;
    color: white;
    }

    .susceptible {
    background-color: #777777;
    color: white;
    }

    /* Mutation Styling */
    .position-cell {
    box-sizing: border-box;
    border: 1px solid #eee;
    }

    .position-major {
    background-color: #d9534f;
    color: white;
    }

    .position-accessory {
    background-color: #f0ad4e;
    color: white;
    }

    .position-other {
    background-color: #5bc0de;
    color: white;
    }

    .position-sdrm {
    border: 2px solid #5cb85c !important;
    }

    /* Charts and Visualizations */
    .hc-plot-wrapper {
    border: 1px solid #dee2e6;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    margin-bottom: 25px;
    }

    /* Custom Components */
    .summary-card {
    border: 1px solid #dee2e6;
    border-radius: 5px;
    padding: 20px;
    margin-bottom: 25px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    .summary-card h4 {
    color: #2a5a8c;
    margin-top: 0;
    padding-bottom: 10px;
    border-bottom: 1px solid #e9ecef;
    margin-bottom: 15px;
    }

    .executive-summary {
    background-color: #f8f9fa;
    border-left: 5px solid #2a5a8c;
    padding: 15px;
    margin-bottom: 25px;
    }

    /* Overall Status Messages */
    .overall-status {
    padding: 15px;
    margin: 15px 0;
    border-radius: 5px;
    font-weight: 500;
    text-align: center;
    }

    .status-high {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
    }

    .status-int {
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeeba;
    }

    .status-low {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    }

    .status-sus {
    background-color: #d1ecf1;
    color: #0c5460;
    border: 1px solid #bee5eb;
    }

    /* Tab Navigation for Clinical Implications */
    .hyrise-tabs {
    display: flex;
    flex-wrap: wrap;
    border-bottom: 1px solid #dee2e6;
    margin-bottom: 15px;
    }

    .hyrise-tab {
    padding: 8px 15px;
    cursor: pointer;
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-bottom: none;
    margin-right: 5px;
    border-radius: 5px 5px 0 0;
    transition: all 0.2s ease;
    }

    .hyrise-tab.active {
    background-color: #fff;
    border-bottom: 1px solid #fff;
    margin-bottom: -1px;
    font-weight: 600;
    color: #2a5a8c;
    }

    .hyrise-tab:hover {
    background-color: #e9ecef;
    }

    .hyrise-tab-content {
    display: none;
    padding: 15px;
    border: 1px solid #dee2e6;
    border-top: none;
    border-radius: 0 0 5px 5px;
    }

    .hyrise-tab-content.active {
    display: block;
    }
    /* Mutation Position Map */
    .position-map {
    display: flex;
    flex-wrap: wrap;
    margin: 20px 0;
    background-color: #f8f9fa;
    padding: 15px;
    border-radius: 5px;
    border: 1px solid #dee2e6;
    }
    /* Tooltips and Information Displays */
    .position-tooltip {
    background-color: #333;
    color: white;
    padding: 8px;
    border-radius: 4px;
    font-size: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,.2);
    }
    /* Footer Styling */
    .footer {
    border-top: 1px solid #dee2e6;
    padding-top: 20px;
    margin-top: 40px;
    color: #6c757d;
    }
    /* Print Optimizations */
    @media print {
    .mqc-toolbox, .side-nav {
        display: none !important;
    }  
    .mainpage {
        margin-left: 0 !important;
        padding: 0 !important;
    }
    .status-high, .status-int, .status-low, .status-sus,
    .high-resistance, .intermediate, .low-resistance, .potential, .susceptible {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }
    .mqc-section {
        page-break-inside: avoid;
    }
    h2, h3 {
        page-break-after: avoid;
    }
    .summary-card, .executive-summary {
        page-break-inside: avoid;
    }
    }
                """
            )

        # Add custom CSS
        config["custom_css_files"] = [
            os.path.join(self.output_dir, "assets", "hyrise_custom.css")
        ]

        # Create the config file
        config_file = os.path.join(self.output_dir, "multiqc_config.yml")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        self.config_path = config_file
        self.logger.info(f"Generated MultiQC config at: {config_file}")
        return config_file

    def run_multiqc(self) -> Tuple[bool, str]:
        """
        Run MultiQC with the generated configuration.

        Returns:
            Tuple of (success, output|error message)
        """
        if not self.config_path:
            self.generate_config()

        # Ensure report directory exists
        os.makedirs(self.report_dir, exist_ok=True)

        # Create the MultiQC command
        cmd = f"multiqc {self.output_dir} -o {self.report_dir} --config {self.config_path}"
        self.logger.info(f"Running MultiQC: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, check=True, capture_output=True, text=True
            )
            self.logger.info("MultiQC completed successfully")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"MultiQC failed: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            self.logger.error(f"Error running MultiQC: {str(e)}")
            return False, str(e)

    def modify_html(
        self, html_path: str, logo_data_uri: str = ""
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Modify the MultiQC HTML report to customize it for HyRISE.

        Args:
            html_path: Path to the HTML report file
            logo_data_uri: Data URI for the HyRISE logo

        Returns:
            Tuple of (success, modifications_made)
        """
        try:
            with open(html_path, "r", encoding="utf-8") as html:
                soup = BeautifulSoup(html.read(), "html.parser")

            # Track successful modifications
            modifications = {
                "logo": False,
                "title": False,
                "footer": False,
                "about_section": False,
                "toolbox": False,
                "favicon": False,
                "welcome": False,
                "citations": False,
                "navbar_version": False,
            }

            # 1. Replace logos if we have a logo URI
            if logo_data_uri:
                # Try the direct approach first - look for all images that might be logos
                logo_replaced = False

                # 1. Find all images with data:image base64 src (typical for embedded logos)
                for img_tag in soup.find_all(
                    "img", src=lambda x: x and x.startswith("data:image/")
                ):
                    img_tag["src"] = logo_data_uri
                    logo_replaced = True

                # 2. Try standard selectors as backup
                if not logo_replaced:
                    logo_selectors = [
                        "img#mqc_logo",  # Direct ID selector
                        ".navbar-brand img",  # Logo in navbar
                        "a.navbar-brand img",  # Variations
                        "header img.logo",  # Another variation
                        'img[alt="MultiQC"]',  # By alt text
                    ]

                    for selector in logo_selectors:
                        try:
                            logo_imgs = soup.select(selector)
                            if logo_imgs:
                                for logo_img in logo_imgs:
                                    logo_img["src"] = logo_data_uri
                                logo_replaced = True
                                break
                        except Exception as e:
                            self.logger.debug(
                                f"Error with logo selector '{selector}': {e}"
                            )

                # 3. If all else fails, try to find any small images in the header or navbar
                if not logo_replaced:
                    for img_tag in soup.find_all("img"):
                        parent = img_tag.parent
                        while parent and parent.name not in ["nav", "header", "div"]:
                            if "class" in parent.attrs and any(
                                c in ["navbar", "header", "nav"]
                                for c in parent.get("class", [])
                            ):
                                img_tag["src"] = logo_data_uri
                                logo_replaced = True
                                break
                            parent = parent.parent

                modifications["logo"] = logo_replaced

                # Update favicon
                favicon = soup.find("link", {"rel": "icon", "type": "image/png"})
                if favicon:
                    favicon["href"] = logo_data_uri
                    modifications["favicon"] = True

            # 1.5 Replace version in navbar
            version_replaced = False

            # First attempt: direct selector for the small tag in the navbar
            version_selectors = [
                "h1 small.hidden-xs",
                "nav small.hidden-xs",
                ".navbar small.hidden-xs",
                "header small.hidden-xs",
            ]

            for selector in version_selectors:
                version_tags = soup.select(selector)
                for tag in version_tags:
                    if tag.text.strip().startswith("v"):  # Likely a version number
                        tag.string = f"v{self.version}"
                        version_replaced = True

            # If not found with selectors, try more general approach
            if not version_replaced:
                for small_tag in soup.find_all("small", class_="hidden-xs"):
                    if small_tag.text.strip().startswith("v"):
                        small_tag.string = f"v{self.version}"
                        version_replaced = True

            modifications["navbar_version"] = version_replaced

            # 2. Replace title in document
            title_tag = soup.find("title")
            if title_tag:
                title_tag.string = "HyRISE Report"
                modifications["title"] = True

            # 3. Replace toolbox headers
            # Try different approaches with fallbacks for robustness
            for tag in soup.find_all(["h3", "h4"]):
                if "MultiQC" in tag.text and "Toolbox" in tag.text:
                    tag.string = tag.text.replace("MultiQC", "HyRISE")
                    modifications["toolbox"] = True

            # 4. Replace footer
            footers = soup.select(".footer, footer")
            for footer in footers:
                # Instead of removing entirely, which could break layout,
                # replace with simpler HyRISE footer
                footer.clear()  # Clear all contents
                footer.append(soup.new_tag("p"))
                footer.p.string = f"Generated by HyRISE - HIV Resistance Interpretation & Scoring Engine"
                modifications["footer"] = True

            # 5. Replace "About" section with custom content
            about_section = soup.find("div", id="mqc_about")
            if about_section:
                # Find and update the header
                about_header = about_section.find("h4")
                if about_header:
                    about_header.string = "About HyRISE"

                # Clear existing paragraphs
                for p in about_section.find_all("p"):
                    p.decompose()

                # Clear existing blockquotes
                for blockquote in about_section.find_all("blockquote"):
                    blockquote.decompose()

                # Add new paragraphs with the correct information
                # Paragraph 1: Version info
                p1 = soup.new_tag("p")
                p1.string = f"This report was generated using HyRISE version {self.version} (HIV Resistance Interpretation & Scoring Engine)"
                about_section.append(p1)

                # Paragraph 2: YouTube link
                p2 = soup.new_tag("p")
                p2.string = "You can see a YouTube video describing how to use HyRISE reports here: "
                a2 = soup.new_tag(
                    "a", href="https://youtu.be/qPbIlO_KWN0", target="_blank"
                )
                a2.string = "https://youtu.be/qPbIlO_KWN0"
                p2.append(a2)
                about_section.append(p2)

                # Paragraph 3: PHAC info
                p3 = soup.new_tag("p")
                p3.string = "HyRISE was developed at the National Laboratory of Microbiology for the Public Health Agency of Canada by the Pathogen Genetics and Genomics group at the Sexually Transmitted Blood-Borne Infections Division."
                about_section.append(p3)

                # Paragraph 4: GitHub link
                p4 = soup.new_tag("p")
                p4.string = "You can find the source code for HyRISE on GitHub: "
                a4 = soup.new_tag(
                    "a", href="https://github.com/phac-nml/HyRISE", target="_blank"
                )
                a4.string = "https://github.com/phac-nml/HyRISE"
                p4.append(a4)
                about_section.append(p4)

                # Paragraph 5: PyPI link
                p5 = soup.new_tag("p")
                p5.string = "HyRISE is available on PyPI: "
                a5 = soup.new_tag(
                    "a", href="https://pypi.org/project/hyrise/", target="_blank"
                )
                a5.string = "https://pypi.org/project/hyrise/"
                p5.append(a5)
                about_section.append(p5)

                # Paragraph 6: Original MultiQC attribution
                p6 = soup.new_tag("p")
                p6.string = "HyRISE is based on MultiQC template. MultiQC is published in Bioinformatics:"
                about_section.append(p6)

                # Add MultiQC citation block
                citation = soup.new_tag("blockquote")

                # Citation title
                strong = soup.new_tag("strong")
                strong.string = "MultiQC: Summarize analysis results for multiple tools and samples in a single report"
                citation.append(strong)
                citation.append(soup.new_tag("br"))

                # Citation authors
                em = soup.new_tag("em")
                em.string = (
                    "Philip Ewels, Måns Magnusson, Sverker Lundin and Max Käller"
                )
                citation.append(em)
                citation.append(soup.new_tag("br"))

                # Citation journal
                citation.append("Bioinformatics (2016)")
                citation.append(soup.new_tag("br"))

                # Citation DOI
                citation.append("doi: ")
                doi_link = soup.new_tag(
                    "a",
                    href="http://dx.doi.org/10.1093/bioinformatics/btw354",
                    target="_blank",
                )
                doi_link.string = "10.1093/bioinformatics/btw354"
                citation.append(doi_link)
                citation.append(soup.new_tag("br"))

                # Citation PMID
                citation.append("PMID: ")
                pmid_link = soup.new_tag(
                    "a",
                    href="http://www.ncbi.nlm.nih.gov/pubmed/27312411",
                    target="_blank",
                )
                pmid_link.string = "27312411"
                citation.append(pmid_link)

                about_section.append(citation)

                modifications["about_section"] = True

            # 6. Remove citations section if present (handled in the About section now)
            citation_selectors = [
                "#mqc_citing",  # Direct ID
                'h4:contains("Citing MultiQC")',  # By text
                "blockquote cite",  # Specific citation element
            ]

            for selector in citation_selectors:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        # Find the parent section if possible
                        section = elem
                        while section and section.name != "section":
                            section = section.parent

                        # Remove the section or just the element if section not found
                        if (
                            section and section.get("id") != "mqc_about"
                        ):  # Don't remove if it's our about section
                            section.decompose()
                        elif elem.parent and elem.parent.get("id") != "mqc_about":
                            elem.decompose()

                        modifications["citations"] = True
                except Exception as e:
                    self.logger.debug(f"Error with citation selector '{selector}': {e}")

            # 7. Remove welcome sections or replace
            welcome_selectors = ["#mqc_welcome", ".mqc-welcome", "section.welcome"]
            for selector in welcome_selectors:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        # Either replace or remove
                        if elem.name == "section":
                            # Create replacement welcome
                            welcome = soup.new_tag("div")
                            welcome["class"] = "welcome"
                            welcome.append(soup.new_tag("h3"))
                            welcome.h3.string = "Welcome to HyRISE Report"
                            welcome.append(soup.new_tag("p"))
                            welcome.p.string = "This report provides a comprehensive analysis of HIV drug resistance mutations."
                            elem.replace_with(welcome)
                        else:
                            elem.decompose()
                        modifications["welcome"] = True
                except Exception as e:
                    self.logger.debug(f"Error with welcome selector '{selector}': {e}")

            # 8. Replace links - but only specific ones, not GitHub links for HyRISE
            for a_tag in soup.find_all(
                "a", href=lambda href: href and "multiqc.info" in href
            ):
                a_tag["href"] = "https://pypi.org/project/hyrise/"

            # Update other MultiQC URLs that shouldn't point to HyRISE's repo
            for a_tag in soup.find_all("a"):
                if a_tag.get("href") and "github.com/ewels/HyRISE" in a_tag.get("href"):
                    a_tag["href"] = "https://github.com/phac-nml/HyRISE"

            # 9. Update meta tags
            for meta in soup.find_all("meta"):
                if (
                    meta.get("name") == "description"
                    or meta.get("property") == "og:description"
                ):
                    meta["content"] = (
                        "HIV Resistance Interpretation & Scoring Engine report"
                    )

            # Write the modified HTML
            with open(html_path, "w", encoding="utf-8") as file:
                file.write(str(soup))

            # Log what was modified
            modified_items = [k for k, v in modifications.items() if v]
            self.logger.info(
                f"HTML modifications completed. Modified: {', '.join(modified_items)}"
            )

            return True, modifications

        except Exception as e:
            self.logger.error(f"Error modifying HTML: {str(e)}")
            return False, {}

    def post_process_report(
        self, logo_path: Optional[str] = None
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Post-process the MultiQC report to customize it for HyRISE.

        Args:
            logo_path: Optional path to a logo file

        Returns:
            Tuple of (success, modifications_made)
        """
        # Find the report HTML file
        html_file = os.path.join(self.report_dir, "hyrise_resistance_report.html")
        if not os.path.exists(html_file):
            self.logger.error(f"Report HTML file not found at: {html_file}")
            return False, {}

        # Create a backup before modifying
        backup_file = f"{html_file}.backup"
        shutil.copy2(html_file, backup_file)
        self.logger.info(f"Created backup of original report at: {backup_file}")

        # Get logo data URI
        logo_data_uri = self.embed_logo(logo_path)

        # Modify the HTML
        success, modifications = self.modify_html(html_file, logo_data_uri)

        if not success:
            # Restore from backup on failure
            self.logger.warning("HTML modification failed, restoring from backup")
            shutil.copy2(backup_file, html_file)
            return False, {}

        self.logger.info("HTML report successfully customized for HyRISE")
        return True, modifications

    def generate_report(
        self,
        input_data_path: Optional[str] = None,
        logo_path: Optional[str] = None,
        run_multiqc: bool = True,
        skip_html_mod: bool = False,
        use_custom_template: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete process to generate a HyRISE report.

        Args:
            input_data_path: Path to Sierra JSON data (optional)
            logo_path: Path to custom logo file (optional)
            run_multiqc: Whether to run MultiQC
            skip_html_mod: Whether to skip HTML modifications
            use_custom_template: Whether to use custom MultiQC template

        Returns:
            Dict containing results of the report generation process
        """
        results = {
            "config_generated": False,
            "multiqc_run": False,
            "html_modified": False,
            "report_path": None,
            "errors": [],
        }

        # Step 1: Load input data if provided to extract metadata
        if input_data_path and os.path.exists(input_data_path):
            try:
                import json

                with open(input_data_path, "r") as f:
                    data = json.load(f)
                self.metadata_info = self.create_metadata_summary(data)
                self.logger.info(f"Loaded metadata from: {input_data_path}")
            except Exception as e:
                self.logger.error(f"Error loading input data: {str(e)}")
                results["errors"].append(f"Data loading error: {str(e)}")

        # Step 2: Generate config using the metadata we just extracted (or default values)
        try:
            self.generate_config(use_custom_template)
            results["config_generated"] = True
            self.logger.info("MultiQC config generated successfully")
        except Exception as e:
            self.logger.error(f"Error generating config: {str(e)}")
            results["errors"].append(f"Config generation error: {str(e)}")
            return results

        # Step 2: Run MultiQC if requested
        if run_multiqc:
            success, output = self.run_multiqc()
            results["multiqc_run"] = success
            if not success:
                self.logger.error(f"MultiQC error: {output}")
                results["errors"].append(f"MultiQC error: {output}")
                return results

        # Step 3: Post-process the report if requested
        if run_multiqc and not skip_html_mod:
            success, modifications = self.post_process_report(logo_path)
            results["html_modified"] = success
            if not success:
                self.logger.error("HTML modification failed")
                results["errors"].append("HTML modification error")

        # Set the final report path
        html_file = os.path.join(self.report_dir, "hyrise_resistance_report.html")
        if os.path.exists(html_file):
            results["report_path"] = html_file

        return results


def main():
    """Command-line interface for the HyRISE report generator."""
    parser = argparse.ArgumentParser(description="HyRISE MultiQC Report Generator")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input directory containing MultiQC data files",
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output directory for report"
    )
    parser.add_argument("-d", "--data", help="Path to Sierra JSON data file (optional)")
    parser.add_argument("-s", "--sample", help="Sample name for the report")
    parser.add_argument("-e", "--email", help="Contact email for the report")
    parser.add_argument("-l", "--logo", help="Path to custom logo file (PNG or SVG)")
    parser.add_argument(
        "-v", "--version", default="0.1.0", help="HyRISE version number"
    )
    parser.add_argument(
        "--skip-multiqc", action="store_true", help="Skip running MultiQC"
    )
    parser.add_argument(
        "--skip-html-mod", action="store_true", help="Skip HTML modifications"
    )
    parser.add_argument(
        "--use-template", action="store_true", help="Use custom MultiQC template"
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)

    # Initialize the report generator
    generator = HyRISEReportGenerator(
        output_dir=args.output,
        version=args.version,
        sample_name=args.sample,
        contact_email=args.email,
    )

    # Generate the report - now our function will handle the metadata extraction
    results = generator.generate_report(
        input_data_path=args.data,
        logo_path=args.logo,
        run_multiqc=not args.skip_multiqc,
        skip_html_mod=args.skip_html_mod,
        use_custom_template=args.use_template,
    )

    # Print results
    if results["errors"]:
        print("Errors occurred during report generation:")
        for error in results["errors"]:
            print(f"  - {error}")
        return 1

    print("\nReport Generation Summary:")
    print(f"  Config generated: {'Yes' if results['config_generated'] else 'No'}")
    print(f"  MultiQC run: {'Yes' if results['multiqc_run'] else 'No'}")
    print(f"  HTML modified: {'Yes' if results['html_modified'] else 'No'}")

    if results["report_path"]:
        print(f"\nReport is available at: {results['report_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
