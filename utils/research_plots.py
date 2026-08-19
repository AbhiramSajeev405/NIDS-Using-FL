"""
Publication-Quality Research Plots for FL-NIDS.

Generates matplotlib/seaborn figures suitable for academic papers:
  - Convergence curves (accuracy/loss vs round)
  - Bar charts (model × strategy comparisons)
  - Heatmaps (results matrices)
  - Box plots (per-client fairness)
  - Non-IID impact curves (accuracy vs Dirichlet α)
  - Accuracy vs communication cost

All plots use LaTeX-compatible fonts and are saved as PDF + PNG.

Usage:
    from utils.research_plots import PlotGenerator
    pg = PlotGenerator(results_dir="results/")
    pg.plot_convergence(...)
    pg.plot_comparison_bars(...)
"""

import os
import json
import glob
import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


# Publication style defaults
PLOT_STYLE = {
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.figsize': (8, 5),
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
}

# Color palette for strategies
STRATEGY_COLORS = {
    'fedavg': '#2196F3',
    'fedprox': '#4CAF50',
    'fedmedian': '#FF9800',
    'trimmed_mean': '#9C27B0',
    'krum': '#F44336',
    'fednova': '#00BCD4',
    'centralized': '#333333',
}

MODEL_MARKERS = {
    'mlp': 'o',
    'cnn': 's',
    'lstm': '^',
    'resnet': 'D',
    'autoencoder': 'v',
}


class PlotGenerator:
    """Generate publication-quality research plots."""

    def __init__(self, output_dir="results/plots"):
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib is required. Install: pip install matplotlib")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        plt.rcParams.update(PLOT_STYLE)

    def _save(self, fig, name):
        """Save figure as PDF (vector) and PNG (raster)."""
        fig.savefig(os.path.join(self.output_dir, f"{name}.pdf"))
        fig.savefig(os.path.join(self.output_dir, f"{name}.png"))
        plt.close(fig)
        print(f"[Plots] Saved {name}.pdf and {name}.png")

    # -----------------------------------------------------------------
    # 1. Convergence Curves
    # -----------------------------------------------------------------
    def plot_convergence(self, experiments, metric='accuracy', title=None):
        """Plot metric vs round for multiple experiments.

        Args:
            experiments: List of dicts with keys:
                'label': str (e.g., 'FedAvg'),
                'history': list of dicts with 'round'/'epoch' and metric
                'strategy': str (for color)
            metric: Column name to plot ('accuracy', 'loss', 'f1_score')
            title: Optional plot title
        """
        fig, ax = plt.subplots()

        for exp in experiments:
            history = exp['history']
            x = list(range(1, len(history) + 1))
            y = [h.get(metric, 0) for h in history]
            strategy = exp.get('strategy', 'fedavg')
            color = STRATEGY_COLORS.get(strategy, '#888888')
            ax.plot(x, y, label=exp['label'], color=color, linewidth=2, marker='o', markersize=4)

        ax.set_xlabel('Round')
        ax.set_ylabel(metric.replace('_', ' ').title())
        ax.set_title(title or f'{metric.replace("_", " ").title()} vs Round')
        ax.legend(loc='best')
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        self._save(fig, f"convergence_{metric}")

    # -----------------------------------------------------------------
    # 2. Bar Chart Comparison
    # -----------------------------------------------------------------
    def plot_comparison_bars(self, results_df, x_col='strategy', y_col='accuracy',
                             hue_col='model', title=None):
        """Grouped bar chart comparing strategies across models.

        Args:
            results_df: DataFrame with columns for x_col, y_col, hue_col
            x_col: Column for x-axis categories
            y_col: Column for bar heights
            hue_col: Column for grouped bars
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        if HAS_SEABORN:
            sns.barplot(data=results_df, x=x_col, y=y_col, hue=hue_col, ax=ax)
        else:
            # Manual grouped bars
            categories = results_df[x_col].unique()
            hues = results_df[hue_col].unique()
            n_hues = len(hues)
            bar_width = 0.8 / n_hues
            x_pos = np.arange(len(categories))

            for i, hue in enumerate(hues):
                vals = [results_df[(results_df[x_col] == c) & (results_df[hue_col] == hue)][y_col].mean()
                        for c in categories]
                ax.bar(x_pos + i * bar_width, vals, bar_width, label=hue)

            ax.set_xticks(x_pos + bar_width * (n_hues - 1) / 2)
            ax.set_xticklabels(categories)
            ax.legend()

        ax.set_xlabel(x_col.replace('_', ' ').title())
        ax.set_ylabel(y_col.replace('_', ' ').title())
        ax.set_title(title or f'{y_col.replace("_", " ").title()} by {x_col.replace("_", " ").title()}')

        self._save(fig, f"comparison_{y_col}_by_{x_col}")

    # -----------------------------------------------------------------
    # 3. Heatmap
    # -----------------------------------------------------------------
    def plot_heatmap(self, results_df, row_col='model', col_col='strategy',
                      val_col='accuracy', title=None, fmt='.3f'):
        """Heatmap of results matrix (e.g., model × strategy).

        Args:
            results_df: DataFrame with row, col, and value columns
            row_col, col_col: Columns for rows/columns of the heatmap
            val_col: Column for cell values
        """
        pivot = results_df.pivot_table(index=row_col, columns=col_col, values=val_col, aggfunc='mean')

        fig, ax = plt.subplots(figsize=(max(8, len(pivot.columns) * 1.5), max(4, len(pivot) * 1.2)))

        if HAS_SEABORN:
            sns.heatmap(pivot, annot=True, fmt=fmt, cmap='YlOrRd', ax=ax,
                        linewidths=0.5, vmin=0, vmax=1 if 'accuracy' in val_col else None)
        else:
            im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
            for i in range(len(pivot)):
                for j in range(len(pivot.columns)):
                    ax.text(j, i, f"{pivot.values[i, j]:{fmt}}", ha='center', va='center')
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels(pivot.columns)
            ax.set_yticks(range(len(pivot)))
            ax.set_yticklabels(pivot.index)
            plt.colorbar(im, ax=ax)

        ax.set_title(title or f'{val_col.replace("_", " ").title()}: {row_col} × {col_col}')

        self._save(fig, f"heatmap_{val_col}_{row_col}_x_{col_col}")

    # -----------------------------------------------------------------
    # 4. Box Plots (Fairness)
    # -----------------------------------------------------------------
    def plot_fairness_boxplot(self, client_metrics, group_col='strategy',
                               metric='accuracy', title=None):
        """Box plot showing per-client metric distribution.

        Shows variance across clients — lower spread = more fair.

        Args:
            client_metrics: DataFrame with per-client rows, columns:
                'client_id', 'strategy', 'accuracy', etc.
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        if HAS_SEABORN:
            sns.boxplot(data=client_metrics, x=group_col, y=metric, ax=ax)
            sns.stripplot(data=client_metrics, x=group_col, y=metric, ax=ax,
                         color='black', alpha=0.5, size=4)
        else:
            groups = client_metrics[group_col].unique()
            data_to_plot = [client_metrics[client_metrics[group_col] == g][metric].values for g in groups]
            ax.boxplot(data_to_plot, labels=groups)

        ax.set_xlabel(group_col.replace('_', ' ').title())
        ax.set_ylabel(metric.replace('_', ' ').title())
        ax.set_title(title or f'Per-Client {metric.title()} Distribution (Fairness)')

        self._save(fig, f"fairness_{metric}_by_{group_col}")

    # -----------------------------------------------------------------
    # 5. Non-IID Impact
    # -----------------------------------------------------------------
    def plot_noniid_impact(self, alpha_results, metric='accuracy', title=None):
        """Plot accuracy vs Dirichlet α for different strategies.

        Args:
            alpha_results: List of dicts:
                {'strategy': str, 'alpha': float, metric: float}
        """
        df = pd.DataFrame(alpha_results)
        fig, ax = plt.subplots()

        for strategy in df['strategy'].unique():
            subset = df[df['strategy'] == strategy].sort_values('alpha')
            color = STRATEGY_COLORS.get(strategy, '#888888')
            ax.plot(subset['alpha'], subset[metric], label=strategy, color=color,
                    linewidth=2, marker='o', markersize=6)

        ax.set_xlabel('Dirichlet α (lower = more Non-IID)')
        ax.set_ylabel(metric.replace('_', ' ').title())
        ax.set_xscale('log')
        ax.set_title(title or f'{metric.title()} vs Data Heterogeneity')
        ax.legend()
        ax.invert_xaxis()  # Low alpha (more Non-IID) on the right

        self._save(fig, f"noniid_impact_{metric}")

    # -----------------------------------------------------------------
    # 6. Communication Cost vs Accuracy
    # -----------------------------------------------------------------
    def plot_comm_vs_accuracy(self, results, title=None):
        """Scatter plot of accuracy vs total communication cost.

        Args:
            results: List of dicts:
                {'strategy': str, 'model': str, 'accuracy': float, 'comm_bytes': int}
        """
        df = pd.DataFrame(results)
        fig, ax = plt.subplots()

        for strategy in df['strategy'].unique():
            subset = df[df['strategy'] == strategy]
            color = STRATEGY_COLORS.get(strategy, '#888888')
            for _, row in subset.iterrows():
                marker = MODEL_MARKERS.get(row.get('model', 'mlp'), 'o')
                ax.scatter(row['comm_bytes'] / 1e6, row['accuracy'],
                          color=color, marker=marker, s=100, edgecolors='black', linewidth=0.5)

            # Add strategy label once
            ax.scatter([], [], color=color, label=strategy, s=60)

        ax.set_xlabel('Communication Cost (MB)')
        ax.set_ylabel('Accuracy')
        ax.set_title(title or 'Accuracy vs Communication Budget')
        ax.legend()

        self._save(fig, "comm_vs_accuracy")

    # -----------------------------------------------------------------
    # Utility: Load experiment results from directory
    # -----------------------------------------------------------------
    def load_results(self, results_base_dir):
        """Load all experiment results into a DataFrame."""
        all_results = []
        for exp_id in os.listdir(results_base_dir):
            exp_dir = os.path.join(results_base_dir, exp_id)
            config_path = os.path.join(exp_dir, "config.json")
            if not os.path.exists(config_path):
                continue

            with open(config_path, 'r') as f:
                config = json.load(f)

            result = {
                'experiment_id': exp_id,
                'model': config.get('model_type', '?'),
                'strategy': config.get('federated', {}).get('strategy', '?'),
                'distribution': config.get('data', {}).get('distribution', '?'),
                'alpha': config.get('data', {}).get('dirichlet_alpha', 'N/A'),
            }

            # Load metrics if available
            metrics_dir = os.path.join(exp_dir, "metrics")
            if os.path.exists(metrics_dir):
                csvs = [f for f in os.listdir(metrics_dir) if f.endswith('.csv')]
                if csvs:
                    mdf = pd.read_csv(os.path.join(metrics_dir, csvs[-1]))
                    for col in ['accuracy', 'f1_score', 'detection_rate', 'false_positive_rate']:
                        if col in mdf.columns:
                            result[col] = mdf[col].mean()

            all_results.append(result)

        return pd.DataFrame(all_results)
