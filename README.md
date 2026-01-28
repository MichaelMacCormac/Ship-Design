# Ship Design & Economic Analyzer

A comprehensive PySide6 application for conceptual ship design, propulsion analysis, and economic modeling. This tool allows users to optimize ship dimensions, analyze nuclear and alternative fuel viability, and visualize operational envelopes.

## Features

* **Hull Optimization:** Calculates optimal dimensions (L, B, T, D) for Tankers, Bulk Carriers, and Container Ships.
* **Propulsion Physics:** Physics-based modeling for:
    * Nuclear Propulsion (Saturated Steam Cycle)
    * Hydrogen & Ammonia (ICE and Fuel Cells)
    * Conventional Diesel & LNG
* **Economic Analysis:** detailed CAPEX/OPEX breakdown including Carbon Tax ($/tCO2), Reactor Decommissioning costs, and Required Freight Rate (RFR).
* **Visual Analytics:** * 2D Parameter sweeping (e.g., Speed vs. RFR).
    * 3D Wireframe plotting for multi-variable analysis.
* **TEU Capacity:** specialized algorithms for container ship volume estimation.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/ship-design-tool.git](https://github.com/YOUR_USERNAME/ship-design-tool.git)
    cd ship-design-tool
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main application entry point:
```bash
python ship_des_view_widget.py
