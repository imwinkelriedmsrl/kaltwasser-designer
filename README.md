# Kaltwasser Designer

**Chilled Water System Design Tool for HVAC Engineers**

A professional web application for designing, calculating, and documenting chilled water (Kaltwasser) pipe networks in buildings.

## Features

- **Network Editor**: Graphically draw chilled water pipe networks with outdoor chillers and indoor fan coils
- **Hydraulic Calculation**: Automatic flow rate distribution and pressure drop calculation
- **Automatic Pipe Sizing**: Select optimal Geberit FlowFit pipe diameters based on velocity and pressure drop criteria
- **Material List (BOM)**: Complete bill of materials with pipe lengths, fittings, and equipment
- **Technical Report**: System summary, performance data, and printable documentation

## Equipment Supported

### Outdoor Unit
- **Climaveneta i-BX2-G07 27Y**: 27.2 kW air-cooled chiller, R32, 7/12°C, 30% ethylene glycol

### Indoor Units
- **Kampmann KaCool W (324001242000M1)**: Wall-mounted fan coil, 2-pipe, size 4, up to 4040 W cooling

## Pipe System
- **Geberit FlowFit**: Sizes Ø16 through Ø75 mm
- Pressure drop tables for 30% and 40% ethylene glycol at 7/12°C

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Usage

1. Open the **Network Editor** and add equipment nodes (chiller, fan coils)
2. Connect nodes with pipe segments, enter lengths and fittings
3. Go to **Hydraulic Calculation** and run the calculation
4. Review pipe sizes, flow rates, and pressure drops
5. Check the **Material List** for the complete BOM
6. Generate the **Technical Report** for documentation

## Calculation Standards

- Flow distribution based on balanced pressure drop method
- Pipe sizing: max 1.5 m/s (main pipes), 1.0 m/s (branches), max 150 Pa/m
- Fitting losses via zeta (ζ) values per VDI 2035
- Critical path analysis for pump adequacy check

## Requirements

- Python 3.10+
- See `requirements.txt` for package dependencies

## License

Internal use — HVAC engineering tool.
