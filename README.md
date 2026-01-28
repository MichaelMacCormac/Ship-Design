# Ship Design & Economic Analyser WORKING BETA VERSION

A comprehensive Python application for conceptual ship design, propulsion analysis, and economic modeling. This tool allows users to optimise ship dimensions, analyse nuclear and alternative fuel viability, and visualise operational envelopes.

## Features

* **Hull Optimisation:** Calculates optimal dimensions (L, B, T, D) for Tankers, Bulk Carriers, and Container Ships.
* **Propulsion Physics:** Physics-based modeling for:
    * Nuclear Propulsion (Saturated Steam Cycle)
    * Hydrogen & Ammonia (ICE and Fuel Cells)
    * Conventional Diesel & LNG
* **Economic Analysis:** detailed CAPEX/OPEX breakdown including Carbon Tax ($/tCO2), Reactor Decommissioning costs, and Required Freight Rate (RFR).
* **Visual Analytics:**
    * 2D Parameter sweeping (e.g., Speed vs. RFR).
    * 3D Wireframe plotting for multi-variable analysis.
* **TEU Capacity:** specialised algorithms for container ship volume estimation.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/MichaelMacCormac/Ship-Design.git](https://github.com/MichaelMacCormac/Ship-Design.git)
    cd Ship-Design
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main application entry point:
```bash
python ship_des_view_widget.py