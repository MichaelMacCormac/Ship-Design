# Validation against the clean ship database

Data: `data\ships_clean.csv`, split **validate** - 278 ship(s) of the tool's types with DWT and speed.

## Assumptions

- Each real ship is redesigned at its own type, speed and total deadweight (secant on the cargo target until total DW matches within 0.1 %).
- Lbp = LOA x Tanker 0.97, Bulk carrier 0.97, Container Ship 0.95, Cargo vessel 0.95, Cruise Ship 0.9, Superyacht 0.88; length errors also shown at +/-1 % on the ratio.
- Direct-drive diesel; RPM = database rpm where known, else 120 rpm; range = solver default; economics off.
- Database power = MCR: compared with installed P2 (includes the solver's 30 % margin); service P1 compared with 0.85 x MCR.
- Fields flagged implausible by the cleaning pipeline, and scantling draughts, are excluded from that field's comparison only.

## Solve rate

| Configuration | Attempted | Solved | RPM adjusted |
|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | 278 | 95 | 0 |
| Taylor / Legacy / Auto-RPM on | 278 | 261 | 177 |
| Taylor / Japan clean / Auto-RPM off | 278 | 59 | 0 |
| Taylor / Japan clean / Auto-RPM on | 278 | 262 | 218 |
| Holtrop / Legacy / Auto-RPM off | 278 | 82 | 0 |
| Holtrop / Legacy / Auto-RPM on | 278 | 247 | 171 |
| Holtrop / Japan clean / Auto-RPM off | 278 | 44 | 0 |
| Holtrop / Japan clean / Auto-RPM on | 278 | 262 | 222 |

## Accuracy (all types)

| Configuration | Quantity | n | Bias % | MAPE % | R² |
|---|---|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | Lbp | 88 | +6.8 | 8.9 | 0.887 |
| Taylor / Legacy / Auto-RPM off | Lbp (ratio +1%) | 88 | +5.8 | 8.2 | 0.896 |
| Taylor / Legacy / Auto-RPM off | Lbp (ratio -1%) | 88 | +7.8 | 9.6 | 0.876 |
| Taylor / Legacy / Auto-RPM off | B | 92 | -5.4 | 6.2 | 0.891 |
| Taylor / Legacy / Auto-RPM off | D | 92 | -8.1 | 11.1 | 0.627 |
| Taylor / Legacy / Auto-RPM off | T | 54 | +2.0 | 6.4 | 0.841 |
| Taylor / Legacy / Auto-RPM off | P installed vs MCR | 15 | +50.3 | 50.3 | -1.138 |
| Taylor / Legacy / Auto-RPM off | P service vs 0.85 MCR | 15 | +36.0 | 36.8 | -0.112 |
| Taylor / Legacy / Auto-RPM on | Lbp | 237 | +7.2 | 8.0 | 0.847 |
| Taylor / Legacy / Auto-RPM on | Lbp (ratio +1%) | 237 | +6.2 | 7.1 | 0.872 |
| Taylor / Legacy / Auto-RPM on | Lbp (ratio -1%) | 237 | +8.3 | 9.0 | 0.817 |
| Taylor / Legacy / Auto-RPM on | B | 251 | -2.0 | 6.2 | 0.878 |
| Taylor / Legacy / Auto-RPM on | D | 250 | -4.4 | 7.3 | 0.731 |
| Taylor / Legacy / Auto-RPM on | T | 138 | +1.5 | 4.9 | 0.930 |
| Taylor / Legacy / Auto-RPM on | P installed vs MCR | 23 | +50.5 | 50.5 | -1.172 |
| Taylor / Legacy / Auto-RPM on | P service vs 0.85 MCR | 23 | +36.2 | 36.7 | -0.168 |
| Taylor / Japan clean / Auto-RPM off | Lbp | 56 | -0.8 | 4.4 | 0.944 |
| Taylor / Japan clean / Auto-RPM off | Lbp (ratio +1%) | 56 | -1.8 | 4.4 | 0.938 |
| Taylor / Japan clean / Auto-RPM off | Lbp (ratio -1%) | 56 | +0.1 | 4.4 | 0.949 |
| Taylor / Japan clean / Auto-RPM off | B | 57 | -6.1 | 7.4 | 0.865 |
| Taylor / Japan clean / Auto-RPM off | D | 57 | -1.8 | 7.8 | 0.832 |
| Taylor / Japan clean / Auto-RPM off | T | 32 | +10.8 | 11.6 | 0.670 |
| Taylor / Japan clean / Auto-RPM off | P installed vs MCR | 15 | +56.8 | 56.8 | -1.589 |
| Taylor / Japan clean / Auto-RPM off | P service vs 0.85 MCR | 15 | +41.9 | 42.1 | -0.419 |
| Taylor / Japan clean / Auto-RPM on | Lbp | 238 | +1.2 | 3.3 | 0.955 |
| Taylor / Japan clean / Auto-RPM on | Lbp (ratio +1%) | 238 | +0.2 | 3.0 | 0.957 |
| Taylor / Japan clean / Auto-RPM on | Lbp (ratio -1%) | 238 | +2.2 | 3.8 | 0.949 |
| Taylor / Japan clean / Auto-RPM on | B | 252 | -0.1 | 6.5 | 0.851 |
| Taylor / Japan clean / Auto-RPM on | D | 251 | -0.3 | 4.9 | 0.869 |
| Taylor / Japan clean / Auto-RPM on | T | 136 | +5.2 | 6.8 | 0.851 |
| Taylor / Japan clean / Auto-RPM on | P installed vs MCR | 23 | +57.7 | 57.7 | -1.793 |
| Taylor / Japan clean / Auto-RPM on | P service vs 0.85 MCR | 23 | +42.7 | 42.8 | -0.559 |
| Holtrop / Legacy / Auto-RPM off | Lbp | 77 | +6.9 | 9.3 | 0.889 |
| Holtrop / Legacy / Auto-RPM off | Lbp (ratio +1%) | 77 | +5.8 | 8.6 | 0.896 |
| Holtrop / Legacy / Auto-RPM off | Lbp (ratio -1%) | 77 | +8.0 | 10.0 | 0.879 |
| Holtrop / Legacy / Auto-RPM off | B | 79 | -5.0 | 5.9 | 0.905 |
| Holtrop / Legacy / Auto-RPM off | D | 79 | -10.1 | 11.9 | 0.611 |
| Holtrop / Legacy / Auto-RPM off | T | 46 | +1.5 | 6.1 | 0.835 |
| Holtrop / Legacy / Auto-RPM off | P installed vs MCR | 14 | +36.5 | 36.7 | -0.672 |
| Holtrop / Legacy / Auto-RPM off | P service vs 0.85 MCR | 14 | +23.5 | 25.1 | 0.254 |
| Holtrop / Legacy / Auto-RPM on | Lbp | 223 | +7.2 | 8.0 | 0.829 |
| Holtrop / Legacy / Auto-RPM on | Lbp (ratio +1%) | 223 | +6.1 | 7.1 | 0.855 |
| Holtrop / Legacy / Auto-RPM on | Lbp (ratio -1%) | 223 | +8.2 | 9.0 | 0.797 |
| Holtrop / Legacy / Auto-RPM on | B | 237 | -1.9 | 6.3 | 0.848 |
| Holtrop / Legacy / Auto-RPM on | D | 236 | -4.8 | 7.3 | 0.690 |
| Holtrop / Legacy / Auto-RPM on | T | 126 | +1.5 | 5.2 | 0.899 |
| Holtrop / Legacy / Auto-RPM on | P installed vs MCR | 23 | +35.0 | 35.1 | -0.011 |
| Holtrop / Legacy / Auto-RPM on | P service vs 0.85 MCR | 23 | +22.1 | 23.1 | 0.559 |
| Holtrop / Japan clean / Auto-RPM off | Lbp | 42 | +0.3 | 4.0 | 0.966 |
| Holtrop / Japan clean / Auto-RPM off | Lbp (ratio +1%) | 42 | -0.7 | 3.8 | 0.964 |
| Holtrop / Japan clean / Auto-RPM off | Lbp (ratio -1%) | 42 | +1.3 | 4.2 | 0.965 |
| Holtrop / Japan clean / Auto-RPM off | B | 43 | -5.6 | 7.1 | 0.868 |
| Holtrop / Japan clean / Auto-RPM off | D | 43 | -1.9 | 7.1 | 0.806 |
| Holtrop / Japan clean / Auto-RPM off | T | 22 | +9.7 | 10.9 | 0.709 |
| Holtrop / Japan clean / Auto-RPM off | P installed vs MCR | 14 | +37.0 | 37.0 | -0.384 |
| Holtrop / Japan clean / Auto-RPM off | P service vs 0.85 MCR | 14 | +24.0 | 25.3 | 0.384 |
| Holtrop / Japan clean / Auto-RPM on | Lbp | 238 | +1.2 | 3.2 | 0.955 |
| Holtrop / Japan clean / Auto-RPM on | Lbp (ratio +1%) | 238 | +0.2 | 3.0 | 0.957 |
| Holtrop / Japan clean / Auto-RPM on | Lbp (ratio -1%) | 238 | +2.2 | 3.8 | 0.950 |
| Holtrop / Japan clean / Auto-RPM on | B | 252 | -0.2 | 6.5 | 0.851 |
| Holtrop / Japan clean / Auto-RPM on | D | 251 | -0.3 | 4.9 | 0.868 |
| Holtrop / Japan clean / Auto-RPM on | T | 136 | +5.1 | 6.8 | 0.852 |
| Holtrop / Japan clean / Auto-RPM on | P installed vs MCR | 23 | +36.9 | 36.9 | -0.114 |
| Holtrop / Japan clean / Auto-RPM on | P service vs 0.85 MCR | 23 | +23.9 | 24.6 | 0.504 |

## Accuracy by ship type

| Configuration | Type | Quantity | n | Bias % | MAPE % | R² |
|---|---|---|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | Bulk carrier | Lbp | 38 | +4.1 | 5.1 | 0.854 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | B | 40 | -6.5 | 8.1 | 0.677 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | T | 26 | +5.5 | 6.0 | 0.829 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | P installed vs MCR | 12 | +55.3 | 55.3 | -1.772 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 12 | +40.5 | 40.5 | -0.470 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.3 | 16.3 | -40.639 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | B | 3 | -6.0 | 6.0 | -0.379 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -80.819 |
| Taylor / Legacy / Auto-RPM off | Container Ship | Lbp | 25 | +2.8 | 8.5 | 0.904 |
| Taylor / Legacy / Auto-RPM off | Container Ship | B | 25 | -6.4 | 6.4 | 0.875 |
| Taylor / Legacy / Auto-RPM off | Container Ship | T | 16 | +3.5 | 3.5 | 0.921 |
| Taylor / Legacy / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +43.7 | 43.7 | nan |
| Taylor / Legacy / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +30.1 | 30.1 | nan |
| Taylor / Legacy / Auto-RPM off | Tanker | Lbp | 23 | +14.7 | 14.8 | -0.285 |
| Taylor / Legacy / Auto-RPM off | Tanker | B | 24 | -2.5 | 3.0 | 0.921 |
| Taylor / Legacy / Auto-RPM off | Tanker | T | 10 | -8.4 | 12.2 | 0.544 |
| Taylor / Legacy / Auto-RPM off | Tanker | P installed vs MCR | 1 | +4.0 | 4.0 | nan |
| Taylor / Legacy / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -5.9 | 5.9 | nan |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | Lbp | 156 | +5.8 | 6.1 | 0.861 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | B | 165 | -0.2 | 6.3 | 0.809 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | T | 100 | +2.3 | 4.5 | 0.927 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | P installed vs MCR | 17 | +57.0 | 57.0 | -3.206 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 17 | +42.1 | 42.1 | -1.301 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | Lbp | 5 | +10.8 | 10.8 | 0.869 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | B | 6 | -6.1 | 6.1 | 0.892 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | T | 4 | +0.5 | 5.5 | 0.850 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +40.5 | 40.5 | -0.150 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +27.1 | 27.1 | 0.398 |
| Taylor / Legacy / Auto-RPM on | Container Ship | Lbp | 25 | +2.8 | 8.5 | 0.904 |
| Taylor / Legacy / Auto-RPM on | Container Ship | B | 25 | -6.4 | 6.4 | 0.875 |
| Taylor / Legacy / Auto-RPM on | Container Ship | T | 16 | +3.5 | 3.5 | 0.921 |
| Taylor / Legacy / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +43.7 | 43.7 | nan |
| Taylor / Legacy / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +30.1 | 30.1 | nan |
| Taylor / Legacy / Auto-RPM on | Tanker | Lbp | 51 | +13.3 | 13.5 | 0.705 |
| Taylor / Legacy / Auto-RPM on | Tanker | B | 55 | -5.1 | 5.7 | 0.919 |
| Taylor / Legacy / Auto-RPM on | Tanker | T | 18 | -4.2 | 8.4 | 0.926 |
| Taylor / Legacy / Auto-RPM on | Tanker | P installed vs MCR | 2 | +11.3 | 11.3 | 0.923 |
| Taylor / Legacy / Auto-RPM on | Tanker | P service vs 0.85 MCR | 2 | +0.8 | 6.7 | 0.963 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | Lbp | 22 | -0.4 | 3.3 | 0.949 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | B | 22 | -4.8 | 7.4 | 0.831 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | T | 14 | +9.7 | 10.2 | 0.764 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | P installed vs MCR | 12 | +63.7 | 63.7 | -2.593 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 12 | +48.1 | 48.1 | -1.022 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.3 | 16.3 | -40.639 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | B | 3 | -6.0 | 6.0 | -0.379 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -80.819 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | Lbp | 22 | -2.6 | 4.8 | 0.910 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | B | 22 | -8.2 | 8.4 | 0.717 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | T | 14 | +12.4 | 12.4 | 0.420 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +39.6 | 39.6 | nan |
| Taylor / Japan clean / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +26.3 | 26.3 | nan |
| Taylor / Japan clean / Auto-RPM off | Tanker | Lbp | 10 | -1.3 | 3.3 | 0.880 |
| Taylor / Japan clean / Auto-RPM off | Tanker | B | 10 | -4.2 | 5.5 | 0.720 |
| Taylor / Japan clean / Auto-RPM off | Tanker | T | 2 | +23.0 | 23.0 | -13.384 |
| Taylor / Japan clean / Auto-RPM off | Tanker | P installed vs MCR | 1 | +8.5 | 8.5 | nan |
| Taylor / Japan clean / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -1.9 | 1.9 | nan |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | Lbp | 161 | +1.7 | 2.8 | 0.962 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | B | 170 | +2.1 | 7.2 | 0.802 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | T | 102 | +4.0 | 5.7 | 0.898 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | P installed vs MCR | 18 | +64.3 | 64.3 | -2.981 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 18 | +48.7 | 48.7 | -1.264 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | Lbp | 5 | +10.8 | 10.8 | 0.869 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | B | 6 | -6.1 | 6.1 | 0.892 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | T | 4 | +0.5 | 5.5 | 0.850 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +40.5 | 40.5 | -0.150 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +27.1 | 27.1 | 0.398 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | Lbp | 25 | -2.8 | 4.7 | 0.918 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | B | 25 | -8.6 | 8.9 | 0.707 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | T | 16 | +12.9 | 12.9 | 0.414 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +39.6 | 39.6 | nan |
| Taylor / Japan clean / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +26.3 | 26.3 | nan |
| Taylor / Japan clean / Auto-RPM on | Tanker | Lbp | 47 | +0.8 | 3.2 | 0.967 |
| Taylor / Japan clean / Auto-RPM on | Tanker | B | 51 | -2.5 | 3.2 | 0.967 |
| Taylor / Japan clean / Auto-RPM on | Tanker | T | 14 | +6.2 | 7.9 | 0.659 |
| Taylor / Japan clean / Auto-RPM on | Tanker | P installed vs MCR | 1 | +8.5 | 8.5 | nan |
| Taylor / Japan clean / Auto-RPM on | Tanker | P service vs 0.85 MCR | 1 | -1.9 | 1.9 | nan |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | Lbp | 28 | +3.8 | 5.2 | 0.822 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | B | 28 | -5.7 | 7.9 | 0.713 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | T | 19 | +4.9 | 5.6 | 0.684 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | P installed vs MCR | 11 | +39.2 | 39.2 | -2.290 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 11 | +26.0 | 26.0 | -0.456 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.2 | 16.2 | -40.239 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | B | 3 | -6.1 | 6.1 | -0.395 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -82.281 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | Lbp | 25 | +2.8 | 8.5 | 0.902 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | B | 25 | -6.4 | 6.4 | 0.874 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | T | 16 | +3.5 | 3.5 | 0.923 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +40.8 | 40.8 | nan |
| Holtrop / Legacy / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +27.4 | 27.4 | nan |
| Holtrop / Legacy / Auto-RPM off | Tanker | Lbp | 22 | +14.6 | 14.8 | -0.255 |
| Holtrop / Legacy / Auto-RPM off | Tanker | B | 23 | -2.5 | 3.0 | 0.920 |
| Holtrop / Legacy / Auto-RPM off | Tanker | T | 9 | -8.0 | 12.2 | 0.584 |
| Holtrop / Legacy / Auto-RPM off | Tanker | P installed vs MCR | 1 | -1.4 | 1.4 | nan |
| Holtrop / Legacy / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -10.8 | 10.8 | nan |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | Lbp | 145 | +5.7 | 6.0 | 0.827 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | B | 154 | -0.1 | 6.5 | 0.712 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | T | 91 | +2.2 | 4.7 | 0.907 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | P installed vs MCR | 17 | +38.3 | 38.3 | -0.775 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 17 | +25.2 | 25.2 | 0.225 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | Lbp | 5 | +10.7 | 10.7 | 0.871 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | B | 6 | -6.1 | 6.1 | 0.891 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | T | 4 | +0.5 | 5.5 | 0.852 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +27.0 | 27.0 | 0.665 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +14.9 | 14.9 | 0.893 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | Lbp | 25 | +2.8 | 8.5 | 0.902 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | B | 25 | -6.4 | 6.4 | 0.874 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | T | 16 | +3.5 | 3.5 | 0.923 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +40.8 | 40.8 | nan |
| Holtrop / Legacy / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +27.4 | 27.4 | nan |
| Holtrop / Legacy / Auto-RPM on | Tanker | Lbp | 48 | +13.4 | 13.6 | 0.605 |
| Holtrop / Legacy / Auto-RPM on | Tanker | B | 52 | -4.9 | 5.6 | 0.908 |
| Holtrop / Legacy / Auto-RPM on | Tanker | T | 15 | -4.8 | 9.8 | 0.780 |
| Holtrop / Legacy / Auto-RPM on | Tanker | P installed vs MCR | 2 | +8.9 | 10.3 | 0.931 |
| Holtrop / Legacy / Auto-RPM on | Tanker | P service vs 0.85 MCR | 2 | -1.5 | 9.3 | 0.899 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | Lbp | 14 | -1.0 | 4.1 | 0.944 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | B | 14 | -4.5 | 8.5 | 0.835 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | T | 8 | +8.2 | 9.0 | 0.846 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | P installed vs MCR | 11 | +39.5 | 39.5 | -0.681 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 11 | +26.3 | 26.3 | 0.260 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.2 | 16.2 | -40.239 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | B | 3 | -6.1 | 6.1 | -0.395 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -82.281 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | Lbp | 17 | +0.3 | 2.6 | 0.973 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | B | 17 | -6.6 | 7.0 | 0.676 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | T | 10 | +11.2 | 11.2 | -1.379 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +41.4 | 41.4 | nan |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +28.0 | 28.0 | nan |
| Holtrop / Japan clean / Auto-RPM off | Tanker | Lbp | 9 | -1.3 | 3.5 | 0.846 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | B | 9 | -5.3 | 5.5 | 0.722 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | T | 2 | +22.9 | 22.9 | -13.310 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | P installed vs MCR | 1 | +0.7 | 0.7 | nan |
| Holtrop / Japan clean / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -8.9 | 8.9 | nan |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | Lbp | 161 | +1.6 | 2.8 | 0.963 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | B | 170 | +2.0 | 7.2 | 0.803 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | T | 102 | +3.9 | 5.7 | 0.899 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | P installed vs MCR | 18 | +39.5 | 39.5 | -0.392 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 18 | +26.2 | 26.2 | 0.377 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | Lbp | 5 | +10.7 | 10.7 | 0.871 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | B | 6 | -6.1 | 6.1 | 0.891 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | T | 4 | +0.5 | 5.5 | 0.852 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +27.0 | 27.0 | 0.665 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +14.9 | 14.9 | 0.893 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | Lbp | 25 | -2.8 | 4.8 | 0.917 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | B | 25 | -8.6 | 8.9 | 0.705 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | T | 16 | +12.9 | 12.9 | 0.417 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +41.4 | 41.4 | nan |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +28.0 | 28.0 | nan |
| Holtrop / Japan clean / Auto-RPM on | Tanker | Lbp | 47 | +0.7 | 3.2 | 0.967 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | B | 51 | -2.6 | 3.2 | 0.966 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | T | 14 | +6.1 | 7.9 | 0.662 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | P installed vs MCR | 1 | +0.7 | 0.7 | nan |
| Holtrop / Japan clean / Auto-RPM on | Tanker | P service vs 0.85 MCR | 1 | -8.9 | 8.9 | nan |

## Failure reasons

- Taylor / Legacy / Auto-RPM off: pitch < 0.5 x164; numerical (complex result) x12; pitch > 1.4, speed too low x3; no convergence x2; pitch < 0.5, speed too high x1; pitch > 1.4 x1
- Taylor / Legacy / Auto-RPM on: numerical (complex result) x14; no convergence x3
- Taylor / Japan clean / Auto-RPM off: pitch < 0.5 x203; pitch > 1.4, speed too low x11; numerical (complex result) x2; pitch < 0.5, speed too high x1; pitch > 1.4 x1; no convergence x1
- Taylor / Japan clean / Auto-RPM on: numerical (complex result) x15; no convergence x1
- Holtrop / Legacy / Auto-RPM off: pitch < 0.5 x162; pitch > 1.4, Fn/CB out of method range x29; no convergence x2; deadweight not matched x1; pitch > 1.4 x1; numerical (complex result) x1
- Holtrop / Legacy / Auto-RPM on: numerical (complex result) x25; no convergence x5; deadweight not matched x1
- Holtrop / Japan clean / Auto-RPM off: pitch < 0.5 x208; pitch > 1.4, Fn/CB out of method range x19; no convergence x3; numerical (complex result) x2; deadweight not matched x1; pitch > 1.4 x1
- Holtrop / Japan clean / Auto-RPM on: numerical (complex result) x14; deadweight not matched x1; no convergence x1

## Figures

- `pred_vs_actual_taylor_legacy_autorpm.png`
- `pred_vs_actual_taylor_japanclean_autorpm.png`
- `pred_vs_actual_holtrop_legacy_autorpm.png`
- `pred_vs_actual_holtrop_japanclean_autorpm.png`
- `errors_by_type.png`
- `basis_comparison.png`
