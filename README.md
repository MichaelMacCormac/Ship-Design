# Ship Design & Economic Analyser (SDEA)

**A physics-based conceptual design tool for next-generation maritime vessels.**

SDEA is a powerful Python application designed for naval architects, researchers, and maritime economists. It goes beyond simple empirical formulas by integrating an iterative hull solver with detailed economic modeling for alternative fuels—including Nuclear, Hydrogen, Ammonia, and Methanol.

Whether you are designing a conventional bulk carrier or a nuclear-powered container ship, SDEA calculates the optimal dimensions, power requirements, and operational costs to determine commercial viability.

## Key Features

### 1. Multi-Physics Hull Optimization
* **Iterative Solver:** Automatically solves for Length ($L_{bp}$), Breadth ($B$), Draft ($T$), and Block Coefficient ($C_B$) based on deadweight or TEU targets.
* **Volume Constraints:** Features a specialized **Phase 3 Volume Solver** that detects when low-density fuels (like Liquid Hydrogen) require hull expansion and auto-adjusts dimensions to fit the fuel tanks.
* **Resistance Prediction:** Calculates frictional, wave-making, and air resistance, with corrections for shallow water and hull roughness.
* **Energy Saving Devices (ESD):** Model the impact of Air Lubrication Systems and Wind Assist technologies on power reduction.

### 2. Next-Gen Propulsion & Fuels
Simulate the transition to green shipping with a comprehensive library of fuel technologies. The physics engine accounts for specific energy density ($LHV$), storage volume penalties (cryogenics/insulation), and machinery mass.
* **Conventional:** Direct/Geared Diesel, Steam Turbines, LNG (Dual Fuel).
* **Alternative:** Hydrogen (ICE & Fuel Cell), Ammonia, Methanol, Battery Electric.
* **Nuclear:** Dedicated modeling for Saturated Steam Cycle reactors, including core life, reactor specific mass ($kg/kW$), and decommissioning fund analysis.

### 3. Economic & Commercial Modeling
* **RFR Calculation:** Precise calculation of **Required Freight Rate** ($/tonne or $/TEU) to break even.
* **Carbon Economics:** Integrated **Carbon Tax** modeling ($/tCO_2$) to stress-test designs against future regulations.
* **Cold Chain Analysis:** Detailed auxiliary load analysis for refrigerated cargo (Reefers), including premium freight income calculations.

### 4. Regulatory Compliance (IMO)
* **EEDI Phase 3:** Automatically calculates the attained Energy Efficiency Design Index against reference baselines.
* **CII Rating:** Estimates the Carbon Intensity Indicator rating (A to E) based on the operational profile.

### 5. Advanced Visualization & Analysis
* **Battle Mode:** Run head-to-head comparisons of two engine types (e.g., *Nuclear vs. Ammonia*) across a speed range to visualize the economic "crossover point".
* **Range Analysis:** Perform 1D or 2D parameter sweeps (e.g., *Speed vs. Block Coefficient*) and export results to CSV or 3D wireframe plots.
* **Route Profiler:** Define custom voyages (e.g., *Asia-Europe via Suez*) with segmented speed profiles to get accurate annual fuel consumption.

## 🛠️ Installation

### Prerequisites
* Python 3.8+
* pip

### Setup
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/MichaelMacCormac/Ship-Design.git](https://github.com/MichaelMacCormac/Ship-Design.git)
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
python ship_des_view_widget.py
```

### Quick Start Guide
1.  **Select Ship Type:** Choose from Tanker, Bulk Carrier, Container Ship, Cruise Ship, or Superyacht from the dropdown menu.
2.  **Select Engine:** Pick a fuel technology (e.g., "Ammonia (Combustion)", "Hydrogen (Fuel Cell)", or "Nuclear Steam Turbine").
3.  **Input Targets:** Enter the desired Cargo Deadweight (tonnes) or TEU capacity in the input fields.
4.  **Set Speed/Range:** Define the service speed in knots and the operational range in nautical miles.
5.  **Calculate:** Click the **Calculate** button to initiate the iterative solver and determine the ship's optimal dimensions.
6.  **Analyze:** Review the results in the output window, use "Output Options" to customize data points, or use "Run & Plot Graph" to visualize parameter sweeps.

## Methodologies

* **Hydrodynamics:** Resistance and propulsion power are calculated using regression-based methods, accounting for Froude and Reynolds numbers to ensure hull efficiency.
* **Weights:** Lightship mass estimation includes detailed breakdowns for steel (using K1 coefficients), outfit (using intercept/slope factors), and machinery mass based on specific engine types.
* **Economics:** The tool employs a Net Present Value (NPV) approach to derive the Required Freight Rate (RFR), factoring in capital repayment, interest rates, annual fuel costs, and carbon taxes.
* **Volume Solver:** For volume-limited designs (like Container Ships or Hydrogen-powered vessels), the "Phase 3 Volume Solver" expands ship dimensions until the required cargo and fuel volumes fit within the hull.

## Project Structure

* `ship_des_view_widget.py`: The main application entry point containing the GUI, the core physics-based iteration loops, and the resistance/power calculators.
* `FuelConfig`: A central database class defining physics properties (LHV, Density, Efficiency) and mass factors for 10 distinct fuel/engine configurations.
* `ShipConfig`: A configuration class containing empirical constants for different ship types, including EEDI and CII reference line parameters.
* `RouteDialog`: A popup module used to calculate operational profiles and power factors for specific global trade routes.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for:
* Adding new fuel types or machinery data to the `FuelConfig` class.
* Refining the resistance regression formulas or adding new ship types.
* Improving the UI/UX and visualization capabilities.

## License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Disclaimer:** *This tool is intended for conceptual design and academic analysis. Validation with tank testing or CFD is required for final design stages.*