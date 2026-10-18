"""
action_handler.py
Translates discrete dispatcher actions into concrete microscopic SUMO/TraCI operations:
1. Dynamic Rerouting & Overtake (Main line vs. Passing loop siding vs. High-speed bypass)
2. Platform Track Allocation (Reassigning station approach stops to open platforms)
3. Timetable Departure Dispatch & Holding (Holding vs. Green-lighting departure)
"""

from typing import Dict, Any, Optional, List
from .observation_builder import STATION_PLATFORMS, PLATFORM_LENGTHS, ROLLING_STOCK_SPECS


class ActionHandler:
    def __init__(self):
        self.action_history: List[Dict[str, Any]] = []
        self.train_hold_seconds: Dict[str, float] = {}
        self.siding_reservations: Dict[str, str] = {}

    def reset(self):
        self.action_history.clear()
        self.train_hold_seconds.clear()
        self.siding_reservations.clear()

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

        # Clear expired loop-siding reservations when the reserving train has left or finished
        for s_edge, res_vid in list(self.siding_reservations.items()):
            if res_vid not in train_states:
                del self.siding_reservations[s_edge]
            else:
                try:
                    res_road = train_states[res_vid].get("road_id", "")
                    res_route = list(traci_module.vehicle.getRoute(res_vid))
                    res_idx = max(0, traci_module.vehicle.getRouteIndex(res_vid))
                    rem_edges = res_route[res_idx:] if res_idx < len(res_route) else []
                    if s_edge not in rem_edges and s_edge not in res_road:
                        del self.siding_reservations[s_edge]
                except Exception:
                    del self.siding_reservations[s_edge]

        # -------------------------------------------------------------
        # 1. Platform Track Allocation Action (plat_act)
        # -------------------------------------------------------------
        if plat_act > 0:
            st_name = focus_state.get("upcoming_station")
            direction = focus_state.get("upcoming_direction", "fw")
            dist = focus_state.get("dist_to_next_stop", 9999.0)
            train_len = focus_state.get("train_length", 200.0)
            is_freight = focus_state.get("is_freight", False)

            # Reallocate platform only when within approach zone (200m - 2500m) and strictly at multi-platform City hubs
            if st_name and st_name in STATION_PLATFORMS and st_name.startswith("City_") and 200.0 < dist < 2500.0:
                st_plat_len = PLATFORM_LENGTHS.get(st_name, 340.0)

                # Physical Constraint 1: Platform Length Check
                if train_len > st_plat_len:
                    action_summary["changes"].append({
                        "type": "action_rejected",
                        "reason": f"Physical length violation: train length ({train_len}m) exceeds platform capacity ({st_plat_len}m) at {st_name}"
                    })
                # Physical Constraint 2: Freight Passenger Platform Exclusion
                elif is_freight:
                    action_summary["changes"].append({
                        "type": "action_rejected",
                        "reason": f"Operational constraint violation: freight train {focus_veh_id} cannot occupy passenger platform at {st_name}"
                    })
                else:
                    available_plats = STATION_PLATFORMS[st_name].get(direction, [])
                    target_idx = (plat_act - 1) % len(available_plats)
                    target_plat_edge = available_plats[target_idx]
                    curr_plat_edge = focus_state.get("scheduled_platform_edge")
                    dist_to_stop = focus_state.get("dist_to_next_stop", 9999.0)
                    is_at_stop = focus_state.get("is_at_stop", False)

                    if is_at_stop:
                        action_summary["changes"].append({
                            "type": "action_rejected",
                            "reason": f"Train {focus_veh_id} is already berthed at {curr_plat_edge}; cannot reassign platform"
                        })
                    elif dist_to_stop < 400.0:
                        action_summary["changes"].append({
                            "type": "action_rejected",
                            "reason": f"Approach locking: train {focus_veh_id} is within {dist_to_stop:.0f}m of {st_name} throat; interlocking locked"
                        })
                    elif target_plat_edge != curr_plat_edge:
                        try:
                            stops = traci_module.vehicle.getStops(focus_veh_id)
                            if stops:
                                curr_stop = stops[0]
                                curr_route = traci_module.vehicle.getRoute(focus_veh_id)
                                route_idx = traci_module.vehicle.getRouteIndex(focus_veh_id)
                                remaining = curr_route[route_idx:] if 0 <= route_idx < len(curr_route) else curr_route

                                # Guardrail 1: The stop being modified MUST be an active passenger platform stop
                                # (Never modify yard sidings, depots, or turnaround pocket reversal stops)
                                stop_lane = getattr(curr_stop, "lane", "")
                                is_actual_platform_stop = (
                                    curr_plat_edge and 
                                    (stop_lane.startswith(curr_plat_edge) or "_plat_" in stop_lane) and
                                    "_pocket_" not in stop_lane and
                                    "_yard_" not in stop_lane and
                                    "_buf_" not in stop_lane
                                )

                                # Guardrail 2: The platform MUST be in the approaching zone (edges 2 to 15, not already entering throat or dwelling)
                                is_dwelling = focus_state.get("is_at_stop", False)
                                in_safe_approach = (curr_plat_edge in remaining[2:15]) if len(remaining) > 2 else False

                                if is_actual_platform_stop and not is_dwelling and in_safe_approach:
                                    # Guardrail 2B: Platform MUST be physically reachable from current road
                                    curr_road = traci_module.vehicle.getRoadID(focus_veh_id)
                                    is_invalid_divert_edge = (
                                        curr_road.startswith(":") or 
                                        "_yard_" in curr_road or 
                                        "_pocket_" in curr_road or 
                                        "_depot_" in curr_road.lower() or 
                                        "_buf_" in curr_road or
                                        "_plat_" in curr_road
                                    )
                                    vtype = focus_state.get("vtype", "")
                                    route_valid = False
                                    if not is_invalid_divert_edge:
                                        try:
                                            test_stage = traci_module.simulation.findRoute(curr_road, target_plat_edge, vtype)
                                            route_valid = (test_stage is not None and len(test_stage.edges) > 0)

                                            # Guardrail 2C: Target platform MUST also connect to downstream stop if scheduled
                                            if route_valid and len(stops) > 1:
                                                next_stop_lane = getattr(stops[1], "lane", "")
                                                next_stop_edge = next_stop_lane.rsplit("_", 1)[0] if "_" in next_stop_lane else next_stop_lane
                                                if next_stop_edge and not next_stop_edge.startswith(":"):
                                                    out_stage = traci_module.simulation.findRoute(target_plat_edge, next_stop_edge, vtype)
                                                    if out_stage is None or len(out_stage.edges) == 0:
                                                        route_valid = False
                                        except Exception:
                                            route_valid = False

                                    if not route_valid:
                                        action_summary["changes"].append({
                                            "type": "action_rejected",
                                            "reason": f"Platform {target_plat_edge} has no valid track connection from {curr_road}"
                                        })
                                    else:
                                        try:
                                            replace_kwargs = {
                                                "pos": min(curr_stop.endPos, 500.0),
                                                "duration": max(45.0, curr_stop.duration)
                                            }
                                            if getattr(curr_stop, "until", -1) > 0:
                                                replace_kwargs["until"] = curr_stop.until
                                            traci_module.vehicle.replaceStop(
                                                focus_veh_id,
                                                0,
                                                target_plat_edge,
                                                **replace_kwargs
                                            )
                                            try:
                                                traci_module.vehicle.rerouteTraveltime(focus_veh_id)
                                            except Exception:
                                                pass
                                            action_summary["changes"].append({
                                                "type": "platform_reassigned",
                                                "from": curr_plat_edge,
                                                "to": target_plat_edge,
                                                "station": st_name,
                                                "train_len": train_len,
                                                "platform_len": st_plat_len
                                            })
                                        except Exception as stop_err:
                                            action_summary["changes"].append({
                                                "type": "action_rejected",
                                                "reason": f"Stop replacement rejected by simulator: {stop_err}"
                                            })
                                else:
                                    action_summary["changes"].append({
                                        "type": "action_rejected",
                                        "reason": f"Train {focus_veh_id} is not in safe platform approach zone ({stop_lane}, dwelling={is_dwelling})"
                                    })
                        except Exception:
                            pass

        # -------------------------------------------------------------
        # 2. Dynamic Rerouting & Overtake Action (route_act)
        # -------------------------------------------------------------
        if route_act == 1:
            # Divert to Alpine passing loop siding on Corridor 3
            # Physical Constraint 3: Only freight or low-priority regional consists take mountain siding
            if focus_state.get("priority", 0) >= 0.9 or focus_state.get("vtype") == "high_speed_emu_300":
                action_summary["changes"].append({
                    "type": "action_rejected",
                    "reason": f"High-speed express {focus_veh_id} cannot divert into freight passing loop siding"
                })
            elif focus_state.get("leader_dist", 3000.0) >= 1500.0 and focus_state.get("delay_sec", 0.0) <= 60.0:
                action_summary["changes"].append({
                    "type": "action_rejected",
                    "reason": f"Mainline clear ahead ({focus_state.get('leader_dist', 0):.0f}m >= 1500m); passing loop diversion unnecessary"
                })
            else:
                road_id = focus_state.get("road_id", "")
                if "c3_Town_8_Town_9" in road_id or "Town_8" in road_id or "Town_9" in road_id:
                    direction = "fw" if "_fw" in road_id else ("bw" if "_bw" in road_id else focus_state.get("upcoming_direction", "fw"))
                    siding_edge = f"c3_Town_8_Town_9_loop_siding_{direction}"
                    mid_edge = f"c3_Town_8_Town_9_loop_T1_mid_{direction}"
                    loop_edges = [
                        f"c3_Town_8_Town_9_loop_lead_in_{direction}",
                        siding_edge,
                        f"c3_Town_8_Town_9_loop_lead_out_{direction}"
                    ]
                    try:
                        # Reservation guardrail: Reject if another train holds the reservation
                        res_veh = self.siding_reservations.get(siding_edge)
                        if res_veh and res_veh != focus_veh_id and res_veh in train_states:
                            action_summary["changes"].append({
                                "type": "action_rejected",
                                "reason": f"Passing loop siding {siding_edge} is currently reserved by {res_veh}"
                            })
                        else:
                            # Occupancy guardrail: Inspect siding, lead-in, and lead-out edges for other vehicles
                            active_loop_vehs = []
                            for le in loop_edges:
                                try:
                                    active_loop_vehs.extend(traci_module.edge.getLastStepVehicleIDs(le))
                                except Exception:
                                    pass
                            other_loop_vehs = [v for v in active_loop_vehs if v != focus_veh_id]
                            if other_loop_vehs:
                                action_summary["changes"].append({
                                    "type": "action_rejected",
                                    "reason": f"Passing loop track or turnouts ({siding_edge}) currently occupied by {other_loop_vehs[0]}"
                                })
                            else:
                                curr_route = list(traci_module.vehicle.getRoute(focus_veh_id))
                                route_idx = max(0, traci_module.vehicle.getRouteIndex(focus_veh_id))
                                remaining = curr_route[route_idx:] if route_idx < len(curr_route) else curr_route

                                # Siding track or mainline mid must be physically in immediate downstream approach
                                if siding_edge in remaining[1:8]:
                                    existing_stops = traci_module.vehicle.getStops(focus_veh_id)
                                    if any(siding_edge in getattr(st, "lane", "") or getattr(st, "edge", "") == siding_edge for st in existing_stops):
                                        pass  # Stop already exists on siding_edge; skip diversion and record nothing
                                    else:
                                        traci_module.vehicle.setStop(
                                            focus_veh_id,
                                            edgeID=siding_edge,
                                            pos=200.0,
                                            duration=180.0
                                        )
                                        self.siding_reservations[siding_edge] = focus_veh_id
                                        action_summary["changes"].append({
                                            "type": "diverted_to_passing_loop",
                                            "siding": siding_edge
                                        })
                                elif mid_edge in remaining[1:8]:
                                    existing_stops = traci_module.vehicle.getStops(focus_veh_id)
                                    if any(siding_edge in getattr(st, "lane", "") or getattr(st, "edge", "") == siding_edge for st in existing_stops):
                                        pass  # Stop already exists on siding_edge; skip diversion and record nothing
                                    else:
                                        mid_idx = curr_route.index(mid_edge, route_idx)
                                        if direction == "fw":
                                            siding_edges = [
                                                "c3_Town_8_Town_9_loop_lead_in_fw",
                                                "c3_Town_8_Town_9_loop_siding_fw",
                                                "c3_Town_8_Town_9_loop_lead_out_fw"
                                            ]
                                        else:
                                            siding_edges = [
                                                "c3_Town_8_Town_9_loop_lead_out_bw",
                                                "c3_Town_8_Town_9_loop_siding_bw",
                                                "c3_Town_8_Town_9_loop_lead_in_bw"
                                            ]
                                        new_route = curr_route[route_idx:mid_idx] + siding_edges + curr_route[mid_idx + 1:]
                                        traci_module.vehicle.setRoute(focus_veh_id, new_route)
                                        traci_module.vehicle.setStop(
                                            focus_veh_id,
                                            edgeID=siding_edge,
                                            pos=200.0,
                                            duration=180.0
                                        )
                                        self.siding_reservations[siding_edge] = focus_veh_id
                                        action_summary["changes"].append({
                                            "type": "diverted_to_passing_loop",
                                            "siding": siding_edge
                                        })
                                else:
                                    action_summary["changes"].append({
                                        "type": "action_rejected",
                                        "reason": f"Siding {siding_edge} not in immediate approach for {focus_veh_id}"
                                    })
                    except Exception as loop_err:
                        action_summary["changes"].append({
                            "type": "action_rejected",
                            "reason": f"Passing loop divert failed: {loop_err}"
                        })
                else:
                    action_summary["changes"].append({
                        "type": "action_rejected",
                        "reason": f"Train {focus_veh_id} on {road_id} is not approaching Corridor 3 loop siding"
                    })

        elif route_act == 2:
            # High-Speed Bypass divert between City 2 and City 5
            # Physical Constraint 4: Only high-speed electrified passenger consists can access 300 km/h bypass
            if not focus_state.get("is_electric", True) or focus_state.get("is_freight", False):
                action_summary["changes"].append({
                    "type": "action_rejected",
                    "reason": f"Consist {focus_veh_id} (freight/diesel) prohibited from 300 km/h electrified bypass chord"
                })
            else:
                road_id = focus_state.get("road_id", "")
                if ("City_2" in road_id or "City_5" in road_id) and focus_state.get("priority", 0) >= 0.8:
                    try:
                        # Dynamically reduce travel time cost on high-speed bypass edges to incentivize bypass
                        bypass_edges = (
                            [f"bypass_City_2_City_5_fw_b{i}" for i in range(10)]
                            if "City_2" in road_id
                            else [f"bypass_City_2_City_5_bw_b{i}" for i in range(10)]
                        )
                        for be in bypass_edges:
                            try:
                                traci_module.vehicle.setAdaptedTraveltime(focus_veh_id, be, 5.0)
                            except Exception:
                                pass
                        route_before = list(traci_module.vehicle.getRoute(focus_veh_id))
                        traci_module.vehicle.rerouteTraveltime(focus_veh_id)
                        route_after = list(traci_module.vehicle.getRoute(focus_veh_id))
                        route_idx = max(0, traci_module.vehicle.getRouteIndex(focus_veh_id))
                        remaining = route_after[route_idx:] if route_idx < len(route_after) else route_after
                        bypass_set = set(bypass_edges)

                        if route_after != route_before and any(be in bypass_set for be in remaining):
                            action_summary["changes"].append({
                                "type": "high_speed_bypass_reroute",
                                "edge": road_id
                            })
                        else:
                            action_summary["changes"].append({
                                "type": "action_rejected",
                                "reason": f"High-speed bypass reroute did not alter downstream route for {focus_veh_id}"
                            })
                    except Exception as bypass_err:
                        action_summary["changes"].append({
                            "type": "action_rejected",
                            "reason": f"High-speed bypass reroute failed: {bypass_err}"
                        })
                else:
                    action_summary["changes"].append({
                        "type": "action_rejected",
                        "reason": f"Train {focus_veh_id} on {road_id} (prio={focus_state.get('priority', 0):.2f}) not eligible for High-Speed Bypass"
                    })

        # -------------------------------------------------------------
        # 3. Timetable Departure Dispatch & Holding Action (hold_act)
        # -------------------------------------------------------------
        if not focus_state.get("is_at_stop", False):
            self.train_hold_seconds[focus_veh_id] = 0.0

        if hold_act > 0 and focus_state.get("is_at_stop", False):
            accumulated_hold = self.train_hold_seconds.get(focus_veh_id, 0.0)
            curr_delay = focus_state.get("delay_sec", 0.0)

            # Guardrail: Never hold a train that is already running significantly late (>120s delay)
            if curr_delay > 120.0:
                action_summary["changes"].append({
                    "type": "action_rejected",
                    "reason": f"Train {focus_veh_id} is already delayed by {curr_delay:.1f}s (>120s); further holding prohibited"
                })
            # Guardrail: Maximum cumulative holding ceiling per dwell (120s max total hold)
            elif accumulated_hold >= 120.0:
                action_summary["changes"].append({
                    "type": "action_rejected",
                    "reason": f"Train {focus_veh_id} reached max hold ceiling ({accumulated_hold:.0f}s >= 120s); forced departure"
                })
            else:
                hold_seconds = 30.0 if hold_act == 1 else (60.0 if hold_act == 2 else 120.0)
                allowed_hold = min(hold_seconds, 120.0 - accumulated_hold)
                road_id = focus_state.get("road_id", "")
                # Avoid placing stops on internal junction lanes
                if road_id and not road_id.startswith(":"):
                    try:
                        stops = traci_module.vehicle.getStops(focus_veh_id)
                        if stops:
                            curr_stop = stops[0]
                            traci_module.vehicle.setStop(
                                focus_veh_id,
                                edgeID=road_id,
                                pos=curr_stop.endPos,
                                duration=allowed_hold
                            )
                        else:
                            lane_id = f"{road_id}_0"
                            lane_len = traci_module.lane.getLength(lane_id)
                            curr_pos = focus_state.get("lane_pos", 10.0)
                            safe_pos = min(max(curr_pos + 10.0, 5.0), max(5.0, lane_len - 5.0))
                            traci_module.vehicle.setStop(
                                focus_veh_id,
                                edgeID=road_id,
                                pos=safe_pos,
                                duration=allowed_hold
                            )
                        self.train_hold_seconds[focus_veh_id] = accumulated_hold + allowed_hold
                        action_summary["changes"].append({
                            "type": "departure_held",
                            "duration_sec": allowed_hold,
                            "total_hold_sec": self.train_hold_seconds[focus_veh_id]
                        })
                    except Exception:
                        pass
        elif hold_act == 0 and focus_state.get("is_at_stop", False):
            if self.train_hold_seconds.get(focus_veh_id, 0.0) > 0:
                self.train_hold_seconds[focus_veh_id] = 0.0
                # Authorize immediate departure / resume if train was held by dispatcher
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
