#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from version import __version__

def load_json(path):
    """Load a JSON file"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_tsv(path):
    """
    Read a TSV file and return a list of KO numbers from the first column.
    Skip any empty lines.
    """
    ids = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ko = line.split('\t')[0]
            ids.append(ko)
    return ids

def evaluate(defn, ids):
    """
    Recursively evaluate a definition object and return whether the ids (list of KO IDs) satisfy it.
    The defn['type'] is one of "all_of", "one_of", or "at_least".
    """
    t = defn.get("type")
    # Leaf node: when `id_list` is present
    if "id_list" in defn:
        id_list = defn["id_list"]
        if t == "all_of":
            return all(k in ids for k in id_list)
        elif t == "one_of":
            return any(k in ids for k in id_list)
        elif t == "at_least":
            required = defn.get("min", len(id_list))
            return sum(1 for k in id_list if k in ids) >= required
        else:
            raise ValueError(f"Unknown leaf type: {t}")

    # Composite node: evaluate the elements under `list`
    subs = defn.get("list", [])
    if t == "all_of":
        return all(evaluate(sub, ids) for sub in subs)
    elif t == "one_of":
        return any(evaluate(sub, ids) for sub in subs)
    elif t == "at_least":
        required = defn.get("min", len(subs))
        return sum(1 for sub in subs if evaluate(sub, ids)) >= required
    else:
        raise ValueError(f"Unknown composite type: {t}")

def main(def_file_path, input_file_path, output_file_path):
    # Check that definitions JSON exists
    if not os.path.isfile(def_file_path):
        print(f"Error: Definition file '{def_file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    # Check that input TSV exists
    if not os.path.isfile(input_file_path):
        print(f"Error: Input file '{input_file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    # Check that output directory exists and is writable
    out_dir = os.path.dirname(output_file_path) or '.'
    if not os.path.isdir(out_dir):
        print(f"Error: Output directory '{out_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not os.access(out_dir, os.W_OK):
        print(f"Error: No write permission in output directory '{out_dir}'.", file=sys.stderr)
        sys.exit(1)

    # Load difitition file
    try:
        definitions = load_json(def_file_path)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in '{def_file_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error: Cannot open JSON file '{def_file_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Load input TSV file
    try:
        input_ids = load_tsv(input_file_path)
    except IOError as e:
        print(f"Error: Cannot open TSV file '{input_file_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Write results to the output file in TSV format
    with open(output_file_path, 'w', encoding='utf-8') as out:
        for pw in definitions.get("pathway_list", []):
            name = pw.get("pathway_name")
            ok = evaluate(pw.get("definition", {}), input_ids)
            mark = "Y" if ok else "N"
            out.write(f"{name}\t{mark}\n")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == '--version':
        print(f"predict_pathways.py {__version__}")
        sys.exit(0)
    if len(sys.argv) != 4:
        print("Usage: python3 ./app/predict_pathways.py ./definitions/kegg_key_enzymes.json ./test/sample.tsv ./output/sample.out", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
