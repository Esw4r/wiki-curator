"""
Application configuration — loads .env and config.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _load_yaml() -> dict[str, Any]:
    """Load config.yaml from project root."""
    config_path = _PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_YAML: dict[str, Any] = _load_yaml()


# ── Accessor helpers ─────────────────────────────────────────────────────

class _ModelsConfig:
    """Model name configuration."""

    @property
    def reviewer_1(self) -> str:
        return _YAML.get("models", {}).get("reviewer_1", "gemini-2.5-flash")

    @property
    def reviewer_2(self) -> str:
        return _YAML.get("models", {}).get("reviewer_2", "gemini-2.5-flash")

    @property
    def reviewer_3(self) -> str:
        return _YAML.get("models", {}).get("reviewer_3", "gemini-2.5-flash-lite")

    @property
    def byzantine(self) -> str:
        return _YAML.get("models", {}).get("byzantine", "gemini-2.5-flash-lite")


class _ConsensusConfig:
    """Consensus engine configuration."""

    @property
    def method(self) -> str:
        return _YAML.get("consensus", {}).get("method", "majority")

    @property
    def min_confidence(self) -> float:
        return float(_YAML.get("consensus", {}).get("min_confidence", 0.5))

    @property
    def tie_break(self) -> str:
        return _YAML.get("consensus", {}).get("tie_break", "NEEDS_MORE_EVIDENCE")


class _ReputationConfig:
    """Reputation system configuration."""

    @property
    def initial_score(self) -> float:
        return float(_YAML.get("reputation", {}).get("initial_score", 0.75))

    @property
    def correct_decision_delta(self) -> float:
        return float(_YAML.get("reputation", {}).get("correct_decision_delta", 2))

    @property
    def incorrect_decision_delta(self) -> float:
        return float(_YAML.get("reputation", {}).get("incorrect_decision_delta", -3))

    @property
    def malicious_detected_delta(self) -> float:
        return float(_YAML.get("reputation", {}).get("malicious_detected_delta", -5))

    @property
    def min_score(self) -> float:
        return float(_YAML.get("reputation", {}).get("min_score", 0.0))

    @property
    def max_score(self) -> float:
        return float(_YAML.get("reputation", {}).get("max_score", 1.0))


class _ByzantineConfig:
    """Byzantine agent configuration."""

    @property
    def enabled(self) -> bool:
        return bool(_YAML.get("byzantine", {}).get("enabled", False))

    @property
    def default_attack_mode(self) -> str:
        return _YAML.get("byzantine", {}).get("default_attack_mode", "FALSE_CLAIM")

    @property
    def intensity(self) -> float:
        return float(_YAML.get("byzantine", {}).get("intensity", 0.8))


class _DatabaseConfig:
    """Database configuration."""

    @property
    def path(self) -> str:
        relative = _YAML.get("database", {}).get("path", "wiki_curator.db")
        return str(_PROJECT_ROOT / relative)


# ── Public config object ─────────────────────────────────────────────────

class Settings:
    """Top-level application settings."""

    def __init__(self) -> None:
        self.models = _ModelsConfig()
        self.consensus = _ConsensusConfig()
        self.reputation = _ReputationConfig()
        self.byzantine = _ByzantineConfig()
        self.database = _DatabaseConfig()

    @property
    def gemini_api_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Copy .env.example to .env and set your key."
            )
        return key

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT


# Singleton
settings = Settings()
