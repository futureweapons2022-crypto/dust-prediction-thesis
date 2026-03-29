"""
Master QA/QC Report Generator
===============================
Runs all dataset-specific QA/QC scripts and produces a unified report.
Outputs: data/qaqc_report.txt

Usage: python scripts/qaqc_report.py
"""

import os
import sys
from datetime import datetime
from io import StringIO

# Ensure scripts directory is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
OUT_DIR = os.path.join(BASE_DIR, "data")


def capture_output(func):
    """Run a function and capture its stdout output."""
    old_stdout = sys.stdout
    sys.stdout = buffer = StringIO()
    try:
        result = func()
    except Exception as e:
        result = ([], [f"Script crashed: {e}"], False)
    sys.stdout = old_stdout
    return result, buffer.getvalue()


def main():
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  THESIS DATA — QA/QC MASTER REPORT")
    report_lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 70)

    checklist = {}
    all_outputs = {}

    # --- CAMS ---
    print("Running CAMS QA/QC...")
    try:
        from qaqc_cams import run_cams_qaqc
        (results, issues, passed), output = capture_output(run_cams_qaqc)
        checklist["CAMS"] = passed
        all_outputs["CAMS"] = output
        if issues:
            checklist["CAMS_issues"] = issues
    except Exception as e:
        checklist["CAMS"] = False
        all_outputs["CAMS"] = f"ERROR: {e}"
        checklist["CAMS_issues"] = [str(e)]
    print(f"  CAMS: {'PASS' if checklist['CAMS'] else 'FAIL'}")

    # --- AERONET ---
    print("Running AERONET QA/QC...")
    try:
        from qaqc_aeronet import run_aeronet_qaqc
        (results, issues, passed), output = capture_output(run_aeronet_qaqc)
        checklist["AERONET"] = passed
        all_outputs["AERONET"] = output
        if issues:
            checklist["AERONET_issues"] = issues
    except Exception as e:
        checklist["AERONET"] = False
        all_outputs["AERONET"] = f"ERROR: {e}"
        checklist["AERONET_issues"] = [str(e)]
    print(f"  AERONET: {'PASS' if checklist['AERONET'] else 'FAIL'}")

    # --- CMIP6 ---
    print("Running CMIP6 QA/QC...")
    try:
        from qaqc_cmip6 import run_cmip6_qaqc
        (results, issues, passed), output = capture_output(run_cmip6_qaqc)
        checklist["CMIP6"] = passed
        all_outputs["CMIP6"] = output
        if issues:
            checklist["CMIP6_issues"] = issues
    except Exception as e:
        checklist["CMIP6"] = False
        all_outputs["CMIP6"] = f"ERROR: {e}"
        checklist["CMIP6_issues"] = [str(e)]
    print(f"  CMIP6: {'PASS' if checklist['CMIP6'] else 'FAIL'}")

    # --- ERA5 (skipped) ---
    checklist["ERA5"] = None  # Not yet available
    all_outputs["ERA5"] = "SKIPPED — ERA5 data still downloading. Run qaqc_era5.py when ready."

    # === Build Report ===

    # Checklist
    report_lines.append("")
    report_lines.append("PASS/FAIL CHECKLIST")
    report_lines.append("-" * 40)
    for dataset in ["CAMS", "AERONET", "CMIP6", "ERA5"]:
        status = checklist.get(dataset)
        if status is None:
            mark = "[ SKIP ]"
        elif status:
            mark = "[ PASS ]"
        else:
            mark = "[ FAIL ]"
        report_lines.append(f"  {mark}  {dataset}")
    report_lines.append("")

    # Issues requiring attention
    any_issues = False
    for dataset in ["CAMS", "AERONET", "CMIP6"]:
        issues = checklist.get(f"{dataset}_issues", [])
        if issues:
            if not any_issues:
                report_lines.append("ISSUES REQUIRING ATTENTION")
                report_lines.append("-" * 40)
                any_issues = True
            report_lines.append(f"\n  {dataset}:")
            for issue in issues:
                report_lines.append(f"    {issue}")

    if not any_issues:
        report_lines.append("No issues found across any dataset.")

    # Detailed output per dataset
    for dataset in ["CAMS", "AERONET", "CMIP6", "ERA5"]:
        report_lines.append("")
        report_lines.append("=" * 70)
        report_lines.append(f"  DETAILED: {dataset}")
        report_lines.append("=" * 70)
        report_lines.append(all_outputs.get(dataset, "No output"))

    # Write report
    report_path = os.path.join(OUT_DIR, "qaqc_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\nReport written to: {report_path}")

    # Overall result
    datasets_checked = [v for k, v in checklist.items()
                        if not k.endswith("_issues") and v is not None]
    overall = all(datasets_checked) if datasets_checked else False
    print(f"\nOverall: {'ALL PASS' if overall else 'ISSUES FOUND — see report'}")
    return overall


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed else 1)
