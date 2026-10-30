# Validation against the clean ship database

Data: `data\ships_clean.csv`, split **validate** - 276 ship(s) of the tool's types with DWT and speed.

## Assumptions

- Each real ship is redesigned at its own type, speed and total deadweight (secant on the cargo target until total DW matches within 0.1 %).
- Lbp = LOA x Tanker 0.97, Bulk carrier 0.97, Container Ship 0.95, Cargo vessel 0.95, Cruise Ship 0.9, Superyacht 0.88; length errors also shown at +/-1 % on the ratio.
- Direct-drive diesel; RPM = database rpm where known, else 120 rpm; range = solver default; economics off.
- Database power = MCR: compared with installed P2 (includes the solver's 30 % margin); service P1 compared with 0.85 x MCR.
- Fields flagged implausible by the cleaning pipeline, and scantling draughts, are excluded from that field's comparison only.

## Solve rate

| Configuration | Attempted | Solved | RPM adjusted |
|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | 276 | 95 | 0 |
| Taylor / Legacy / Auto-RPM on | 276 | 259 | 175 |
| Taylor / Japan clean / Auto-RPM off | 276 | 59 | 0 |
| Taylor / Japan clean / Auto-RPM on | 276 | 261 | 217 |
| Holtrop / Legacy / Auto-RPM off | 276 | 82 | 0 |
| Holtrop / Legacy / Auto-RPM on | 276 | 246 | 170 |
| Holtrop / Japan clean / Auto-RPM off | 276 | 44 | 0 |
| Holtrop / Japan clean / Auto-RPM on | 276 | 261 | 220 |

## Accuracy (all types)

| Configuration | Quantity | n | Bias % | MAPE % | R² |
|---|---|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | Lbp | 84 | +6.9 | 8.9 | 0.884 |
| Taylor / Legacy / Auto-RPM off | Lbp (ratio +1%) | 84 | +5.9 | 8.1 | 0.893 |
| Taylor / Legacy / Auto-RPM off | Lbp (ratio -1%) | 84 | +8.0 | 9.6 | 0.872 |
| Taylor / Legacy / Auto-RPM off | B | 92 | -5.4 | 6.2 | 0.891 |
| Taylor / Legacy / Auto-RPM off | D | 92 | -8.6 | 11.5 | 0.598 |
| Taylor / Legacy / Auto-RPM off | T | 54 | +2.0 | 6.4 | 0.841 |
| Taylor / Legacy / Auto-RPM off | P installed vs MCR | 15 | +50.3 | 50.3 | -1.138 |
| Taylor / Legacy / Auto-RPM off | P service vs 0.85 MCR | 15 | +36.0 | 36.8 | -0.112 |
| Taylor / Legacy / Auto-RPM on | Lbp | 226 | +7.1 | 7.8 | 0.854 |
| Taylor / Legacy / Auto-RPM on | Lbp (ratio +1%) | 226 | +6.1 | 6.9 | 0.878 |
| Taylor / Legacy / Auto-RPM on | Lbp (ratio -1%) | 226 | +8.2 | 8.8 | 0.825 |
| Taylor / Legacy / Auto-RPM on | B | 249 | -1.9 | 6.1 | 0.876 |
| Taylor / Legacy / Auto-RPM on | D | 248 | -4.6 | 7.4 | 0.710 |
| Taylor / Legacy / Auto-RPM on | T | 136 | +1.5 | 4.9 | 0.928 |
| Taylor / Legacy / Auto-RPM on | P installed vs MCR | 23 | +50.5 | 50.5 | -1.172 |
| Taylor / Legacy / Auto-RPM on | P service vs 0.85 MCR | 23 | +36.2 | 36.7 | -0.168 |
| Taylor / Japan clean / Auto-RPM off | Lbp | 54 | -0.7 | 4.2 | 0.947 |
| Taylor / Japan clean / Auto-RPM off | Lbp (ratio +1%) | 54 | -1.6 | 4.2 | 0.941 |
| Taylor / Japan clean / Auto-RPM off | Lbp (ratio -1%) | 54 | +0.3 | 4.2 | 0.952 |
| Taylor / Japan clean / Auto-RPM off | B | 57 | -6.1 | 7.4 | 0.865 |
| Taylor / Japan clean / Auto-RPM off | D | 57 | -2.7 | 8.3 | 0.798 |
| Taylor / Japan clean / Auto-RPM off | T | 32 | +10.8 | 11.6 | 0.669 |
| Taylor / Japan clean / Auto-RPM off | P installed vs MCR | 15 | +56.7 | 56.7 | -1.585 |
| Taylor / Japan clean / Auto-RPM off | P service vs 0.85 MCR | 15 | +41.8 | 42.1 | -0.416 |
| Taylor / Japan clean / Auto-RPM on | Lbp | 228 | +1.3 | 3.2 | 0.956 |
| Taylor / Japan clean / Auto-RPM on | Lbp (ratio +1%) | 228 | +0.3 | 2.9 | 0.958 |
| Taylor / Japan clean / Auto-RPM on | Lbp (ratio -1%) | 228 | +2.3 | 3.7 | 0.950 |
| Taylor / Japan clean / Auto-RPM on | B | 251 | -0.1 | 6.5 | 0.852 |
| Taylor / Japan clean / Auto-RPM on | D | 250 | -0.6 | 5.0 | 0.854 |
| Taylor / Japan clean / Auto-RPM on | T | 135 | +5.1 | 6.7 | 0.852 |
| Taylor / Japan clean / Auto-RPM on | P installed vs MCR | 23 | +57.6 | 57.6 | -1.790 |
| Taylor / Japan clean / Auto-RPM on | P service vs 0.85 MCR | 23 | +42.6 | 42.8 | -0.557 |
| Holtrop / Legacy / Auto-RPM off | Lbp | 73 | +7.1 | 9.3 | 0.886 |
| Holtrop / Legacy / Auto-RPM off | Lbp (ratio +1%) | 73 | +6.0 | 8.6 | 0.893 |
| Holtrop / Legacy / Auto-RPM off | Lbp (ratio -1%) | 73 | +8.1 | 10.1 | 0.875 |
| Holtrop / Legacy / Auto-RPM off | B | 79 | -5.0 | 5.9 | 0.905 |
| Holtrop / Legacy / Auto-RPM off | D | 79 | -10.7 | 12.3 | 0.580 |
| Holtrop / Legacy / Auto-RPM off | T | 46 | +1.5 | 6.1 | 0.835 |
| Holtrop / Legacy / Auto-RPM off | P installed vs MCR | 14 | +36.5 | 36.7 | -0.672 |
| Holtrop / Legacy / Auto-RPM off | P service vs 0.85 MCR | 14 | +23.5 | 25.1 | 0.254 |
| Holtrop / Legacy / Auto-RPM on | Lbp | 213 | +7.1 | 7.9 | 0.838 |
| Holtrop / Legacy / Auto-RPM on | Lbp (ratio +1%) | 213 | +6.0 | 7.0 | 0.863 |
| Holtrop / Legacy / Auto-RPM on | Lbp (ratio -1%) | 213 | +8.1 | 8.8 | 0.807 |
| Holtrop / Legacy / Auto-RPM on | B | 236 | -1.9 | 6.2 | 0.850 |
| Holtrop / Legacy / Auto-RPM on | D | 235 | -5.0 | 7.5 | 0.671 |
| Holtrop / Legacy / Auto-RPM on | T | 125 | +1.4 | 5.1 | 0.901 |
| Holtrop / Legacy / Auto-RPM on | P installed vs MCR | 23 | +35.0 | 35.1 | -0.011 |
| Holtrop / Legacy / Auto-RPM on | P service vs 0.85 MCR | 23 | +22.1 | 23.1 | 0.559 |
| Holtrop / Japan clean / Auto-RPM off | Lbp | 41 | +0.7 | 3.7 | 0.973 |
| Holtrop / Japan clean / Auto-RPM off | Lbp (ratio +1%) | 41 | -0.3 | 3.6 | 0.973 |
| Holtrop / Japan clean / Auto-RPM off | Lbp (ratio -1%) | 41 | +1.7 | 3.9 | 0.971 |
| Holtrop / Japan clean / Auto-RPM off | B | 43 | -5.7 | 7.1 | 0.868 |
| Holtrop / Japan clean / Auto-RPM off | D | 44 | -2.7 | 7.8 | 0.734 |
| Holtrop / Japan clean / Auto-RPM off | T | 22 | +9.7 | 10.9 | 0.711 |
| Holtrop / Japan clean / Auto-RPM off | P installed vs MCR | 14 | +37.0 | 37.0 | -0.382 |
| Holtrop / Japan clean / Auto-RPM off | P service vs 0.85 MCR | 14 | +24.0 | 25.3 | 0.384 |
| Holtrop / Japan clean / Auto-RPM on | Lbp | 228 | +1.2 | 3.2 | 0.956 |
| Holtrop / Japan clean / Auto-RPM on | Lbp (ratio +1%) | 228 | +0.2 | 2.9 | 0.958 |
| Holtrop / Japan clean / Auto-RPM on | Lbp (ratio -1%) | 228 | +2.2 | 3.7 | 0.950 |
| Holtrop / Japan clean / Auto-RPM on | B | 251 | -0.1 | 6.5 | 0.852 |
| Holtrop / Japan clean / Auto-RPM on | D | 250 | -0.6 | 5.0 | 0.853 |
| Holtrop / Japan clean / Auto-RPM on | T | 135 | +5.1 | 6.7 | 0.853 |
| Holtrop / Japan clean / Auto-RPM on | P installed vs MCR | 23 | +37.1 | 37.1 | -0.136 |
| Holtrop / Japan clean / Auto-RPM on | P service vs 0.85 MCR | 23 | +24.0 | 24.8 | 0.494 |

## Accuracy by ship type

| Configuration | Type | Quantity | n | Bias % | MAPE % | R² |
|---|---|---|---|---|---|---|
| Taylor / Legacy / Auto-RPM off | Bulk carrier | Lbp | 36 | +4.3 | 4.9 | 0.873 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | B | 40 | -6.5 | 8.1 | 0.677 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | T | 26 | +5.5 | 6.0 | 0.829 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | P installed vs MCR | 12 | +55.3 | 55.3 | -1.772 |
| Taylor / Legacy / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 12 | +40.5 | 40.5 | -0.470 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.3 | 16.3 | -40.639 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | B | 3 | -6.0 | 6.0 | -0.379 |
| Taylor / Legacy / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -80.819 |
| Taylor / Legacy / Auto-RPM off | Container Ship | Lbp | 24 | +3.0 | 8.8 | 0.900 |
| Taylor / Legacy / Auto-RPM off | Container Ship | B | 25 | -6.4 | 6.4 | 0.875 |
| Taylor / Legacy / Auto-RPM off | Container Ship | T | 16 | +3.5 | 3.5 | 0.921 |
| Taylor / Legacy / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +43.7 | 43.7 | nan |
| Taylor / Legacy / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +30.1 | 30.1 | nan |
| Taylor / Legacy / Auto-RPM off | Tanker | Lbp | 22 | +14.7 | 14.8 | -0.241 |
| Taylor / Legacy / Auto-RPM off | Tanker | B | 24 | -2.5 | 3.0 | 0.921 |
| Taylor / Legacy / Auto-RPM off | Tanker | T | 10 | -8.4 | 12.2 | 0.544 |
| Taylor / Legacy / Auto-RPM off | Tanker | P installed vs MCR | 1 | +4.0 | 4.0 | nan |
| Taylor / Legacy / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -5.9 | 5.9 | nan |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | Lbp | 153 | +5.9 | 6.0 | 0.862 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | B | 165 | -0.2 | 6.3 | 0.809 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | T | 100 | +2.3 | 4.5 | 0.927 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | P installed vs MCR | 17 | +57.0 | 57.0 | -3.206 |
| Taylor / Legacy / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 17 | +42.1 | 42.1 | -1.301 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | Lbp | 4 | +11.4 | 11.4 | 0.842 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | B | 5 | -4.9 | 4.9 | 0.927 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | T | 3 | -2.9 | 3.7 | 0.694 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +40.5 | 40.5 | -0.150 |
| Taylor / Legacy / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +27.1 | 27.1 | 0.398 |
| Taylor / Legacy / Auto-RPM on | Container Ship | Lbp | 24 | +3.0 | 8.8 | 0.900 |
| Taylor / Legacy / Auto-RPM on | Container Ship | B | 25 | -6.4 | 6.4 | 0.875 |
| Taylor / Legacy / Auto-RPM on | Container Ship | T | 16 | +3.5 | 3.5 | 0.921 |
| Taylor / Legacy / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +43.7 | 43.7 | nan |
| Taylor / Legacy / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +30.1 | 30.1 | nan |
| Taylor / Legacy / Auto-RPM on | Tanker | Lbp | 45 | +13.1 | 13.3 | 0.719 |
| Taylor / Legacy / Auto-RPM on | Tanker | B | 54 | -5.0 | 5.7 | 0.916 |
| Taylor / Legacy / Auto-RPM on | Tanker | T | 17 | -4.4 | 8.8 | 0.909 |
| Taylor / Legacy / Auto-RPM on | Tanker | P installed vs MCR | 2 | +11.3 | 11.3 | 0.923 |
| Taylor / Legacy / Auto-RPM on | Tanker | P service vs 0.85 MCR | 2 | +0.8 | 6.7 | 0.963 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | Lbp | 20 | +0.1 | 2.7 | 0.976 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | B | 22 | -4.9 | 7.5 | 0.830 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | T | 14 | +9.7 | 10.1 | 0.765 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | P installed vs MCR | 12 | +63.6 | 63.6 | -2.587 |
| Taylor / Japan clean / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 12 | +48.1 | 48.1 | -1.018 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.3 | 16.3 | -40.639 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | B | 3 | -6.0 | 6.0 | -0.379 |
| Taylor / Japan clean / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -80.819 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | Lbp | 22 | -2.6 | 4.8 | 0.910 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | B | 22 | -8.2 | 8.5 | 0.716 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | T | 14 | +12.5 | 12.5 | 0.416 |
| Taylor / Japan clean / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +39.6 | 39.6 | nan |
| Taylor / Japan clean / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +26.3 | 26.3 | nan |
| Taylor / Japan clean / Auto-RPM off | Tanker | Lbp | 10 | -1.2 | 3.3 | 0.882 |
| Taylor / Japan clean / Auto-RPM off | Tanker | B | 10 | -4.3 | 5.6 | 0.717 |
| Taylor / Japan clean / Auto-RPM off | Tanker | T | 2 | +22.9 | 22.9 | -13.301 |
| Taylor / Japan clean / Auto-RPM off | Tanker | P installed vs MCR | 1 | +8.3 | 8.3 | nan |
| Taylor / Japan clean / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -2.0 | 2.0 | nan |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | Lbp | 158 | +1.8 | 2.7 | 0.964 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | B | 170 | +2.1 | 7.2 | 0.802 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | T | 102 | +4.0 | 5.7 | 0.898 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | P installed vs MCR | 18 | +64.3 | 64.3 | -2.974 |
| Taylor / Japan clean / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 18 | +48.7 | 48.7 | -1.260 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | Lbp | 4 | +11.4 | 11.4 | 0.842 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | B | 5 | -4.9 | 4.9 | 0.927 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | T | 3 | -2.9 | 3.7 | 0.694 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +40.5 | 40.5 | -0.150 |
| Taylor / Japan clean / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +27.1 | 27.1 | 0.398 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | Lbp | 24 | -2.8 | 4.8 | 0.914 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | B | 25 | -8.6 | 8.9 | 0.706 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | T | 16 | +12.9 | 12.9 | 0.409 |
| Taylor / Japan clean / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +39.6 | 39.6 | nan |
| Taylor / Japan clean / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +26.3 | 26.3 | nan |
| Taylor / Japan clean / Auto-RPM on | Tanker | Lbp | 42 | +0.6 | 3.3 | 0.968 |
| Taylor / Japan clean / Auto-RPM on | Tanker | B | 51 | -2.6 | 3.2 | 0.967 |
| Taylor / Japan clean / Auto-RPM on | Tanker | T | 14 | +6.2 | 7.9 | 0.660 |
| Taylor / Japan clean / Auto-RPM on | Tanker | P installed vs MCR | 1 | +8.3 | 8.3 | nan |
| Taylor / Japan clean / Auto-RPM on | Tanker | P service vs 0.85 MCR | 1 | -2.0 | 2.0 | nan |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | Lbp | 26 | +4.0 | 4.9 | 0.852 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | B | 28 | -5.7 | 7.9 | 0.713 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | T | 19 | +4.9 | 5.6 | 0.684 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | P installed vs MCR | 11 | +39.2 | 39.2 | -2.290 |
| Holtrop / Legacy / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 11 | +26.0 | 26.0 | -0.456 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.2 | 16.2 | -40.239 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | B | 3 | -6.1 | 6.1 | -0.395 |
| Holtrop / Legacy / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -82.281 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | Lbp | 24 | +3.0 | 8.8 | 0.898 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | B | 25 | -6.4 | 6.4 | 0.874 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | T | 16 | +3.5 | 3.5 | 0.923 |
| Holtrop / Legacy / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +40.8 | 40.8 | nan |
| Holtrop / Legacy / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +27.4 | 27.4 | nan |
| Holtrop / Legacy / Auto-RPM off | Tanker | Lbp | 21 | +14.7 | 14.8 | -0.211 |
| Holtrop / Legacy / Auto-RPM off | Tanker | B | 23 | -2.5 | 3.0 | 0.920 |
| Holtrop / Legacy / Auto-RPM off | Tanker | T | 9 | -8.0 | 12.2 | 0.584 |
| Holtrop / Legacy / Auto-RPM off | Tanker | P installed vs MCR | 1 | -1.4 | 1.4 | nan |
| Holtrop / Legacy / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -10.8 | 10.8 | nan |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | Lbp | 142 | +5.8 | 5.9 | 0.829 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | B | 154 | -0.1 | 6.5 | 0.712 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | T | 91 | +2.2 | 4.7 | 0.907 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | P installed vs MCR | 17 | +38.3 | 38.3 | -0.775 |
| Holtrop / Legacy / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 17 | +25.2 | 25.2 | 0.225 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | Lbp | 4 | +11.3 | 11.3 | 0.844 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | B | 5 | -5.0 | 5.0 | 0.926 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | T | 3 | -3.0 | 3.7 | 0.689 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +27.0 | 27.0 | 0.665 |
| Holtrop / Legacy / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +14.9 | 14.9 | 0.893 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | Lbp | 24 | +3.0 | 8.8 | 0.898 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | B | 25 | -6.4 | 6.4 | 0.874 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | T | 16 | +3.5 | 3.5 | 0.923 |
| Holtrop / Legacy / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +40.8 | 40.8 | nan |
| Holtrop / Legacy / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +27.4 | 27.4 | nan |
| Holtrop / Legacy / Auto-RPM on | Tanker | Lbp | 43 | +13.1 | 13.4 | 0.649 |
| Holtrop / Legacy / Auto-RPM on | Tanker | B | 52 | -4.9 | 5.6 | 0.908 |
| Holtrop / Legacy / Auto-RPM on | Tanker | T | 15 | -4.8 | 9.8 | 0.780 |
| Holtrop / Legacy / Auto-RPM on | Tanker | P installed vs MCR | 2 | +8.9 | 10.3 | 0.931 |
| Holtrop / Legacy / Auto-RPM on | Tanker | P service vs 0.85 MCR | 2 | -1.5 | 9.3 | 0.899 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | Lbp | 13 | +0.0 | 3.4 | 0.975 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | B | 14 | -4.5 | 8.6 | 0.834 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | T | 8 | +8.2 | 9.0 | 0.846 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | P installed vs MCR | 11 | +39.5 | 39.5 | -0.679 |
| Holtrop / Japan clean / Auto-RPM off | Bulk carrier | P service vs 0.85 MCR | 11 | +26.2 | 26.2 | 0.261 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | Lbp | 2 | +16.2 | 16.2 | -40.239 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | B | 3 | -6.1 | 6.1 | -0.395 |
| Holtrop / Japan clean / Auto-RPM off | Cargo vessel | T | 2 | -5.0 | 5.0 | -82.281 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | Lbp | 17 | +0.3 | 2.6 | 0.973 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | B | 17 | -6.6 | 7.0 | 0.676 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | T | 10 | +11.1 | 11.1 | -1.368 |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | P installed vs MCR | 2 | +41.4 | 41.4 | nan |
| Holtrop / Japan clean / Auto-RPM off | Container Ship | P service vs 0.85 MCR | 2 | +28.0 | 28.0 | nan |
| Holtrop / Japan clean / Auto-RPM off | Tanker | Lbp | 9 | -1.2 | 3.5 | 0.848 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | B | 9 | -5.4 | 5.5 | 0.717 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | T | 2 | +22.8 | 22.8 | -13.229 |
| Holtrop / Japan clean / Auto-RPM off | Tanker | P installed vs MCR | 1 | +0.6 | 0.6 | nan |
| Holtrop / Japan clean / Auto-RPM off | Tanker | P service vs 0.85 MCR | 1 | -9.0 | 9.0 | nan |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | Lbp | 158 | +1.7 | 2.7 | 0.965 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | B | 170 | +2.0 | 7.2 | 0.803 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | T | 102 | +3.9 | 5.7 | 0.899 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | P installed vs MCR | 18 | +39.7 | 39.7 | -0.427 |
| Holtrop / Japan clean / Auto-RPM on | Bulk carrier | P service vs 0.85 MCR | 18 | +26.4 | 26.4 | 0.362 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | Lbp | 4 | +11.3 | 11.3 | 0.844 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | B | 5 | -5.0 | 5.0 | 0.926 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | T | 3 | -3.0 | 3.7 | 0.689 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | P installed vs MCR | 2 | +27.0 | 27.0 | 0.665 |
| Holtrop / Japan clean / Auto-RPM on | Cargo vessel | P service vs 0.85 MCR | 2 | +14.9 | 14.9 | 0.893 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | Lbp | 24 | -2.8 | 4.9 | 0.913 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | B | 25 | -8.6 | 8.9 | 0.704 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | T | 16 | +12.9 | 12.9 | 0.412 |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | P installed vs MCR | 2 | +41.4 | 41.4 | nan |
| Holtrop / Japan clean / Auto-RPM on | Container Ship | P service vs 0.85 MCR | 2 | +28.0 | 28.0 | nan |
| Holtrop / Japan clean / Auto-RPM on | Tanker | Lbp | 42 | +0.6 | 3.3 | 0.968 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | B | 51 | -2.7 | 3.2 | 0.966 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | T | 14 | +6.1 | 7.9 | 0.664 |
| Holtrop / Japan clean / Auto-RPM on | Tanker | P installed vs MCR | 1 | +0.6 | 0.6 | nan |
| Holtrop / Japan clean / Auto-RPM on | Tanker | P service vs 0.85 MCR | 1 | -9.0 | 9.0 | nan |

## Failure reasons

- Taylor / Legacy / Auto-RPM off: pitch < 0.5 x162; numerical (complex result) x12; pitch > 1.4, speed too low x3; no convergence x2; pitch < 0.5, speed too high x1; pitch > 1.4 x1
- Taylor / Legacy / Auto-RPM on: numerical (complex result) x14; no convergence x3
- Taylor / Japan clean / Auto-RPM off: pitch < 0.5 x202; pitch > 1.4, speed too low x8; numerical (complex result) x3; no convergence x2; pitch < 0.5, speed too high x1; pitch > 1.4 x1
- Taylor / Japan clean / Auto-RPM on: numerical (complex result) x13; no convergence x2
- Holtrop / Legacy / Auto-RPM off: pitch < 0.5 x161; pitch > 1.4, Fn/CB out of method range x28; no convergence x2; deadweight not matched x1; pitch > 1.4 x1; numerical (complex result) x1
- Holtrop / Legacy / Auto-RPM on: numerical (complex result) x24; no convergence x5; deadweight not matched x1
- Holtrop / Japan clean / Auto-RPM off: pitch < 0.5 x207; pitch > 1.4, Fn/CB out of method range x16; no convergence x5; numerical (complex result) x2; deadweight not matched x1; pitch > 1.4 x1
- Holtrop / Japan clean / Auto-RPM on: numerical (complex result) x14; deadweight not matched x1

## Figures

- `pred_vs_actual_taylor_legacy_autorpm.png`
- `pred_vs_actual_taylor_japanclean_autorpm.png`
- `pred_vs_actual_holtrop_legacy_autorpm.png`
- `pred_vs_actual_holtrop_japanclean_autorpm.png`
- `errors_by_type.png`
- `basis_comparison.png`
