"""
action_handler.py
Translates discrete dispatcher actions into concrete microscopic SUMO/TraCI operations:
1. Dynamic Rerouting & Overtake (Main line vs. Passing loop siding vs. High-speed bypass)
2. Platform Track Allocation (Reassigning station approach stops to open platforms)
3. Timetable Departure Dispatch & Holding (Holding vs. Green-lighting departure)
"""

from typing import Dict, Any, Optional, List
from .observation_builder import STATION_PLATFORMS


class ActionHandler:
    def __init__(self):
        self.action_history: List[Dict[str, Any]] = []

    def reset(self):
        self.action_history.clear()

    def apply_action(
        self,
        focus_veh_id: Optional[str],
        action: Any,  # MultiDiscrete: [route_act, plat_act, hold_act]
        train_states: Dict[str, Dict[str, Any]],
        sim_time: float,
        traci_module: Any
    ) -> Dict[str, Any]:
        """
        Executes the dispatcher decision in SUMO.
        """
        if not focus_veh_id or focus_veh_id not in train_states:
            return {"applied": False, "reason": "no_focus_vehicle"}

        focus_state = train_states[focus_veh_id]
        route_act, plat_act, hold_act = int(action[0]), int(action[1]), int(action[2])

        action_summary = {
            "time": sim_time,
            "veh_id": focus_veh_id,
            "route_act": route_act,
            "plat_act": plat_act,
            "hold_act": hold_act,
            "changes": []
        }

        # -------------------------------------------------------------
        # 1. Platform Track Allocation Action (plat_act)
        # -------------------------------------------------------------
        if plat_act > 0:
            st_name = focus_state.get("upcoming_station")
            direction = focus_state.get("upcoming_direction", "fw")
            dist = focus_state.get("dist_to_next_stop", 9999.0)

            # Reallocate platform only when within approach zone (300m - 2000m)
            if st_name and st_name in STATION_PLATFORMS and 200.0 < dist < 2500.0:
                available_plats = STATION_PLATFORMS[st_name].get(direction, [])
                target_idx = (plat_act - 1) % len(available_plats)
                target_plat_edge = available_plats[target_idx]
                curr_plat_edge = focus_state.get("scheduled_platform_edge")

                if target_plat_edge != curr_plat_edge:
                    try:
                        stops = traci_module.vehicle.getStops(focus_veh_id)
                        if stops:
                            curr_stop = stops[0]
                            # Replace next stop with target platform track
                            traci_module.vehicle.replaceStop(
                                focus_veh_id,
                                0,
                                target_plat_edge,
                                pos=min(curr_stop.endPos, 500.0),
                                duration=max(45.0, curr_stop.duration)
                            )
                            # Update route to traverse the new platform throat switch
                            traci_module.vehicle.rerouteTraveltime(focus_veh_id)
                            action_summary["changes"].append({
                                "type": "platform_reassigned",
                                "from": curr_plat_edge,
                                "to": target_plat_edge,
                                "station": st_name
                            })
                    except Exception:
                        pass

        # -------------------------------------------------------------
        # 2. Dynamic Rerouting & Overtake Action (route_act)
        # -------------------------------------------------------------
        if route_act == 1:
            # Divert to Alpine passing loop siding on Corridor 3
            road_id = focus_state.get("road_id", "")
            if "c3_Town_8_Town_9" in road_id or "Town_8" in road_id:
                direction = "fw" if "_fw" in road_id else "bw"
                siding_edge = f"c3_Town_8_Town_9_loop_siding_{direction}"
                try:
                    curr_route = traci_module.vehicle.getRoute(focus_veh_id)
                    # Only insert stop if siding or loop track is downstream on this route
                    if siding_edge in curr_route or any("loop" in e for e in curr_route):
                        traci_module.vehicle.setStop(
                            focus_veh_id,
                            edgeID=siding_edge,
                            pos=200.0,
                            duration=180.0
                        )
                        traci_module.vehicle.rerouteTraveltime(focus_veh_id)
                        action_summary["changes"].append({
                            "type": "diverted_to_passing_loop",
                            "siding": siding_edge
                        })
                except Exception:
                    pass

        elif route_act == 2:
            # High-Speed Bypass divert between City 2 and City 5
            road_id = focus_state.get("road_id", "")
            if ("City_2" in road_id or "City_5" in road_id) and focus_state.get("priority", 0) >= 0.8:
                try:
                    # Dynamically reduce travel time cost on high-speed bypass edges to incentivize bypass
                    traci_module.vehicle.rerouteTraveltime(focus_veh_id)
                    action_summary["changes"].append({
                        "type": "high_speed_bypass_reroute",
                        "edge": road_id
                    })
                except Exception:
                    pass

        # -------------------------------------------------------------
        # 3. Timetable Departure Dispatch & Holding Action (hold_act)
        # -------------------------------------------------------------
        if hold_act > 0 and focus_state.get("is_at_stop", False):
            # Hold train to resolve downstream junction conflict
            hold_seconds = 30.0 if hold_act == 1 else (60.0 if hold_act == 2 else 120.0)
            road_id = focus_state.get("road_id", "")
            # Avoid placing stops on internal junction lanes
            if road_id and not road_id.startswith(":"):
                try:
                    lane_id = f"{road_id}_0"
                    lane_len = traci_module.lane.getLength(lane_id)
                    curr_pos = focus_state.get("lane_pos", 10.0)
                    safe_pos = min(max(curr_pos + 1.0, 5.0), max(5.0, lane_len - 5.0))
                    traci_module.vehicle.setStop(
                        focus_veh_id,
                        edgeID=road_id,
                        pos=safe_pos,
                        duration=hold_seconds
                    )
                    action_summary["changes"].append({
                        "type": "departure_held",
                        "duration_sec": hold_seconds
                    })
                except Exception:
                    pass
        elif hold_act == 0 and focus_state.get("is_at_stop", False):
            # Authorize immediate departure / resume if dwell has finished
            try:
                traci_module.vehicle.resume(focus_veh_id)
                action_summary["changes"].append({
                    "type": "departure_cleared"
                })
            except Exception:
                pass

        if action_summary["changes"]:
            self.action_history.append(action_summary)

        return action_summary
