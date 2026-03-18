# TODO — Kaltwasser Designer

## Hydraulic Calculation

1. **System topology**: Parse the pipe network as a directed graph (NetworkX) — build adjacency from session_state edges
2. **Flow distribution**: For parallel branches, calculate flow splits based on balanced pressure drops (Hardy-Cross iteration)
3. **Pipe sizing criteria**:
   - Max velocity: 1.5 m/s for mains, 1.0 m/s for branches
   - Max pressure drop: 150 Pa/m = 1.5 mbar/m
   - Select smallest FlowFit pipe that satisfies both criteria
4. **Pressure drop calculation**:
   - Straight pipe: R × L (mbar/m × m)
   - Fittings using zeta (ζ) values:
     - T-piece (flow through): ζ = 0.5
     - T-piece (branch): ζ = 1.5
     - 90° elbow: ζ = 1.0
     - Coupling/straight connector: ζ = 0.2
     - Isolation valve (fully open): ζ = 0.5
     - Balancing valve: ζ = 2.0–10.0 (adjustable)
     - Air vent: negligible
   - ΔP_fitting = ζ × ρ × v² / 2 [Pa]
5. **Critical path**: Find path with highest total pressure drop (determines pump requirements)
6. **Pump check**: Verify outdoor unit available pump head ≥ total system pressure drop on critical path
7. **Glycol correction**: Apply glycol properties for flow/pressure calculations (density, viscosity, cp)
8. **Heat load validation**: Sum of all indoor unit cooling loads ≤ outdoor unit rated capacity
9. **Minimum system volume**: Calculate total water content of all pipes, verify ≥ minimum required (typically 3× system flow rate in litres)
10. **Frosting check**: Supply temperature ≥ freeze point for selected glycol type and concentration

## Network Editor

- [ ] Drag-and-drop node repositioning
- [ ] Undo/redo for network edits
- [ ] Snap-to-grid alignment
- [ ] Auto-routing of pipe connections
- [ ] Import DXF floor plans as background image
- [ ] Copy/paste node groups

## Material List

- [ ] Export to Excel (openpyxl) with formatted table
- [ ] Export to PDF (fpdf2) with company logo
- [ ] Price database integration (Geberit pricelists)
- [ ] Thermal insulation sizing and material list
- [ ] Hanger/support calculation (spacing per diameter)

## Technical Report

- [ ] Part-load performance curves
- [ ] Annual energy simulation (degree-hours method)
- [ ] CO₂ equivalent refrigerant charge calculation
- [ ] Noise immission calculation (distance attenuation)
- [ ] Hydraulic schematic export (P&ID style)

## Data

- [ ] Add Geberit FlowFit fitting dimensions (for isometric drawing)
- [ ] Add more chiller models (Climaveneta, Aermec, Chiltrix)
- [ ] Add more fan coil models (Kampmann, Jaga, Zehnder)
- [ ] Propylene glycol pressure drop tables
- [ ] Water-only (0% glycol) tables

## Infrastructure

- [ ] User authentication (for saving projects)
- [ ] Project save/load to JSON file
- [ ] Cloud storage integration
- [ ] Multi-language support (DE/FR/IT/EN)
- [ ] Mobile-responsive layout
