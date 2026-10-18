"""
multi_train_ppo.py
Option 2: Multi-Train Centralized PPO Dispatcher with Concurrent Spatial Attention.

Upgrades Centralized PPO from 1-train-at-a-time focus execution to concurrent multi-train dispatching:
- Identifies all active conflict clusters across the rail network during each 15-second macro cycle.
- Evaluates policy decisions simultaneously across top-k candidate trains (up to 4 trains per step).
- Resolves simultaneous bottleneck conflicts at opposing hubs (e.g. City 1 and City 6) without waiting
  for sequential 15-second cycles, eliminating peak-rush delay propagation.
"""

import os
import sys
import numpy as np
import logging
from typing import Dict, Any, Optional, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dispatcher.agents.baseline_dispatchers import BaseDispatcher
from dispatcher.evaluation.evaluate import ModelAgentWrapper

logger = logging.getLogger(__name__)

DEFAULT_PPO_PATH = os.path.join(ROOT_DIR, "dispatcher", "models", "best_model.zip")


class MultiTrainCentralizedDispatcher(BaseDispatcher):
    """
    Option 2: Multi-Train Centralized PPO Dispatcher.
    Wraps the trained PPO network to evaluate and dispatch decisions across multiple conflicting trains
    concurrently in a single macro step.
    """
    def __init__(
        self,
        model_path: str = DEFAULT_PPO_PATH,
        name: str = "Multi_Train_Centralized_PPO",
        max_concurrent: int = 4,
        exception_gating: bool = True,
        smart_interlocking: bool = True
    ):
        super().__init__(name=name)
        self.max_concurrent = max_concurrent
        self.base_wrapper = ModelAgentWrapper(
            model_path=model_path,
            name=name,
            exception_gating=exception_gating,
            smart_interlocking=smart_interlocking
        )

    def predict(
        self,
        observation: np.ndarray,
        info: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Generates actions. If multiple candidate conflict trains are identified in info,
        evaluates decisions concurrently and returns a dictionary of {veh_id: action_array}.
        Otherwise returns a single action array for the primary focus vehicle.
        """
        info_dict = info if (info and isinstance(info, dict)) else {}
        candidate_trains = info_dict.get("candidate_trains", [])
        focus_veh = info_dict.get("focus_vehicle")

        # If only 0 or 1 candidate train, execute standard single-agent path
        if not candidate_trains or len(candidate_trains) <= 1:
            return self.base_wrapper.predict(observation, info_dict)

        # Multi-Train Path: Dispatch top-k candidate conflict trains concurrently
        actions_dict: Dict[str, np.ndarray] = {}
        target_trains = candidate_trains[:self.max_concurrent]

        # Prioritize the primary focus train first
        if focus_veh and focus_veh not in target_trains:
            target_trains = [focus_veh] + target_trains[:self.max_concurrent - 1]

        for vid in target_trains:
            # Build localized train context
            sub_info = dict(info_dict)
            sub_info["focus_vehicle"] = vid
            act = self.base_wrapper.predict(observation, sub_info)
            actions_dict[vid] = act

        return actions_dict
