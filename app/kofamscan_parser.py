#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from dataclasses import dataclass
from typing import Dict, List, Set
from version import __version__


@dataclass
class Row:
    """Data class representing a hit row information"""
    asterisk: bool
    original_columns: List[str]
    ko: str
    gene: str
    thrshld: float
    score: float


def group_by_genes(result: str):
    """Parse TSV file content and convert to data structure."""
    gene_data: Dict[str, List[Row]] = {}

    for line in result.splitlines():
        line = line.rstrip()

        # Save the first comment line as header if it exists
        if line.startswith('#'):
            continue

        # Skip empty lines
        if not line:
            continue

        columns = line.split('\t')
        if len(columns) < 7:
            continue

        # Parse columns
        asterisk_mark = columns[0] == '*'
        gene = columns[1]
        ko = columns[2]
        # Handle empty thrshld/score (some KOs have no threshold defined)
        thrshld = float(columns[3]) if columns[3] else 0.0
        score = float(columns[4]) if columns[4] else 0.0

        # Save hits by gene
        if gene not in gene_data:
            gene_data[gene] = []

        hit = Row(
            asterisk=asterisk_mark,
            original_columns=columns,
            ko=ko,
            gene=gene,
            thrshld=thrshld,
            score=score
        )
        gene_data[gene].append(hit)
    
    return gene_data


def determine_selected_indices(hits: List[Row], top_n: int, min_score_ratio: float = None):
    """
    Determine which hit indices should be selected for KO output.
    Returns set of indices that should be selected.

    If min_score_ratio is specified, hits without asterisk are only selected
    if score/thrshld >= min_score_ratio.
    """
    selected_indices = set()
    has_asterisk = any(hit.asterisk for hit in hits)

    for index, hit in enumerate(hits):
        # Ratio check: if min_score_ratio is specified, check score/thrshld ratio
        if min_score_ratio is not None and hit.thrshld > 0:
            passes_ratio_check = (hit.score / hit.thrshld) >= min_score_ratio
        else:
            passes_ratio_check = True  # No filtering if not specified or thrshld is 0

        # Mark as selected if: has asterisk OR (no asterisk in gene and within top_n and passes ratio check)
        if hit.asterisk or (not has_asterisk and index < top_n and passes_ratio_check):
            selected_indices.add(index)

    return selected_indices


def format_detail_output(gene_data: Dict[str, List[Row]], top_n: int, detail_top: int, min_score_ratio: float = None):
    """
    Generate output lines for detail mode.
    Output the Top N results specified by the detail_top argument, and mark selected KO numbers with 'Y' in the hit column.
    """
    output_lines = []

    # Write header
    output_lines.append("hit\trank\tasterisk_mark\tgene\tKO\tthreshold\tscore\te_value\tKO_definition")

    # Process each gene
    for i, (gene, hits) in enumerate(gene_data.items()):

        # Add separator line between genes (except before the first gene)
        if i > 0:
            output_lines.append('-' * 100)

        # Use common function to determine which rows would be selected
        selected_indices = determine_selected_indices(hits, top_n, min_score_ratio)

        # Output hits up to detail_top
        for index, hit in enumerate(hits):
            if index < detail_top or hit.asterisk:
                original_rank = index + 1
                # Mark with 'Y' if this row would be selected for KO output
                hit_mark = 'Y' if index in selected_indices else ''
                asterisk_mark = '*' if hit.asterisk else ''
                
                # Output: rank, hit mark, asterisk_mark, then all original columns except the first one
                cols_str = '\t'.join(hit.original_columns[1:])
                output_lines.append(f"{hit_mark}\t{original_rank}\t{asterisk_mark}\t{cols_str}")

    return output_lines


def format_ko_output(gene_data: Dict[str, List[Row]], top_n: int, min_score_ratio: float = None):
    """Generate output lines for KO-only mode."""
    unique_kos: Set[str] = set()

    # Process each gene
    for gene_name, hits in gene_data.items():
        # Use common function to determine which rows to select
        selected_indices = determine_selected_indices(hits, top_n, min_score_ratio)

        # Add KOs from selected indices
        for index in selected_indices:
            if index < len(hits):
                unique_kos.add(hits[index].ko)

    # Return sorted unique KOs
    return sorted(unique_kos)


def format_gene_output(gene_data: Dict[str, List[Row]], top_n: int, min_score_ratio: float = None):
    """Generate output lines for gene mode with detailed hit information."""
    output_lines = []

    # Write header
    output_lines.append("KO\tgene name\tthrshld\tscore\tE-value\tmark")

    # Process each gene
    for gene_name, hits in gene_data.items():
        # Use common function to determine which rows to select
        selected_indices = determine_selected_indices(hits, top_n, min_score_ratio)

        # Output selected hits
        for index in selected_indices:
            if index < len(hits):
                hit = hits[index]
                # Extract relevant columns from original data
                # columns[0] = asterisk mark, columns[1] = gene, columns[2] = KO
                # columns[3] = thrshld, columns[4] = score, columns[5] = E-value
                cols = hit.original_columns
                ko = cols[2]
                gene = cols[1]
                thrshld = cols[3] if len(cols) > 3 else ''
                score = cols[4] if len(cols) > 4 else ''
                e_value = cols[5] if len(cols) > 5 else ''
                mark = '*' if hit.asterisk else ''

                output_lines.append(f"{ko}\t{gene}\t{thrshld}\t{score}\t{e_value}\t{mark}")

    return output_lines


def load_tsv(file_path: str):
    """Read a TSV file and return its content as string."""
    with open(file_path, 'r') as file:
        return file.read()


def generate_output_filename(base_file: str, suffix: str) -> str:
    """Generate output filename by adding suffix before the extension."""
    if '.' in os.path.basename(base_file):
        name, ext = os.path.splitext(base_file)
        return f"{name}_{suffix}{ext}"
    else:
        return f"{base_file}_{suffix}"


def parse_kofamscan_result_file(input_file: str, output_file: str, top_n: int = 1, min_score_ratio: float = None):
    """Parse the KofamScan result file and output three files: KO list, gene details, and detail view"""
    # Load input KofamScan result file
    kofamscan_results = load_tsv(input_file)

    # Parse KofamScan results and group by genes
    gene_data = group_by_genes(kofamscan_results)

    # Generate output filenames
    gene_output_file = generate_output_filename(output_file, "gene")
    detail_output_file = generate_output_filename(output_file, "detail")

    # Output 1: KO list only (default)
    ko_lines = format_ko_output(gene_data, top_n, min_score_ratio)
    with open(output_file, 'w', encoding='utf-8') as out:
        if ko_lines:
            out.write('\n'.join(ko_lines))

    # Output 2: Gene details
    gene_lines = format_gene_output(gene_data, top_n, min_score_ratio)
    with open(gene_output_file, 'w', encoding='utf-8') as out:
        if gene_lines:
            out.write('\n'.join(gene_lines))

    # Output 3: Detail view (detail_top is fixed at 10)
    detail_lines = format_detail_output(gene_data, top_n, detail_top=10, min_score_ratio=min_score_ratio)
    with open(detail_output_file, 'w', encoding='utf-8') as out:
        if detail_lines:
            out.write('\n'.join(detail_lines))


def main():
    """Main function to process a Kofamscan result file."""
    parser = argparse.ArgumentParser(
        description='Process Kofamscan result TSV files and extract hits KO numbers.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('input_file', 
                        help='Path to the input TSV file')
    parser.add_argument('output_file', 
                        help='Path to the output TSV file')
    parser.add_argument('--top',
                        type=int,
                        default=1,
                        help='Number of top hits to select for KO extraction (default: 1, selected only if no line is marked with an asterisk)')
    parser.add_argument('--min-score-ratio',
                        type=float,
                        default=None,
                        help='Minimum score/threshold ratio (0 < ratio < 1) for selecting hits without asterisk. If not specified, no ratio filtering is applied.')
    parser.add_argument('--version',
                        action='version',
                        version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    # Validate min_score_ratio range
    if args.min_score_ratio is not None:
        if not (0 < args.min_score_ratio < 1):
            print("Error: --min-score-ratio must be greater than 0 and less than 1", file=sys.stderr)
            sys.exit(1)
    
    # Check that input TSV exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist")
        sys.exit(1)
    
    # Check that output directory exists and is writable
    out_dir = os.path.dirname(args.output_file) or '.'
    if not os.path.isdir(out_dir):
        print(f"Error: Output directory '{out_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not os.access(out_dir, os.W_OK):
        print(f"Error: No write permission in output directory '{out_dir}'.", file=sys.stderr)
        sys.exit(1)
    
    # Parse the KofamScan result file and output three files
    parse_kofamscan_result_file(args.input_file, args.output_file, args.top, args.min_score_ratio)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ./kofamscan_parser.py ./example/kofamscan_result.tsv ./example/ko_list.tsv", file=sys.stderr)
        sys.exit(1)
    main()