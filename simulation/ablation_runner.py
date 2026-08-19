"""
Ablation Study Runner for FL-NIDS.

Generates experiment configurations by systematically varying one
parameter at a time (or a grid of parameters), then runs all
experiments and collects results for comparison.

Usage:
    python simulation/ablation_runner.py --config config/local_test_config.yaml

Or programmatic usage:
    runner = AblationRunner(base_config)
    runner.add_axis('model_type', ['mlp', 'cnn', 'lstm', 'resnet'])
    runner.add_axis('federated.strategy', ['fedavg', 'fedprox', 'fedmedian', 'krum'])
    configs = runner.generate_configs()
"""

import os
import sys
import copy
import json
import yaml
import itertools
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _set_nested(d, key_path, value):
    """Set a value in a nested dict using dot-separated key path.

    e.g., _set_nested(d, 'federated.strategy', 'krum')
    """
    keys = key_path.split('.')
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _get_nested(d, key_path, default=None):
    """Get a value from a nested dict using dot-separated key path."""
    keys = key_path.split('.')
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


class AblationRunner:
    """Generate and manage ablation study configurations."""

    def __init__(self, base_config):
        """
        Args:
            base_config: Base config dict (all parameters at default values)
        """
        self.base_config = copy.deepcopy(base_config)
        self.axes = []  # List of (param_path, values) tuples

    def add_axis(self, param_path, values, name=None):
        """Add an ablation axis (parameter to vary).

        Args:
            param_path: Dot-separated config key (e.g., 'federated.strategy')
            values: List of values to try for this parameter
            name: Human-readable name (default: param_path)
        """
        self.axes.append({
            'param_path': param_path,
            'values': values,
            'name': name or param_path.split('.')[-1],
        })

    def generate_single_axis_configs(self):
        """Generate configs varying one parameter at a time (ablation).

        Returns:
            List of (description, config) tuples
        """
        configs = []

        # Baseline
        configs.append(("baseline", copy.deepcopy(self.base_config)))

        for axis in self.axes:
            base_val = _get_nested(self.base_config, axis['param_path'])
            for val in axis['values']:
                if val == base_val:
                    continue  # Skip the baseline value
                cfg = copy.deepcopy(self.base_config)
                _set_nested(cfg, axis['param_path'], val)

                desc = f"{axis['name']}={val}"
                cfg.setdefault('experiment', {})['name'] = f"ablation_{desc}"
                configs.append((desc, cfg))

        return configs

    def generate_grid_configs(self, axes_indices=None):
        """Generate full grid of all parameter combinations.

        Args:
            axes_indices: Optional list of axis indices to include.
                Default: all axes.

        Returns:
            List of (description, config) tuples
        """
        if axes_indices is None:
            selected_axes = self.axes
        else:
            selected_axes = [self.axes[i] for i in axes_indices]

        all_values = [axis['values'] for axis in selected_axes]
        all_names = [axis['name'] for axis in selected_axes]
        all_paths = [axis['param_path'] for axis in selected_axes]

        configs = []
        for combo in itertools.product(*all_values):
            cfg = copy.deepcopy(self.base_config)
            desc_parts = []
            for path, name, val in zip(all_paths, all_names, combo):
                _set_nested(cfg, path, val)
                desc_parts.append(f"{name}={val}")

            desc = "_".join(desc_parts)
            cfg.setdefault('experiment', {})['name'] = f"grid_{desc}"
            configs.append((desc, cfg))

        return configs

    def generate_seed_variants(self, config, seeds):
        """Generate variants of a config with different seeds.

        Args:
            config: Base config tuple (description, config_dict)
            seeds: List of seed values

        Returns:
            List of (description, config) tuples
        """
        desc, cfg = config
        variants = []
        for seed in seeds:
            cfg_copy = copy.deepcopy(cfg)
            cfg_copy.setdefault('experiment', {})['seed'] = seed
            variants.append((f"{desc}_seed{seed}", cfg_copy))
        return variants

    def save_configs(self, configs, output_dir=None):
        """Save all generated configs to YAML files.

        Args:
            configs: List of (description, config) tuples
            output_dir: Directory to save configs

        Returns:
            List of saved file paths
        """
        if output_dir is None:
            output_dir = os.path.join(_PROJECT_ROOT, "configs", "ablation")
        os.makedirs(output_dir, exist_ok=True)

        paths = []
        for desc, cfg in configs:
            filename = f"{desc}.yaml".replace(" ", "_").replace("=", "_")
            path = os.path.join(output_dir, filename)
            with open(path, 'w') as f:
                yaml.dump(cfg, f, default_flow_style=False)
            paths.append(path)

        print(f"[Ablation] Saved {len(paths)} configs to {output_dir}/")
        return paths

    def print_summary(self, configs):
        """Print a summary of all generated configs."""
        print("\n" + "=" * 60)
        print(f"ABLATION STUDY: {len(configs)} configurations")
        print("=" * 60)
        for i, (desc, cfg) in enumerate(configs):
            parts = []
            for axis in self.axes:
                val = _get_nested(cfg, axis['param_path'])
                parts.append(f"{axis['name']}={val}")
            seed = _get_nested(cfg, 'experiment.seed', '?')
            print(f"  [{i+1:3d}] {desc:40s}  seed={seed}")
        print("=" * 60)


def create_standard_ablation(base_config):
    """Create a standard ablation study for FL-NIDS research.

    Varies: models, strategies, Non-IID levels, and seeds.

    Returns:
        AblationRunner with pre-configured axes
    """
    runner = AblationRunner(base_config)

    runner.add_axis('model_type', ['mlp', 'cnn', 'lstm', 'resnet'], name='model')
    runner.add_axis('federated.strategy',
                    ['fedavg', 'fedprox', 'fedmedian', 'trimmed_mean', 'krum', 'fednova'],
                    name='strategy')
    runner.add_axis('data.distribution', ['iid', 'non_iid'], name='distribution')
    runner.add_axis('data.dirichlet_alpha', [0.1, 0.5, 1.0], name='alpha')

    return runner


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ablation Study Config Generator")
    parser.add_argument("--config", type=str, default="config/local_test_config.yaml",
                        help="Base config file")
    parser.add_argument("--mode", type=str, default="ablation",
                        choices=["ablation", "grid"],
                        help="ablation = vary one at a time, grid = full combo")
    parser.add_argument("--seeds", type=int, nargs='+', default=[42, 123, 456],
                        help="Random seeds for each config")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        base_config = yaml.safe_load(f)

    runner = create_standard_ablation(base_config)

    if args.mode == "ablation":
        configs = runner.generate_single_axis_configs()
    else:
        # Grid over model × strategy (the core comparison table)
        configs = runner.generate_grid_configs(axes_indices=[0, 1])

    # Add seed variants
    all_configs = []
    for cfg in configs:
        all_configs.extend(runner.generate_seed_variants(cfg, args.seeds))

    runner.print_summary(all_configs)
    runner.save_configs(all_configs)
    print(f"\nTotal experiments to run: {len(all_configs)}")
