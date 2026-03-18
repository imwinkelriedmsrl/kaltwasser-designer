"""
Hydraulic network calculation for chilled water systems.

Uses NetworkX to model the pipe network as a directed graph.
Supports:
  - Flow distribution based on equipment loads
  - Pressure drop calculation per segment (pipe + fittings)
  - Critical path analysis
  - Pump adequacy check (pump head from chiller node props)
  - System water volume

Each node has a 'type' attribute (CHILLER, FAN_COIL, T_JUNCTION, etc.)
Each edge has attributes:
  flow_W, length_m, fittings, nominal_dn (after sizing)
"""

import networkx as nx
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

from calculations.pipe_sizing import (
    size_pipe,
    calculate_segment_dp,
    calculate_pipe_water_content,
    get_pipe_data,
)
from data.geberit_flowfit import get_fluid_properties
from data.component_library import get_chiller, get_fan_coil, get_fan_coil_dp_kPa, CHILLERS, FAN_COILS


class NetworkCalculator:
    """
    Hydraulic calculator for a chilled water pipe network.

    Usage
    -----
    calc = NetworkCalculator(nodes, edges, system_params)
    results = calc.run()
    """

    def __init__(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        system_params: Dict,
    ):
        self.nodes = {n["id"]: n for n in nodes}
        self.edges = {e["id"]: e for e in edges}
        self.system_params = system_params
        self.glycol_pct = int(system_params.get("glycol_pct", 30))
        self.graph = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        """Build NetworkX graph from node/edge lists."""
        for nid, node in self.nodes.items():
            self.graph.add_node(nid, **node)
        for eid, edge in self.edges.items():
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                edge_id=eid,
                **edge,
            )

    # ------------------------------------------------------------------
    # Flow distribution
    # ------------------------------------------------------------------

    def _get_fan_coil_flow_W(self, node: Dict) -> float:
        """Return design cooling load in W for a fan coil node."""
        props = node.get("props", {})
        model = props.get("model", node.get("model", "Kampmann_KaCool_W_Size4"))

        # Custom unit: use stored cooling_W directly
        if model == "custom":
            return float(props.get("cooling_W", node.get("cooling_W", 3000)))

        try:
            fc = get_fan_coil(model)
            voltages = sorted(fc["performance"].keys())
            v = voltages[-1]  # use max (10V) as design point
            return float(fc["performance"][v]["cooling_total_W"])
        except Exception:
            return float(props.get("cooling_W", node.get("cooling_W", 3000)))

    def calculate_flows(self) -> Dict[str, float]:
        """
        Calculate thermal flow [W] for each edge.
        """
        load_map: Dict[str, float] = {}
        for nid, node in self.nodes.items():
            if node.get("type") == "FAN_COIL":
                load_map[nid] = self._get_fan_coil_flow_W(node)
            else:
                load_map[nid] = 0.0

        downstream_load: Dict[str, float] = {}
        for nid in self.nodes:
            reachable = nx.descendants(self.graph, nid)
            total = load_map.get(nid, 0.0)
            for d in reachable:
                total += load_map.get(d, 0.0)
            downstream_load[nid] = total

        edge_flows: Dict[str, float] = {}
        for eid, edge in self.edges.items():
            target = edge["target"]
            flow = downstream_load.get(target, 0.0)
            if self.nodes.get(target, {}).get("type") == "FAN_COIL":
                flow = load_map.get(target, 0.0)
            edge_flows[eid] = flow

        self._edge_flows = edge_flows
        return edge_flows

    # ------------------------------------------------------------------
    # Pipe sizing
    # ------------------------------------------------------------------

    def size_all_pipes(self) -> Dict[str, int]:
        """Size all pipe segments. Must call calculate_flows() first."""
        if not hasattr(self, "_edge_flows"):
            self.calculate_flows()

        pipe_sizes: Dict[str, int] = {}
        for eid, edge in self.edges.items():
            flow_W = self._edge_flows.get(eid, 0.0)
            is_branch = self._is_branch_edge(eid)
            if flow_W > 0:
                dn, _ = size_pipe(flow_W, glycol_pct=self.glycol_pct, is_branch=is_branch)
            else:
                dn = 16
            pipe_sizes[eid] = dn

        self._pipe_sizes = pipe_sizes
        return pipe_sizes

    def _is_branch_edge(self, edge_id: str) -> bool:
        """An edge is a branch if it connects directly to a FAN_COIL."""
        edge = self.edges[edge_id]
        target = edge.get("target")
        node = self.nodes.get(target, {})
        return node.get("type") == "FAN_COIL"

    # ------------------------------------------------------------------
    # Pressure drop calculation
    # ------------------------------------------------------------------

    def calculate_pressure_drops(self) -> Dict[str, Dict]:
        """Calculate pressure drops for all edges."""
        if not hasattr(self, "_pipe_sizes"):
            self.size_all_pipes()

        dp_results: Dict[str, Dict] = {}
        for eid, edge in self.edges.items():
            flow_W   = self._edge_flows.get(eid, 0.0)
            dn       = self._pipe_sizes.get(eid, 16)
            length_m = edge.get("length_m", 1.0)

            # Support both old flat structure and new props-nested structure
            fittings = edge.get("fittings", edge.get("props", {}).get("fittings_raw", {}))
            if isinstance(fittings, dict):
                pass
            else:
                fittings = {}

            if flow_W > 0:
                dp_data = calculate_segment_dp(
                    flow_W, length_m, dn, self.glycol_pct, fittings
                )
            else:
                dp_data = {
                    "dp_pipe_Pa":             0.0,
                    "dp_fittings_Pa":         0.0,
                    "dp_total_Pa":            0.0,
                    "dp_total_kPa":           0.0,
                    "velocity_m_s":           0.0,
                    "pressure_drop_mbar_m":   0.0,
                    "mass_flow_kg_h":         0.0,
                }

            dp_results[eid] = dp_data

        self._dp_results = dp_results
        return dp_results

    # ------------------------------------------------------------------
    # Critical path
    # ------------------------------------------------------------------

    def find_critical_path(self) -> Tuple[List[str], float]:
        """Find the pipe path with highest total pressure drop."""
        if not hasattr(self, "_dp_results"):
            self.calculate_pressure_drops()

        chiller_nodes = [
            nid for nid, n in self.nodes.items() if n.get("type") == "CHILLER"
        ]
        fan_coil_nodes = [
            nid for nid, n in self.nodes.items() if n.get("type") == "FAN_COIL"
        ]

        if not chiller_nodes or not fan_coil_nodes:
            return [], 0.0

        chiller_id = chiller_nodes[0]
        best_path_edges: List[str] = []
        best_dp = 0.0

        for fc_id in fan_coil_nodes:
            try:
                path_nodes = nx.shortest_path(self.graph, chiller_id, fc_id)
            except nx.NetworkXNoPath:
                continue

            path_edges = []
            path_dp = 0.0
            for i in range(len(path_nodes) - 1):
                u = path_nodes[i]
                v = path_nodes[i + 1]
                for eid, edge in self.edges.items():
                    if edge["source"] == u and edge["target"] == v:
                        path_edges.append(eid)
                        path_dp += self._dp_results[eid]["dp_total_Pa"]
                        break

            # Add fan coil internal pressure drop
            fc_node = self.nodes.get(fc_id, {})
            props = fc_node.get("props", {})
            fc_model = props.get("model", fc_node.get("model", "Kampmann_KaCool_W_Size4"))
            try:
                if fc_model == "custom":
                    fc_dp_kPa = float(props.get("dp_kPa", fc_node.get("dp_kPa", 0.0)))
                else:
                    fc_dp_kPa = get_fan_coil_dp_kPa(fc_model)
                path_dp += fc_dp_kPa * 1000.0
            except Exception:
                pass

            if path_dp > best_dp:
                best_dp = path_dp
                best_path_edges = path_edges

        self._critical_path = best_path_edges
        self._critical_path_dp_Pa = best_dp
        return best_path_edges, best_dp

    # ------------------------------------------------------------------
    # Pump adequacy — head from chiller node props
    # ------------------------------------------------------------------

    def check_pump_adequacy(self) -> Dict[str, Any]:
        """
        Compare pump head (from chiller node) with system pressure drop.
        Pump head is read from the chiller node's props dict first,
        then falls back to the library chiller data.
        """
        if not hasattr(self, "_critical_path_dp_Pa"):
            self.find_critical_path()

        chiller_nodes = [
            nid for nid, n in self.nodes.items() if n.get("type") == "CHILLER"
        ]
        pump_head_Pa = 0.0
        if chiller_nodes:
            chiller_id = chiller_nodes[0]
            chiller_node = self.nodes[chiller_id]
            props = chiller_node.get("props", {})

            # Prefer pump head from node props (user-entered or library-loaded)
            if "pump_head_kPa" in props:
                pump_head_Pa = float(props["pump_head_kPa"]) * 1000.0
            elif "pump_head_kPa" in chiller_node:
                pump_head_Pa = float(chiller_node["pump_head_kPa"]) * 1000.0
            else:
                model = props.get("model", chiller_node.get("model", "Climaveneta_iBX2_G07_27Y"))
                try:
                    if model == "custom":
                        pump_head_Pa = float(props.get("pump_head_kPa_val", 96.8)) * 1000.0
                    else:
                        chiller_data = get_chiller(model)
                        pump_head_Pa = chiller_data["pump_head_kPa"] * 1000.0
                except Exception:
                    pump_head_Pa = 96800.0

        system_dp_Pa = self._critical_path_dp_Pa
        margin_Pa = pump_head_Pa - system_dp_Pa

        return {
            "adequate":       margin_Pa >= 0,
            "pump_head_kPa":  pump_head_Pa / 1000.0,
            "system_dp_kPa":  system_dp_Pa / 1000.0,
            "margin_kPa":     margin_Pa / 1000.0,
            "margin_pct":     (margin_Pa / pump_head_Pa * 100.0) if pump_head_Pa > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Heat load validation
    # ------------------------------------------------------------------

    def check_heat_load(self) -> Dict[str, Any]:
        """Check if total indoor unit loads <= outdoor unit rated capacity."""
        total_indoor_W = sum(
            self._get_fan_coil_flow_W(n)
            for n in self.nodes.values()
            if n.get("type") == "FAN_COIL"
        )

        chiller_capacity_W = 0.0
        chiller_model = None
        for n in self.nodes.values():
            if n.get("type") == "CHILLER":
                props = n.get("props", {})
                model = props.get("model", n.get("model", "Climaveneta_iBX2_G07_27Y"))
                chiller_model = model
                try:
                    if model == "custom":
                        chiller_capacity_W = float(props.get("cooling_capacity_kW", 27.2)) * 1000.0
                    else:
                        chiller_data = get_chiller(model)
                        chiller_capacity_W = chiller_data["cooling_capacity_kW"] * 1000.0
                except Exception:
                    chiller_capacity_W = 27200.0
                break

        utilisation_pct = (
            total_indoor_W / chiller_capacity_W * 100.0
        ) if chiller_capacity_W > 0 else 0.0

        return {
            "total_indoor_W":       total_indoor_W,
            "total_indoor_kW":      total_indoor_W / 1000.0,
            "chiller_capacity_W":   chiller_capacity_W,
            "chiller_capacity_kW":  chiller_capacity_W / 1000.0,
            "adequate":             total_indoor_W <= chiller_capacity_W,
            "utilisation_pct":      utilisation_pct,
            "chiller_model":        chiller_model,
        }

    # ------------------------------------------------------------------
    # System water volume
    # ------------------------------------------------------------------

    def calculate_water_volume(self) -> Dict[str, Any]:
        """Calculate total water content in the system."""
        if not hasattr(self, "_pipe_sizes"):
            self.size_all_pipes()

        total_volume_L = 0.0
        volume_by_dn: Dict[int, float] = {}

        for eid, edge in self.edges.items():
            dn = self._pipe_sizes.get(eid, 16)
            length_m = edge.get("length_m", 1.0)
            vol = calculate_pipe_water_content(dn, length_m)
            total_volume_L += vol
            volume_by_dn[dn] = volume_by_dn.get(dn, 0.0) + vol

        chiller_flow_m3h = 5.16
        for n in self.nodes.values():
            if n.get("type") == "CHILLER":
                props = n.get("props", {})
                model = props.get("model", n.get("model", "Climaveneta_iBX2_G07_27Y"))
                try:
                    if model == "custom":
                        chiller_flow_m3h = float(props.get("flow_rate_m3h", 5.16))
                    else:
                        chiller_data = get_chiller(model)
                        chiller_flow_m3h = chiller_data["flow_rate_m3h"]
                except Exception:
                    pass
                break

        min_volume_L = chiller_flow_m3h * 1000.0 / 60.0 * 3.0

        return {
            "total_volume_L":  total_volume_L,
            "min_required_L":  min_volume_L,
            "adequate":        total_volume_L >= min_volume_L,
            "volume_by_dn":    volume_by_dn,
        }

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Execute the full hydraulic calculation and return all results."""
        flows       = self.calculate_flows()
        pipe_sizes  = self.size_all_pipes()
        dp_results  = self.calculate_pressure_drops()
        crit_path, crit_dp = self.find_critical_path()
        pump_check  = self.check_pump_adequacy()
        load_check  = self.check_heat_load()
        vol_check   = self.calculate_water_volume()

        segment_summary = []
        for eid, edge in self.edges.items():
            src_label = self.nodes.get(edge["source"], {}).get("label", edge["source"])
            tgt_label = self.nodes.get(edge["target"], {}).get("label", edge["target"])
            segment_summary.append({
                "edge_id":           eid,
                "from":              src_label,
                "to":                tgt_label,
                "flow_W":            flows.get(eid, 0.0),
                "flow_kW":           flows.get(eid, 0.0) / 1000.0,
                "nominal_dn":        pipe_sizes.get(eid, 16),
                "length_m":          edge.get("length_m", 0.0),
                "velocity_m_s":      dp_results[eid]["velocity_m_s"],
                "dp_pipe_Pa":        dp_results[eid]["dp_pipe_Pa"],
                "dp_fittings_Pa":    dp_results[eid]["dp_fittings_Pa"],
                "dp_total_Pa":       dp_results[eid]["dp_total_Pa"],
                "dp_total_kPa":      dp_results[eid]["dp_total_kPa"],
                "on_critical_path":  eid in crit_path,
                "water_content_L":   vol_check["volume_by_dn"].get(pipe_sizes.get(eid, 16), 0.0),
            })

        return {
            "segment_summary":       segment_summary,
            "edge_flows":            flows,
            "pipe_sizes":            pipe_sizes,
            "dp_results":            dp_results,
            "critical_path":         crit_path,
            "critical_path_dp_Pa":   crit_dp,
            "pump_check":            pump_check,
            "load_check":            load_check,
            "water_volume":          vol_check,
        }
