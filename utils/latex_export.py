"""
LaTeX Table Exporter for FL-NIDS Research.

Converts experiment results into publication-ready LaTeX tables
that can be pasted directly into a paper.

Usage:
    from utils.latex_export import results_to_latex
    latex = results_to_latex(results_df, row='model', col='strategy', val='accuracy')
    print(latex)
"""

import pandas as pd
import numpy as np


def results_to_latex(df, row_col='model', col_col='strategy', val_col='accuracy',
                      caption=None, label=None, fmt='.4f', bold_best=True):
    """Convert a results DataFrame into a LaTeX table string.

    Args:
        df: DataFrame with columns for row_col, col_col, val_col
        row_col: Column for table rows
        col_col: Column for table columns
        val_col: Column for cell values
        caption: LaTeX table caption
        label: LaTeX table label (for \\ref{})
        fmt: Number format string
        bold_best: If True, bold the best value in each row

    Returns:
        String containing LaTeX table code
    """
    pivot = df.pivot_table(index=row_col, columns=col_col, values=val_col, aggfunc='mean')

    # Also compute std if there are multiple values per cell
    pivot_std = df.pivot_table(index=row_col, columns=col_col, values=val_col, aggfunc='std')

    has_std = not pivot_std.isna().all().all()

    # Build LaTeX
    cols = pivot.columns.tolist()
    n_cols = len(cols)

    lines = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")

    if caption:
        lines.append(f"\\caption{{{caption}}}")
    if label:
        lines.append(f"\\label{{{label}}}")

    col_fmt = "l" + "c" * n_cols
    lines.append(f"\\begin{{tabular}}{{{col_fmt}}}")
    lines.append("\\toprule")

    # Header row
    header = f"\\textbf{{{row_col.title()}}}"
    for c in cols:
        header += f" & \\textbf{{{c}}}"
    header += " \\\\"
    lines.append(header)
    lines.append("\\midrule")

    # Data rows
    for row_name in pivot.index:
        row_vals = pivot.loc[row_name]
        best_val = row_vals.max() if 'accuracy' in val_col or 'f1' in val_col else row_vals.min()

        parts = [str(row_name)]
        for c in cols:
            val = row_vals[c]
            if pd.isna(val):
                parts.append("---")
                continue

            if has_std:
                std = pivot_std.loc[row_name, c]
                if pd.isna(std) or std == 0:
                    cell = f"{val:{fmt}}"
                else:
                    cell = f"{val:{fmt}} $\\pm$ {std:{fmt}}"
            else:
                cell = f"{val:{fmt}}"

            if bold_best and val == best_val:
                cell = f"\\textbf{{{cell}}}"

            parts.append(cell)

        lines.append(" & ".join(parts) + " \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    return "\n".join(lines)


def multi_metric_table(df, row_col='model', col_col='strategy',
                        metrics=None, caption=None, label=None):
    """Generate a multi-metric LaTeX table.

    Each cell shows multiple metrics stacked.

    Args:
        df: Results DataFrame
        row_col, col_col: Row and column identifiers
        metrics: List of metric column names (default: accuracy, f1)
        caption, label: LaTeX table metadata

    Returns:
        LaTeX table string
    """
    if metrics is None:
        metrics = ['accuracy', 'f1_score']

    cols = df[col_col].unique().tolist()
    rows = df[row_col].unique().tolist()

    lines = []
    lines.append("\\begin{table*}[htbp]")
    lines.append("\\centering")
    lines.append("\\small")

    if caption:
        lines.append(f"\\caption{{{caption}}}")
    if label:
        lines.append(f"\\label{{{label}}}")

    n_cols = len(cols)
    col_fmt = "l" + "c" * n_cols
    lines.append(f"\\begin{{tabular}}{{{col_fmt}}}")
    lines.append("\\toprule")

    # Header
    header = f"\\textbf{{{row_col.title()}}}"
    for c in cols:
        header += f" & \\textbf{{{c}}}"
    header += " \\\\"
    lines.append(header)
    lines.append("\\midrule")

    # Data rows
    for row_name in rows:
        parts = [str(row_name)]
        for c in cols:
            subset = df[(df[row_col] == row_name) & (df[col_col] == c)]
            if subset.empty:
                parts.append("---")
                continue

            cell_parts = []
            for m in metrics:
                if m in subset.columns:
                    mean = subset[m].mean()
                    std = subset[m].std()
                    if pd.isna(std) or std == 0:
                        cell_parts.append(f"{mean:.3f}")
                    else:
                        cell_parts.append(f"{mean:.3f}$\\pm${std:.3f}")
                else:
                    cell_parts.append("---")

            parts.append(" / ".join(cell_parts))

        lines.append(" & ".join(parts) + " \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")

    # Add footnote explaining metrics
    metric_names = [m.replace('_', ' ').title() for m in metrics]
    lines.append(f"\\\\\\footnotesize{{Metrics: {' / '.join(metric_names)}}}")
    lines.append("\\end{table*}")

    return "\n".join(lines)


def save_latex(latex_str, output_path):
    """Save LaTeX string to a .tex file."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(latex_str)
    print(f"[LaTeX] Saved to {output_path}")
