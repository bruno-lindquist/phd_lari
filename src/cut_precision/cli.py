from __future__ import annotations

from .cli_args import build_pipeline_parser
from .pipeline_service import _pick_best_registration_for_contour, run_pipeline


def build_parser():
    return build_pipeline_parser()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_pipeline(args)


__all__ = ["build_parser", "main", "_pick_best_registration_for_contour"]
