# Ship Design WORKING BETA

**A physics-based conceptual design tool for maritime vessels and fuel types.**

This is a Python application designed for naval architects. It goes beyond simple empirical formulas by integrating an iterative hull solver with detailed economic modeling for alternative fuels—including Nuclear, Hydrogen, Ammonia, and Methanol.

Facilitating a high-level analysis of differing fuel, ship types and configurations to find base parameters that can be used as a starting point for further exploration.

## Key Features

### 1. Hull Optimisation
* **Iterative Solver:** Automatically solves for Length ($L_{bp}$), Breadth ($B$), Draught ($T$), and Block Coefficient ($C_B$) based on deadweight or TEU targets (if Container Ship is selected).
* **Volume Constraints:** Features a volumer limiter that detects when low-density fuels (like Liquid Hydrogen) require hull expansion and auto-adjusts dimensions to fit the fuel tanks.
* **Resistance Prediction:** Calculates frictional, wave-making, and air resistance.
* **Energy Saving Devices (ESD):** Ability to model the impact of Air Lubrication Systems and Wind Assist technologies on power reduction.

### 2. Next-Gen Propulsion & Fuels
A multitude of alternative fuel types. The volume constraints account for specific energy density, storage volume penalties (cryogenics/insulation), and machinery mass.
* **Conventional:** Direct/Geared Diesel, Steam Turbines, LNG (Dual Fuel).
* **Alternative:** Hydrogen (ICE & Fuel Cell), Ammonia, Methanol, Battery Electric.
* **Nuclear:** Dedicated modeling for Small Modular reactors, including core life, reactor specific mass ($kg/kW$) and decommissioning fund analysis.

### 3. Economic & Commercial Modeling
* **RFR Calculation:** Precise calculation of **Required Freight Rate** (tonne or TEU) to break even.
* **Year-by-Year Cash Flow:** RFR is derived from a discounted yearly cash flow (loan repayments, OPEX, maintenance, fuel, carbon tax, nuclear core/decommissioning, premium income). Ship life can differ from the loan term, and the full table exports to CSV.
* **Dynamic Fuel & Carbon Prices:** "Price paths..." sets how the fuel price and carbon tax move from the delivery year onwards: flat, constant %/yr escalation, or calendar-year keyframes (% of base, interpolated). The paths scale the base price fields, so sweeps and battle mode still work. The report shows levelised (PV-weighted) prices, and fuel/carbon escalation are available as sweep parameters.
* **Carbon Economics:** Integrated **Carbon Tax** modeling to stress-test designs against future regulations.
* **Cold Chain Analysis:** Detailed auxiliary load analysis for refrigerated cargo (Reefers), including premium freight income calculations.

### 4. Emission Regulatory Compliance
* **EEDI:** Automatically calculates the attained Energy Efficiency Design Index against reference baselines.
* **CII Rating:** Estimates the Carbon Intensity Indicator rating (A to E) based on the operational profile.

### 5. Advanced Visualisation & Analysis
* **Battle Mode:** Run head-to-head comparisons of two engine types (e.g., *Nuclear vs. Ammonia*) across a speed range to visualise their economic impacts.
* **Range Analysis:** Perform 1D or 2D parameter sweeps (e.g., *Speed vs. Block Coefficient*) and export the results to CSV or 3D wireframe plots.
* **Route Profiler:** Define custom voyages (e.g., *Asia-Europe via Suez*) with segmented speed profiles to get accurate annual fuel consumption.

## Installation

### Prerequisites
* Python 3.8+
* pip

### Setup
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/MichaelMacCormac/Ship-Design.git
    cd Ship-Design
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: Key dependencies include `PySide6` for the GUI, `matplotlib` for plotting, and `numpy` for calculations.)*

## Usage

Run the main application interface:
```bash
python main.py
```

### Quick Start Guide
1.  **Select Ship Type:** Choose from Tanker, Bulk Carrier, Container Ship, Cruise Ship, or Superyacht from the dropdown menu.
2.  **Select Engine:** Pick a fuel technology (e.g., "Ammonia (Combustion)", "Hydrogen (Fuel Cell)", or "Nuclear SMR").
3.  **Input Targets:** Enter the desired Cargo Deadweight (tonnes) or TEU capacity in the input fields.
4.  **Set Speed/Range:** Define the service speed in knots and the operational range in nautical miles.
5.  **Calculate:** Click the **Calculate** button to initiate the iterative solver and determine the ship's optimal dimensions.
6.  **Analyse:** Review the results in the output window, use "Output Options" to customize data points, or use "Run & Plot Graph" to visualize parameter sweeps.

## Methodologies

* **Hydrodynamics:** Resistance and propulsion power are calculated using regression-based methods, accounting for Froude and Reynolds numbers to ensure hull efficiency.
* **Weights:** Lightship mass estimation includes detailed breakdowns for steel (using K1 coefficients), outfit (using intercept/slope factors), and machinery mass based on specific engine types.
* **Economics:** The Required Freight Rate is the freight rate at which the present value of revenue equals the present value of costs: `RFR = PV(costs − premium income) / PV(cargo)`, discounted at the interest rate. Loan payments run for the repayment term; cargo and operating costs run for the ship life. With ship life equal to the loan term and constant prices, this equals the classic annualised `(CRF·capex + annual costs) / annual cargo`. Every cost line accepts a per-year array, so price paths can be plugged in.
* **Volume Solver:** For volume-limited designs (like Container Ships or Hydrogen-powered vessels), the Volume Limiter expands ship dimensions until the required cargo and fuel volumes fit within the hull.

## Project Structure

* `main.py`: Application entry point.
* `ship_des_view_widget_holtrop.py`: The GUI (`ShipDesViewWidget`), plus range analysis, battle mode, plotting and the text report. It inherits the solver below and copies its form values onto the solver inputs.
* `ship_solver.py`: `ShipDesignSolver`, the Qt-free physics and economics: the iterative hull solver, resistance (Taylor / Holtrop-Mennen), propeller, masses, volume limiter, costs, EEDI/CII.
* `economics.py`: The year-by-year cash flow (`build_cash_flow`) and RFR.
* `ship_config.py`: Static tables: `FuelConfig` (LHV, density, efficiency, mass/volume factors per fuel), `ShipConfig` (per-ship-type constants, EEDI/CII reference lines), `ResistanceMethodConfig`, `EmpiricalBasisConfig`.
* `RouteDialog`: A popup module used to calculate operational profiles and power factors for specific global trade routes.
* `tests/`: Headless unit tests (`python -m unittest discover tests`).

### Running the solver without the GUI

```python
from ship_solver import ShipDesignSolver

s = ShipDesignSolver()
s.set_inputs(ship_name="Tanker", engine_name="Ammonia (Combustion)",
             m_Weight=50000.0, m_Speed=15.0, m_Fuel=700.0, m_LHV=18.6,
             m_ShipLife=25.0)
if s.solve():
    print(s.results()["RFR($/tonne or $/TEU)"], s.cash_flow.pv_costs)
else:
    print(s.solver_errors)
```

`set_inputs` rejects unknown attribute names. After `solve()`, `s.cash_flow` holds the yearly table (`s.cash_flow.to_rows()`).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for:
* Adding new fuel types or machinery data to the `FuelConfig` class.
* Refining the resistance regression formulas or adding new ship types.
* Improving the UI/UX and visualization capabilities.

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Disclaimer:** *This tool is intended for conceptual design and academic analysis. Validation with tank testing or CFD is required for final design stages.*