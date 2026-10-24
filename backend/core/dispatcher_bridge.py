"""
backend/core/dispatcher_bridge.py
Unified bridge for loading, switching, and executing all 8 Dispatcher AI paradigms.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

from backend.config import PPO_MODEL_PATH, MAPPO_MODEL_PATH, DISPATCHER_MODELS

logger = logging.getLogger("dispatcher_bridge")


MODEL_ALIASES: Dict[str, str] = {
    "MAPPO": "Decentralized_MAPPO",
    "Decentralized_DQN": "Decentralized_MAPPO",
    "Dynamic_Priority_Heuristic": "Priority_Greedy_Heuristic",
    "Priority_Heuristic": "Priority_Greedy_Heuristic",
    "Rule_Based_FIFO": "FIFO_Heuristic",
    "First_Come_First_Served": "FIFO_Heuristic",
    "FIFO": "FIFO_Heuristic",
    "SUMO_Default": "Static_Baseline",
    "Static": "Static_Baseline",
    "PPO": "Centralized_PPO"
}


class DispatcherBridge:
    """Manages dispatcher agent instances and provides a unified prediction interface."""

    def __init__(self, default_model: str = "Centralized_PPO"):
        self.active_model_name: str = default_model
        self.agent: Any = None
        self._cached_agents: Dict[str, Any] = {}
        self.load_model(default_model)

    def is_marl_model(self, model_name: Optional[str] = None) -> bool:
        """Returns True if the model runs under the Multi-Agent RL environment."""
        m = model_name or self.active_model_name
        m = MODEL_ALIASES.get(m, m)
        return m in ("Decentralized_MAPPO", "Comm_MAPPO")

    def load_model(self, model_name: str) -> bool:
        """Loads or switches to the specified dispatcher model."""
        model_name = MODEL_ALIASES.get(model_name, model_name)
        if model_name not in DISPATCHER_MODELS:
            logger.warning(f"Unknown dispatcher model '{model_name}'. Falling back to Centralized_PPO.")
            model_name = "Centralized_PPO"

        if model_name in self._cached_agents:
            self.agent = self._cached_agents[model_name]
            self.active_model_name = model_name
            return True

        try:
            if model_name == "Static_Baseline":
                from dispatcher.agents.baseline_dispatchers import StaticDispatcher
                agent = StaticDispatcher()

            elif model_name == "FIFO_Heuristic":
                from dispatcher.agents.baseline_dispatchers import FIFODispatcher
                agent = FIFODispatcher()

            elif model_name == "Priority_Greedy_Heuristic":
                from dispatcher.agents.baseline_dispatchers import PriorityGreedyDispatcher
                agent = PriorityGreedyDispatcher()

            elif model_name in ("Centralized_PPO", "Trained_PPO_Dispatcher"):
                from dispatcher.evaluation.evaluate import ModelAgentWrapper
                agent = ModelAgentWrapper(str(PPO_MODEL_PATH))

            elif model_name in ("Multi_Train_Centralized_PPO", "Multi_Train_PPO"):
                from dispatcher.agents.multi_train_ppo import MultiTrainCentralizedDispatcher
                agent = MultiTrainCentralizedDispatcher(str(PPO_MODEL_PATH))

            elif model_name == "Decentralized_MAPPO":
                from dispatcher.agents.mappo_agent import MAPPODispatcher
                agent = MAPPODispatcher(
                    checkpoint_path=str(MAPPO_MODEL_PATH),
                    exception_gating=True,
                    smart_interlocking=True
                )

            elif model_name == "Comm_MAPPO":
                from dispatcher.agents.comm_mappo_agent import CommMAPPODispatcher
                agent = CommMAPPODispatcher(
                    checkpoint_path=str(MAPPO_MODEL_PATH),
                    exception_gating=True,
                    smart_interlocking=True
                )

            elif model_name in ("Hierarchical_Hybrid", "Hierarchical_Hybrid_Ensemble"):
                from dispatcher.agents.hybrid_dispatcher import HierarchicalHybridDispatcher
                agent = HierarchicalHybridDispatcher(str(PPO_MODEL_PATH), str(MAPPO_MODEL_PATH))

            else:
                from dispatcher.agents.baseline_dispatchers import StaticDispatcher
                agent = StaticDispatcher()

            self._cached_agents[model_name] = agent
            self.agent = agent
            self.active_model_name = model_name
            logger.info(f"Loaded dispatcher model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            from dispatcher.agents.baseline_dispatchers import StaticDispatcher
            self.agent = StaticDispatcher()
            self.active_model_name = "Static_Baseline"
            return False

    def predict(self, obs: Any, info: Dict[str, Any]) -> Any:
        """Queries the active dispatcher for decisions."""
        if self.agent is None:
            self.load_model(self.active_model_name)

        try:
            if self.is_marl_model():
                return self.agent.predict(obs, info, deterministic=True)
            else:
                return self.agent.predict(obs, info)
        except Exception as e:
            logger.error(f"Prediction error in {self.active_model_name}: {e}")
            if self.is_marl_model():
                return {}
            return [0, 0, 0]
