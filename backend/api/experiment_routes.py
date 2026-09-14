"""
Experiment API routes.

Provides endpoints for running fault-tolerance experiments,
listing past results, and retrieving detailed metrics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.database import models as db
from backend.experiments.runner import ExperimentRunner
from backend.schemas.messages import ExperimentConfig, ExperimentResult

logger = logging.getLogger(__name__)
router = APIRouter()

_runner = ExperimentRunner()


@router.post("/run", response_model=ExperimentResult)
async def run_experiment(config: ExperimentConfig):
    """
    Run a controlled fault-tolerance experiment.

    This runs multiple proposals through the review pipeline under
    the specified Byzantine conditions and computes metrics.
    """
    logger.info(
        "Starting experiment '%s': %d proposals, %d byzantine agents, mode=%s",
        config.name,
        config.num_proposals,
        config.num_byzantine_agents,
        config.byzantine_attack_mode.value,
    )
    result = await _runner.run(config)
    logger.info(
        "Experiment '%s' complete: accuracy=%.1f%%, FAR=%.1f%%, FRR=%.1f%%",
        config.name,
        result.metrics.accuracy * 100,
        result.metrics.false_acceptance_rate * 100,
        result.metrics.false_rejection_rate * 100,
    )
    return result


@router.get("/")
async def list_experiments(limit: int = 50, offset: int = 0):
    """List all past experiment runs."""
    experiments = await db.list_experiments(limit, offset)
    return {"experiments": experiments, "limit": limit, "offset": offset}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get detailed results for a specific experiment."""
    experiment = await db.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment
