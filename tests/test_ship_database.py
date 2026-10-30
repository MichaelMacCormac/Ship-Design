"""Tests for the V2 ship-database cleaning pipeline (ship_database.py).

Run from the repository root:
    python -m unittest discover tests
"""
import csv
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ship_database as sd  # noqa: E402

V2 = os.path.join(ROOT, "boat_database_V2.csv")
COLUMNS = ["boat_name", "vessel_type", "builder", "owner", "hull_no", "delivery_date", "capacity", "speed",
           "classification", "registry", "dim_length_oa", "dim_breadth", "dim_depth", "dim_draft",
           "ton_gross_tonnage", "ton_deadweight", "engine_engine_model", "engine_power_output", "source_file"]


def row(**cells):
    r = {c: "" for c in COLUMNS}
    r.update(cells)
    return r


def clean(**cells):
    return sd.clean_row(row(**cells), COLUMNS)


class TestParsing(unittest.TestCase):
    def test_power_formats(self):
        self.assertEqual(sd.parse_power("11,920kW x 105min⁻¹")[:3], (11920.0, 1, 105.0))
        self.assertEqual(sd.parse_power("2 x 12,600kW")[:2], (25200.0, 2))
        self.assertEqual(sd.parse_power("3,310kW x 2")[:2], (6620.0, 2))
        self.assertAlmostEqual(sd.parse_power("13,500PS")[0], 13500 * 0.7355)
        self.assertEqual(sd.parse_power("12.9MW")[0], 12900.0)
        self.assertEqual(sd.parse_power("6,620 kW (9,000 PS) x 130rpm")[0], 6620.0)
        self.assertEqual(sd.parse_power("1,370kW x 4 units")[:2], (5480.0, 4))
        self.assertEqual(sd.parse_power("8,570kW x 600/134.6min⁻¹ per unit")[2], 134.6)
        self.assertIsNone(sd.parse_power("null"))

    def test_dates(self):
        for s, y in (("April 7, 2022", 2022), ("Sept. 30, 2010", 2010), ("Mar-22", 2022),
                     ("28/06/2004", 2004), ("2005", 2005), ("null", None), ("14.5kt", None)):
            self.assertEqual(sd.parse_date_year(s), y, s)

    def test_cell_kinds(self):
        self.assertEqual(sd.classify_cell("229.0m")[0][:2], ("length", 229.0))
        self.assertEqual(sd.classify_cell("approx. 346m")[0][2], "approx")
        self.assertEqual(sd.classify_cell("32,20m")[0][1], 32.2)        # decimal comma
        self.assertEqual(sd.classify_cell("12.65m at full load")[0][2], "design")
        self.assertEqual(sd.classify_cell("82,384t")[0][:2], ("tonnage", 82384.0))
        self.assertEqual(sd.classify_cell("81,500 DWT")[0][2], "dwt")
        self.assertEqual(sd.classify_cell("34,400 (International)")[0], ("tonnage", 34400.0, "gt"))
        self.assertEqual(sd.classify_cell("about 14.5kt")[0][:2], ("speed", 14.5))
        self.assertEqual(sd.classify_cell("Sea362.pdf")[0][0], "source")
        self.assertEqual(sd.classify_cell("Lane Meter:2,000 M For Trailers")[0][0], "text")
        self.assertEqual(sd.classify_cell("73,614m³")[0][0], "text")
        self.assertEqual(sd.classify_cell("N/A"), [])


class TestRealignment(unittest.TestCase):
    def test_aligned_row_unchanged_and_unaudited(self):
        c = clean(boat_name="RUBINA", vessel_type="Bulk carrier", delivery_date="April 7, 2022", speed="14.5kt",
                  dim_length_oa="229.0m", dim_breadth="32.26m", dim_depth="20.20m", dim_draft="14.55m",
                  ton_gross_tonnage="44,618", ton_deadweight="82,384t", source_file="SEA-Japan-No-413.pdf")
        v = c.v
        self.assertEqual((v["LOA_m"], v["B_m"], v["D_m"], v["T_m"]), (229.0, 32.26, 20.2, 14.55))
        self.assertEqual((v["GT"], v["DWT"], v["speed_kn"], v["delivery_year"]), (44618.0, 82384.0, 14.5, 2022))
        self.assertEqual(c.audit, [])
        self.assertNotIn("realigned_row", c.flags)

    def test_shifted_row_rebuilt_by_unit(self):
        # MAERSK FUKUOKA pattern: tonnages early, dimensions at the end.
        c = clean(boat_name="MAERSK FUKUOKA", vessel_type="Container carrier", delivery_date="21.50kt",
                  speed="63,709t", classification="6G80ME-C10.6", dim_depth="76,480t",
                  ton_gross_tonnage="American Bureau of Shipping", ton_deadweight="254.94m",
                  engine_engine_model="40.00m", engine_power_output="21.70m")
        v = c.v
        self.assertEqual((v["LOA_m"], v["B_m"], v["D_m"]), (254.94, 40.0, 21.7))
        self.assertNotIn("T_m", v)
        self.assertEqual((v["GT"], v["DWT"], v["speed_kn"]), (63709.0, 76480.0, 21.5))
        self.assertIn("realigned_row", c.flags)
        self.assertTrue(any(a[1] == "LOA_m" and a[3] == "ton_deadweight" for a in c.audit))

    def test_constant_offset_block(self):
        # Whole L..DWT block slid two columns left; draught explicitly missing.
        c = clean(boat_name="X", vessel_type="Bulk carrier", classification="174.00m", registry="30.00m",
                  dim_length_oa="15.10m", dim_breadth="null", dim_depth="24,000", dim_draft="37,000t",
                  ton_gross_tonnage="MAN B&W 6S46ME-B8", engine_engine_model="SEA-Japan-No.-419.pdf")
        v = c.v
        self.assertEqual((v["LOA_m"], v["B_m"], v["D_m"]), (174.0, 30.0, 15.1))
        self.assertEqual((v["GT"], v["DWT"]), (24000.0, 37000.0))
        self.assertEqual(v["source_file"], "SEA-Japan-No.-419.pdf")
        self.assertTrue(any("offset-2" in a[5] for a in c.audit))

    def test_third_dimension_by_ratio_and_ambiguous(self):
        # Capesize 291.92 x 45 with one more length 18.2: L/x = 16 -> draught.
        c = clean(boat_name="OCEAN ASIA", vessel_type="Bulk carrier", classification="291.92m",
                  registry="45.0m", dim_length_oa="18.2m", dim_breadth="Not specified", dim_depth="93,721",
                  dim_draft="182,090t", ton_gross_tonnage="MAN B&W 6G70ME")
        self.assertEqual(c.v.get("T_m"), 18.2)
        self.assertNotIn("D_m", c.v)
        self.assertIn("third_dimension_by_ratio", c.flags)
        # L/x = 13.8 sits in the no-call band: blank and flagged.
        c = clean(boat_name="Y", vessel_type="Container ship", speed="336.0m", classification="45.8m",
                  registry="24.4m", dim_length_oa="98,747", dim_breadth="99,214t", dim_depth="x.pdf")
        self.assertNotIn("D_m", c.v)
        self.assertNotIn("T_m", c.v)
        self.assertIn("ambiguous_third_dimension", c.flags)

    def test_missing_loa_detected(self):
        c = clean(boat_name="NEWBURY", vessel_type="Tanker", speed="Bahamas", classification="Not specified",
                  registry="44.00m", dim_length_oa="21.80m", dim_breadth="Not specified",
                  dim_depth="abt. 60,100", dim_draft="abt. 112,100t", ton_gross_tonnage="Hitachi MAN B&W")
        self.assertNotIn("LOA_m", c.v)
        self.assertEqual(c.v["B_m"], 44.0)
        self.assertIn("loa_missing", c.flags)

    def test_bare_hull_number_not_taken_as_dwt(self):
        c = clean(boat_name="BALOS", vessel_type="Bulk carrier", delivery_date="May 22, 2018",
                  capacity="96,597m³ (grain)", speed="about 14.5kt", dim_length_oa="229.00m",
                  dim_breadth="32.24m", dim_depth="20.20m", dim_draft="43,380", ton_gross_tonnage="MAN B&W 6S60MC",
                  ton_deadweight="Sea390.pdf", engine_engine_model="1356", engine_power_output="14.668m",
                  source_file="82,025t")
        self.assertEqual((c.v["GT"], c.v["DWT"], c.v["T_m"]), (43380.0, 82025.0, 14.668))

    def test_single_tonnage_by_ratio(self):
        c = clean(boat_name="EISHO", vessel_type="Bulk carrier", hull_no="December 11, 2012", delivery_date="14.5kt",
                  capacity="225.00m", speed="32.26m", classification="19.80m", registry="74,930t",
                  dim_length_oa="B&W 7S50MC-C8", dim_breadth="Sea358.pdf")
        self.assertEqual(c.v.get("DWT"), 74930.0)
        self.assertIn("tonnage_by_ratio", c.flags)


class TestTypesAndFlags(unittest.TestCase):
    def test_type_map(self):
        cases = {"Panamax bulk carrier": ("Bulk carrier", "Bulk carrier"), "VLCC": ("Tanker", "Tanker"),
                 "Membrane type LNG carrier": ("LNG carrier", ""), "LPG/NH3 carrier": ("Gas carrier", ""),
                 "Pure car and truck carrier (PCTC)": ("Car carrier / Ro-Ro", ""),
                 "Mega container ship": ("Container ship", "Container Ship"),
                 "Open hatch cargo ship": ("General cargo", "Cargo vessel"),
                 "Passenger/car ferry": ("Ferry / RoPax", ""), "Cruise ship": ("Passenger / cruise", "Cruise Ship"),
                 "Chemical/product oil carrier": ("Tanker", "Tanker"), "Harbour tug": ("Other", ""),
                 "null": ("Unknown", "")}
        for raw, expect in cases.items():
            self.assertEqual(sd.classify_type(raw), expect, raw)

    def test_plausibility_flags_do_not_edit(self):
        c = clean(boat_name="BM BONANZA", vessel_type="Tanker", speed="about 14kt", dim_length_oa="237.71m",
                  dim_breadth="42.00m", dim_depth="12.19m", dim_draft="14.85m", ton_gross_tonnage="56,172t",
                  ton_deadweight="105,400t")
        self.assertIn("T>=D", c.flags)
        self.assertEqual((c.v["D_m"], c.v["T_m"]), (12.19, 14.85))   # flagged, not changed

    def test_rejections(self):
        self.assertEqual(sd.reject_reason(clean(boat_name="Kawasaki LH2 Carrier Design", dim_length_oa="346m")),
                         "design_or_concept_not_a_built_ship")
        self.assertEqual(sd.reject_reason(clean(boat_name="MILES")), "no_length_and_no_deadweight")


class TestPipeline(unittest.TestCase):
    def _run(self, rows, **kw):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "in.csv")
        with open(src, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        kept, rejected, cut, _ = sd.run(src, os.path.join(d, "out"), **kw)
        return d, kept, rejected, cut

    def test_dedupe_keeps_row_with_source(self):
        a = row(boat_name="DUP", vessel_type="Tanker", builder="Imabari Shipbuilding", dim_length_oa="200m",
                dim_breadth="32m", ton_deadweight="50,000t")
        b = dict(a, source_file="Sea300.pdf")
        _, kept, rejected, _ = self._run([a, b])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].v["source_file"], "Sea300.pdf")
        self.assertTrue(rejected[0][1].startswith("duplicate_of:"))

    def test_split_and_overrides(self):
        rows = [row(boat_name=f"S{i}", vessel_type="Bulk carrier", delivery_date=f"May 1, {2000 + i}",
                    dim_length_oa="200m", dim_breadth="32m", ton_deadweight="50,000t") for i in range(10)]
        d, kept, _, cut = self._run(rows)
        self.assertEqual(cut, 2007)                       # newest 3 of 10 -> validate
        self.assertEqual(sum(r.v["split"] == "validate" for r in kept), 3)
        _, kept2, _, cut2 = self._run(rows, cutoff=2005)
        self.assertEqual(sum(r.v["split"] == "validate" for r in kept2), 5)
        # overrides: fix a draught, reject a ship
        sid = kept[0].id
        ov = os.path.join(d, "ov.csv")
        with open(ov, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ship_id", "field", "value", "note"])
            w.writerow([sid, "T_m", "12.5", "PDF p.3"])
            w.writerow([kept[1].id, "reject", "not a ship", ""])
        src = os.path.join(d, "in.csv")
        kept3, rejected3, _, _ = sd.run(src, os.path.join(d, "out2"), overrides=ov)
        fixed = next(r for r in kept3 if r.id == sid)
        self.assertEqual(fixed.v["T_m"], 12.5)
        self.assertTrue(any(a[1] == "T_m" and a[5].startswith("manual override") for a in fixed.audit))
        self.assertTrue(any(why.startswith("manual") for _, why in rejected3))

    def test_reject_column_commas_and_problems(self):
        rows = [row(boat_name=f"S{i}", vessel_type="Tanker", delivery_date=f"May 1, {2010 + i}",
                    dim_length_oa="200m", dim_breadth="32m", ton_deadweight="50,000t") for i in range(4)]
        d, kept, _, _ = self._run(rows)
        ids = [r.id for r in kept]
        ov = os.path.join(d, "ov.csv")
        with open(ov, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ship_id", "field", "value", "note", "reject"])
            w.writerow([ids[0], "DWT", "37,160", "", ""])            # thousands separator
            w.writerow([ids[1], "", "", "Not relevant", "reject"])    # reject column
            w.writerow([ids[2], "GT", "", "", ""])                    # blank value clears
            w.writerow([ids[3], "DWT", "abc", "", ""])                # bad number: reported
            w.writerow(["ffffffffff", "DWT", "1", "", ""])            # unknown ship: reported
        kept2, rejected2, _, summary = sd.run(os.path.join(d, "in.csv"), os.path.join(d, "out"), overrides=ov)
        by = {r.id: r for r in kept2}
        self.assertEqual(by[ids[0]].v["DWT"], 37160.0)
        self.assertNotIn(ids[1], by)
        self.assertIn((ids[1], "manual: Not relevant"), [(r.id, why) for r, why in rejected2])
        self.assertIsNone(by[ids[2]].v.get("GT"))
        self.assertEqual(by[ids[3]].v["DWT"], 50000.0)             # unchanged
        self.assertIn("Override rows NOT applied (2)", summary)

    def test_review_marks_survive_rerun(self):
        rows = [row(boat_name=f"S{i}", vessel_type="Tanker", dim_length_oa="200m", dim_breadth="32m",
                    ton_deadweight="50,000t") for i in range(3)]
        d, kept, _, _ = self._run(rows)
        out = os.path.join(d, "out")
        path = os.path.join(out, "review_sample.csv")
        with open(path, encoding="utf-8") as f:
            sample = list(csv.DictReader(f))
        sample[0]["verified"] = "Yes"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sample[0].keys()))
            w.writeheader()
            w.writerows(sample)
        sd.run(os.path.join(d, "in.csv"), out)
        with open(path, encoding="utf-8") as f:
            again = {r["ship_id"]: r for r in csv.DictReader(f)}
        self.assertEqual(again[sample[0]["ship_id"]]["verified"], "Yes")

    def test_bare_year_in_delivery_column(self):
        c = clean(boat_name="KOHYOHSAN", vessel_type="Capesize bulk carrier", delivery_date="2001",
                  ton_deadweight="172,000DWT", source_file="Sea318.pdf")
        self.assertEqual(c.v.get("delivery_year"), 2001)
        self.assertIsNone(c.v.get("GT"))
        self.assertEqual(c.v.get("DWT"), 172000.0)
        self.assertNotIn("realigned_row", c.flags)


@unittest.skipUnless(os.path.exists(V2), "raw V2 database not present")
class TestRealDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.kept, cls.rejected, cls.cut, _ = sd.run(V2, cls.out)
        with open(V2, encoding="utf-8-sig") as f:
            cls.n_raw = sum(1 for _ in csv.DictReader(f))
        cls.by_name = {r.v["boat_name"].upper(): r for r in cls.kept}

    def test_row_counts_add_up(self):
        self.assertEqual(len(self.kept) + len(self.rejected), self.n_raw)

    def test_no_unit_text_in_numeric_columns(self):
        with open(os.path.join(self.out, "ships_clean.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for c in sd.NUMERIC:
                    if r[c]:
                        float(r[c])                       # raises if not a plain number

    def test_known_v10_errors_come_out_right(self):
        oga = self.by_name["SUPER LINER OGASAWARA"].v
        self.assertEqual(oga.get("GT"), 14500.0)          # V10 had GT = 2005 (the year)
        suz = self.by_name["SUZURAN"].v
        self.assertNotEqual(suz.get("DWT"), 34400.0)      # V10 put the international GT in DWT
        self.assertEqual(suz.get("LOA_m"), 224.5)
        self.assertEqual(suz.get("GT"), 34400.0)
        mol = self.by_name["MOL PARAMOUNT"].v
        self.assertEqual((mol["D_m"], mol["T_m"]), (24.3, 14.0))   # V10 had D 26 / T 24.3
        cos = self.by_name["COSCO DALIAN"].v
        self.assertEqual((cos["D_m"], cos["T_m"]), (24.0, 14.0))
        self.assertEqual(self.by_name["HUMEN BRIDGE"].v["GT"], 98747.0)   # V10 had 3,207

    def test_every_value_traceable(self):
        """A clean numeric value either parses from the raw cell of its own
        column or has an audit entry naming where it came from."""
        own = {"LOA_m": "dim_length_oa", "B_m": "dim_breadth", "D_m": "dim_depth", "T_m": "dim_draft",
               "GT": "ton_gross_tonnage", "DWT": "ton_deadweight", "speed_kn": "speed"}
        for r in self.kept:
            audited = {a[1] for a in r.audit}
            for field, col in own.items():
                v = r.v.get(field)
                if v is None or field in audited:
                    continue
                cells = sd.classify_cell(r.raw.get(col))
                self.assertTrue(cells and math.isclose(cells[0][1], v), (r.v["boat_name"], field, v))

    def test_split_cutoff_and_share(self):
        tool = [r for r in self.kept if r.v.get("tool_type") and r.v.get("delivery_year")]
        share = sum(r.v["split"] == "validate" for r in tool) / len(tool)
        self.assertTrue(0.2 <= share <= 0.4, share)
        self.assertTrue(all(r.v["split"] == "fit" for r in self.kept if r.v.get("delivery_year") is None))

    def test_output_files_written(self):
        for name in ("ships_clean.csv", "ships_audit.csv", "ships_rejected.csv", "review_sample.csv",
                     "overrides.csv", "cleaning_summary.txt"):
            self.assertTrue(os.path.exists(os.path.join(self.out, name)), name)


if __name__ == "__main__":
    unittest.main()
