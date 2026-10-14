"""
evaluation module
"""
from .evaluate import evaluate_dispatcher, run_benchmark_suite
from .visualizer import plot_benchmark_charts

__all__ = ["evaluate_dispatcher", "run_benchmark_suite", "plot_benchmark_charts"]
