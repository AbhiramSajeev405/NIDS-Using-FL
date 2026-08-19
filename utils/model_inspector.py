"""
Model Inspector for FL-NIDS.

Weight drift analysis and model health diagnostics:
  - Layer-wise parameter norm tracking across rounds
  - Client-to-global model divergence (L2, cosine)
  - Gradient health check (dead neurons, vanishing/exploding)
  - Model size and FLOPs profiling per architecture

Usage:
    from utils.model_inspector import ModelInspector
    inspector = ModelInspector(model)
    inspector.layer_norms()
    inspector.gradient_health()
    inspector.profile()
"""

import os
import json
import numpy as np
import torch
import torch.nn as nn


class ModelInspector:
    """Inspect and analyze PyTorch model health and complexity."""

    def __init__(self, model):
        """
        Args:
            model: PyTorch nn.Module
        """
        self.model = model

    # ─── Layer-Wise Parameter Norms ─────────────────────────────────

    def layer_norms(self):
        """Compute L2 norm of parameters for each layer.

        Returns:
            Dict mapping layer_name -> {norm, num_params, mean, std, min, max}
        """
        report = {}
        for name, param in self.model.named_parameters():
            data = param.detach().cpu().numpy()
            report[name] = {
                "norm": float(np.linalg.norm(data)),
                "num_params": int(data.size),
                "mean": float(np.mean(data)),
                "std": float(np.std(data)),
                "min": float(np.min(data)),
                "max": float(np.max(data)),
            }
        return report

    def layer_norms_diff(self, other_model):
        """Compare layer norms between this model and another (e.g., global vs local).

        Args:
            other_model: Another PyTorch nn.Module with the same architecture

        Returns:
            Dict mapping layer_name -> {norm_diff, cosine_sim}
        """
        report = {}
        for (name, p1), (_, p2) in zip(
            self.model.named_parameters(), other_model.named_parameters()
        ):
            v1 = p1.detach().cpu().numpy().flatten()
            v2 = p2.detach().cpu().numpy().flatten()

            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            cos_sim = 0.0
            if norm1 > 0 and norm2 > 0:
                cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))

            report[name] = {
                "norm_diff": float(abs(norm1 - norm2)),
                "l2_distance": float(np.linalg.norm(v1 - v2)),
                "cosine_similarity": cos_sim,
            }
        return report

    # ─── Gradient Health Check ──────────────────────────────────────

    def gradient_health(self):
        """Check gradient health across layers.

        Must be called after loss.backward() but before optimizer.step().

        Returns:
            Dict with per-layer gradient stats and health warnings
        """
        report = {"layers": {}, "warnings": []}

        for name, param in self.model.named_parameters():
            if param.grad is None:
                report["layers"][name] = {"status": "no_gradient"}
                report["warnings"].append(f"{name}: No gradient — dead or detached layer")
                continue

            grad = param.grad.detach().cpu().numpy()
            grad_norm = float(np.linalg.norm(grad))
            grad_mean = float(np.mean(np.abs(grad)))

            status = "healthy"
            if grad_norm < 1e-7:
                status = "vanishing"
                report["warnings"].append(f"{name}: Vanishing gradient (norm={grad_norm:.2e})")
            elif grad_norm > 1e3:
                status = "exploding"
                report["warnings"].append(f"{name}: Exploding gradient (norm={grad_norm:.2e})")

            report["layers"][name] = {
                "status": status,
                "grad_norm": grad_norm,
                "grad_mean_abs": grad_mean,
                "grad_std": float(np.std(grad)),
                "grad_max": float(np.max(np.abs(grad))),
            }

        return report

    # ─── Dead Neuron Detection ──────────────────────────────────────

    def dead_neurons(self, dataloader, device=None, threshold=0.01, max_batches=10):
        """Detect dead (always-zero) neurons in ReLU layers.

        Runs a forward pass on sample data and checks which neurons
        never activate.

        Args:
            dataloader: DataLoader with sample input data
            device: torch.device (default: CPU)
            threshold: Activation below this counts as "dead"
            max_batches: Max batches to sample

        Returns:
            Dict with per-layer dead neuron counts
        """
        if device is None:
            device = torch.device("cpu")

        activation_sums = {}
        hooks = []

        def _make_hook(layer_name):
            def hook_fn(module, input, output):
                act = output.detach().cpu()
                if layer_name not in activation_sums:
                    activation_sums[layer_name] = torch.zeros(act.shape[1:])
                activation_sums[layer_name] += torch.abs(act).sum(dim=0)
            return hook_fn

        # Register hooks on ReLU-like layers
        for name, module in self.model.named_modules():
            if isinstance(module, (nn.ReLU, nn.LeakyReLU, nn.ELU, nn.GELU)):
                hooks.append(module.register_forward_hook(_make_hook(name)))

        # Forward pass
        self.model.eval()
        n_samples = 0
        with torch.no_grad():
            for i, (data, _) in enumerate(dataloader):
                if i >= max_batches:
                    break
                data = data.to(device)
                self.model(data)
                n_samples += data.shape[0]

        # Remove hooks
        for h in hooks:
            h.remove()

        # Analyze
        report = {}
        for layer_name, sums in activation_sums.items():
            avg_activation = sums / max(1, n_samples)
            flat = avg_activation.flatten()
            total = len(flat)
            dead_count = int((flat < threshold).sum())
            report[layer_name] = {
                "total_neurons": total,
                "dead_neurons": dead_count,
                "dead_ratio": round(dead_count / max(1, total), 4),
                "avg_activation": float(flat.mean()),
            }

        return report

    # ─── Model Profiling ────────────────────────────────────────────

    def profile(self):
        """Profile model size and parameter count.

        Returns:
            Dict with model profiling info
        """
        total_params = 0
        trainable_params = 0
        layer_info = []

        for name, param in self.model.named_parameters():
            n = param.numel()
            total_params += n
            if param.requires_grad:
                trainable_params += n
            layer_info.append({
                "name": name,
                "shape": list(param.shape),
                "params": n,
                "trainable": param.requires_grad,
                "dtype": str(param.dtype),
            })

        # Size in bytes (float32 = 4 bytes)
        size_bytes = total_params * 4
        size_kb = size_bytes / 1024
        size_mb = size_kb / 1024

        return {
            "total_params": total_params,
            "trainable_params": trainable_params,
            "frozen_params": total_params - trainable_params,
            "size_bytes": size_bytes,
            "size_kb": round(size_kb, 2),
            "size_mb": round(size_mb, 4),
            "num_layers": len(layer_info),
            "layers": layer_info,
        }

    def print_profile(self):
        """Pretty-print model profile."""
        p = self.profile()
        print(f"\n{'='*60}")
        print(f"MODEL PROFILE")
        print(f"{'='*60}")
        print(f"  Total params:     {p['total_params']:,}")
        print(f"  Trainable params: {p['trainable_params']:,}")
        print(f"  Model size:       {p['size_kb']:.1f} KB ({p['size_mb']:.4f} MB)")
        print(f"  Layers:           {p['num_layers']}")
        print(f"\n  {'Layer':<40s} {'Shape':<20s} {'Params':>10s}")
        print(f"  {'-'*70}")
        for layer in p["layers"]:
            shape_str = str(layer["shape"])
            print(f"  {layer['name']:<40s} {shape_str:<20s} {layer['params']:>10,}")
        print(f"{'='*60}")

    # ─── Weight Drift Tracking ──────────────────────────────────────

    @staticmethod
    def compute_drift(model_a, model_b):
        """Compute overall weight drift between two models.

        Args:
            model_a, model_b: PyTorch nn.Module instances

        Returns:
            Dict with overall drift metrics
        """
        all_a = []
        all_b = []
        for pa, pb in zip(model_a.parameters(), model_b.parameters()):
            all_a.append(pa.detach().cpu().numpy().flatten())
            all_b.append(pb.detach().cpu().numpy().flatten())

        vec_a = np.concatenate(all_a)
        vec_b = np.concatenate(all_b)

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        cos_sim = 0.0
        if norm_a > 0 and norm_b > 0:
            cos_sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

        return {
            "l2_distance": float(np.linalg.norm(vec_a - vec_b)),
            "cosine_similarity": cos_sim,
            "norm_a": float(norm_a),
            "norm_b": float(norm_b),
            "norm_ratio": float(norm_a / norm_b) if norm_b > 0 else 0.0,
            "total_params": len(vec_a),
        }
