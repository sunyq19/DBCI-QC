"""Stable, dependency-light interface for the local service and worker."""
from .planning import catalog, build_plan


def run_job(request, job_dir, emit):
    from .runtime import execute
    return execute(request, job_dir, emit)


__all__ = ["catalog", "build_plan", "run_job"]
