#!/usr/bin/env python3
import os
import sys
import json
import statistics
from collections import defaultdict

def analyze_results(res_dir):
    stats = defaultdict(lambda: {"count": 0, "times": []})

    for fname in os.listdir(res_dir):
        if not fname.endswith(".json"):
            continue
        try:
            version, presolve, seed, n_with_ext = fname.split("_")
            n = int(n_with_ext.replace(".json", ""))
        except ValueError:
            # Non-compliant file name
            version, presolve, seed, n_with_ext = "", "", "", ""
            continue

        path = os.path.join(res_dir, fname)
        with open(path, "r") as f:
            data = json.load(f)

        for _, result in data.items():
            time_val = result.get("time", None)
            if time_val is not None and time_val != 300:
                key = (n, presolve, version)
                stats[key]["count"] += 1
                stats[key]["times"].append(time_val)

    # Compute statistics
    report = {}
    for key, vals in stats.items():
        n, presolve, version = key
        if vals["times"]:
            mean_time = statistics.mean(vals["times"])
            min_time = min(vals["times"])
            max_time = max(vals["times"])
        else:
            mean_time = min_time = max_time = None
        report[key] = {
            "count": vals["count"],
            "mean": mean_time,
            "min": min_time,
            "max": max_time
        }
    return report

def print_table(report, warm_start, objective):
    # Desired orders
    version_order = {"base": 0, "i<j": 1}
    presolve_order = {"True": 0, "False": 1}  # note: presolve comes as a string

    def sort_key(item):
        (n, presolve, version), _ = item
        v_rank = version_order.get(version, 99)     # 99 if not found
        p_rank = presolve_order.get(presolve, 99)  # same
        return (v_rank, p_rank, n)

    # Meta-header
    print(f"Warm_start: {warm_start} | Objective: {objective}")
    header = f"{'n':<5} {'presolve':<10} {'version':<10} {'mean':<10} {'min':<10} {'max':<10} {'count':<7}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for (n, presolve, version), vals in sorted(report.items(), key=sort_key):
        mean_str = f"{vals['mean']:.2f}" if vals['mean'] is not None else "-"
        min_str = f"{vals['min']:.2f}" if vals['min'] is not None else "-"
        max_str = f"{vals['max']:.2f}" if vals['max'] is not None else "-"
        print(f"{n:<5} {presolve:<10} {version:<10} {mean_str:<10} {min_str:<10} {max_str:<10}  {vals['count']}")

    print("-" * len(header))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <results_folder>")
        sys.exit(1)

    res_dir = sys.argv[1]
    if not os.path.isdir(res_dir):
        print(f"Error: {res_dir} is not a valid folder.")
        sys.exit(1)

    # Extract warm_start and objective from the last part of the path
    last_part = os.path.basename(os.path.normpath(res_dir))
    if "_" in last_part:
        warm_start, objective = last_part.split("_", 1)
    else:
        warm_start, objective = last_part, "unknown"

    report = analyze_results(res_dir)
    if report:
        print_table(report, warm_start, objective)
    else:
        print("No valid results found.")
        print_table(report, warm_start, objective)
