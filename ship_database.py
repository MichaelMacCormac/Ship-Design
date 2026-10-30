"""Scripted, audited cleaning of the SEA-Japan ship database (V2 -> clean).

The raw file (boat_database_V2.csv) was extracted from PDF tables. In about
a third of the rows the values slid one to three columns along (a draught
in the depth column, a speed in the delivery-date column, a PDF name in a
dimension column), but they kept their source order:

    ... speed, class, registry, L, B, D, T, GT, DWT, engine, power, source

Each cell carries its unit ("229.0m", "82,384t", "14.5kt", "11,920kW"), so a
shifted row can be rebuilt from the units, in order. Rows whose cells
already carry the right units are kept as they are.

Principles:
  * every change to a value is written to the audit file with its rule;
  * implausible values are flagged, never silently edited;
  * a value that cannot be resolved confidently is left blank and flagged;
  * manual corrections live in data/overrides.csv and are applied last;
  * ship_id is a hash of the raw row, so overrides survive rule changes.

Run:  python ship_database.py [--input boat_database_V2.csv] [--out data]
                              [--cutoff YEAR] [--seed 42]
"""
import argparse
import csv
import hashlib
import os
import random
import re
from collections import Counter, OrderedDict

# ----------------------------------------------------------------------
# Token recognition
# ----------------------------------------------------------------------
NUM = r"(\d[\d,]*(?:\.\d+)?)"
NULLS = {"", "null", "none", "n/a", "na", "-", "not stated", "not specified", "unknown", "nan"}

RE_PDF = re.compile(r"\.pdf\b|_comp\b", re.I)
RE_POWER = re.compile(NUM + r"\s*(kW|MW|PS)\b", re.I)
RE_RPM = re.compile(NUM + r"(?:/" + NUM + r")?\s*(?:rpm|min-1|min⁻¹|min−1|min\^-1)", re.I)
RE_ENGINES_PREFIX = re.compile(r"^\s*(\d)\s*[x×]\s*", re.I)
RE_ENGINES_SUFFIX = re.compile(r"[x×]\s*(\d)\s*(?:units?|sets?|engines?)?\s*(?:$|\()", re.I)
RE_SPEED = re.compile(NUM + r"\s*(?:kt|kts|knots?)\b", re.I)
# A length cell is essentially just a measurement: an optional qualifier,
# the number, "m", and an optional trailing note ("(ext.)", "at full load",
# "/ 20.1m"). Text such as "Lane Meter: 2,000 M for trailers" is not one.
RE_LENGTH = re.compile(r"^\s*(?:approx\.?|abt\.?|about|ca\.?|max\.?)?\s*" + NUM
                       + r"\s*m\b(?![³²3])\s*(?:\(.*\)|at .*|/.*|[a-z .]{0,12})?\s*$", re.I)
RE_TONNAGE = re.compile(NUM + r"\s*(DWT|GT|MT|tons?|t)\b(?!\s*/)", re.I)
RE_TEU = re.compile(NUM + r"\s*-?\s*TEU", re.I)
RE_BARE = re.compile(r"^\s*(?:approx\.?|abt\.?|about|ca\.?)?\s*" + NUM + r"\s*$", re.I)
RE_APPROX = re.compile(r"\b(approx|abt|about|ca)\b\.?", re.I)
RE_YEAR = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
RE_MON_YY = re.compile(r"^\s*([A-Za-z]{3,9})\.?-(\d{2})\s*$")
RE_DMY = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
RE_MONTH_WORD = re.compile(r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?\s+\d{1,2},?\s+(\d{4})", re.I)


def is_null(s):
    return s is None or str(s).strip().lower() in NULLS


def to_float(s):
    return float(s.replace(",", ""))


def parse_date_year(s):
    """Delivery year from 'April 7, 2022', 'Sept. 30, 2010', 'Mar-22',
    '28/06/2004', or a bare year; None if the cell is not a date."""
    if is_null(s):
        return None
    s = str(s)
    m = RE_MONTH_WORD.search(s)
    if m:
        return int(m.group(2))
    m = RE_MON_YY.match(s)
    if m and m.group(1)[:3].lower() in MONTHS:
        yy = int(m.group(2))
        return 2000 + yy if yy <= 40 else 1900 + yy
    m = RE_DMY.match(s)
    if m:
        return int(m.group(3))
    if re.fullmatch(r"\s*(19[5-9]\d|20[0-3]\d)\s*", s):
        return int(s)
    return None


def parse_power(s):
    """(total_kW, n_engines, rpm, note) from a power cell, or None.

    '11,920kW x 105min-1' -> (11920, 1, 105); '2 x 12,600kW' -> (25200, 2);
    '3,310kW x 2' -> (6620, 2); '13,500PS' -> kW; '6,620 kW (9,000 PS)'
    -> the kW figure. 'per unit' with an engine count multiplies.
    """
    if is_null(s):
        return None
    s = str(s)
    hits = RE_POWER.findall(s)
    if not hits:
        return None
    kw_hits = [h for h in hits if h[1].lower() == "kw"]
    val, unit = (kw_hits[0] if kw_hits else hits[0])
    kw = to_float(val)
    note = ""
    if unit.lower() == "mw":
        kw *= 1000.0
        note = "MW->kW"
    elif unit.lower() == "ps":
        kw *= 0.7355
        note = "PS->kW"
    n = 1
    m = RE_ENGINES_PREFIX.match(s)
    if m:
        n = int(m.group(1))
    else:
        after = s[s.lower().find(val.lower()) + len(val):]
        m2 = re.match(r"\s*(?:kW|MW|PS)\s*[x×]\s*(\d)\b(?!\s*\d)(?!\.\d)(?!\s*(?:rpm|min))", after, re.I)
        if m2:
            n = int(m2.group(1))
        else:
            m3 = re.search(r"[x×]\s*(\d)\s*(?:units|sets|engines)\b", s, re.I)
            if m3:
                n = int(m3.group(1))
    if n > 1:
        kw *= n
        note = (note + "; " if note else "") + f"x{n} engines"
    rpm = None
    m = RE_RPM.search(s)
    if m:
        rpm = to_float(m.group(2) or m.group(1))   # 'a/b min-1': take the shaft speed b
    return kw, n, rpm, note


def classify_cell(raw):
    """Token kinds found in one raw cell: list of (kind, value, tag)."""
    if is_null(raw):
        return []
    s = str(raw).strip()
    out = []
    if RE_PDF.search(s):
        return [("source", s, "")]
    p = parse_power(s)
    if p:
        out.append(("power", p, ""))
        return out
    m = RE_SPEED.search(s)
    if m and to_float(m.group(1)) <= 60:
        out.append(("speed", to_float(m.group(1)), ""))
        return out
    m = RE_TEU.search(s)
    if m:
        return [("teu", to_float(m.group(1)), "")]
    y = parse_date_year(s)
    if y and not RE_BARE.match(s):
        return [("date", y, "")]
    m = RE_LENGTH.search(s)
    if m:
        tag = []
        if RE_APPROX.search(s):
            tag.append("approx")
        low = s.lower()
        if "b.p" in low or "lbp" in low:
            tag.append("lbp")
        if "ext" in low or "scantling" in low or "summer" in low:
            tag.append("scantling")
        elif "design" in low or "full load" in low:
            tag.append("design")
        txt = m.group(1)
        if re.fullmatch(r"\d{1,3},\d{1,2}", txt):   # '32,20m': decimal comma
            val = float(txt.replace(",", "."))
            tag.append("decimal_comma")
        else:
            val = to_float(txt)
        return [("length", val, ";".join(tag))]
    m = RE_TONNAGE.search(s)
    if m:
        unit = m.group(2).lower()
        tag = "dwt" if unit in ("dwt", "mt") else ("gt" if unit == "gt" else "")
        if "international" in s.lower():
            tag = "gt"
        if RE_APPROX.search(s):
            tag = (tag + ";approx").strip(";")
        return [("tonnage", to_float(m.group(1)), tag)]
    m = re.match(r"^\s*" + NUM + r"\s*\((?:international|intl\.?|ITC)\)", s, re.I)
    if m:                                  # '34,400 (International)': international GT
        return [("tonnage", to_float(m.group(1)), "gt")]
    m = RE_BARE.match(s)
    if m:
        return [("bare", to_float(m.group(1)), "approx" if RE_APPROX.search(s) else "")]
    return [("text", s, "")]


# ----------------------------------------------------------------------
# Row realignment
# ----------------------------------------------------------------------
DIM_COLS = ("dim_length_oa", "dim_breadth", "dim_depth", "dim_draft")
DIM_OUT = ("LOA_m", "B_m", "D_m", "T_m")
SCAN_FROM = "hull_no"   # numeric tokens are gathered from here to the end


def _kinds(raw):
    return {k for k, _, _ in classify_cell(raw)}


def is_aligned(row):
    """True if every key field holds a value of its own kind (or nothing)."""
    ok_dim = {"length", "bare"}
    for c in DIM_COLS:
        k = _kinds(row.get(c))
        if k and not k <= ok_dim:
            return False
        if "bare" in k and classify_cell(row.get(c))[0][1] >= (500 if c == "dim_length_oa" else 60):
            return False
    for c, tagbad in (("ton_gross_tonnage", "dwt"), ("ton_deadweight", "gt")):
        cells = classify_cell(row.get(c))
        if cells and (cells[0][0] not in ("tonnage", "bare") or cells[0][2].startswith(tagbad)):
            return False
    k = _kinds(row.get("speed"))
    if k and not k <= {"speed"} and not (k == {"bare"} and classify_cell(row.get("speed"))[0][1] <= 60):
        return False
    k = _kinds(row.get("engine_power_output"))
    if k and not k <= {"power", "bare", "text"}:
        return False
    k = _kinds(row.get("delivery_date"))
    if k and not k <= {"date", "text"} and parse_date_year(row.get("delivery_date")) is None:
        return False
    return True


class Cleaned:
    """Mutable record for one ship while it moves through the stages."""

    def __init__(self, raw, ship_id):
        self.raw = raw
        self.id = ship_id
        self.v = OrderedDict()
        self.flags = []
        self.audit = []

    def set(self, field, value, raw_value=None, raw_column="", rule=""):
        self.v[field] = value
        if rule:
            self.audit.append((self.id, field, raw_value, raw_column, value, rule))

    def flag(self, f):
        if f not in self.flags:
            self.flags.append(f)


def _num_from(raw, kind_ok):
    cells = classify_cell(raw)
    if cells and cells[0][0] in kind_ok:
        return cells[0][1], cells[0][2]
    return None, ""


def extract_aligned(rec):
    r = rec.raw
    for c, out in zip(DIM_COLS, DIM_OUT):
        val, tag = _num_from(r.get(c), ("length", "bare"))
        if val is not None:
            rec.set(out, val)
            _dim_tags(rec, out, tag)
    gt, gtag = _num_from(r.get("ton_gross_tonnage"), ("tonnage", "bare"))
    dwt, dtag = _num_from(r.get("ton_deadweight"), ("tonnage", "bare"))
    if gt is not None:
        rec.set("GT", gt)
    if dwt is not None:
        rec.set("DWT", dwt)
    if "approx" in gtag or "approx" in dtag:
        rec.flag("approx_tonnage")
    sp, _ = _num_from(r.get("speed"), ("speed", "bare"))
    if sp is not None:
        rec.set("speed_kn", sp)
    _power(rec, r.get("engine_power_output"), "engine_power_output")
    y = parse_date_year(r.get("delivery_date"))
    if y:
        rec.set("delivery_year", y)
    _teu(rec, r)
    rec.set("source_file", (r.get("source_file") or "").strip())


def _dim_tags(rec, out, tag):
    if "approx" in tag:
        rec.flag(f"approx_{out}")
    if out == "LOA_m" and "lbp" in tag:
        rec.flag("length_is_lbp")
    if out == "T_m":
        rec.set("T_kind", "scantling" if "scantling" in tag else ("design" if "design" in tag else "unknown"))


def _power(rec, raw, col):
    p = parse_power(raw)
    if p:
        kw, n, rpm, note = p
        rec.set("power_kW", round(kw, 1), raw, col, f"unit:{note}" if note else "")
        rec.set("n_engines", n)
        if rpm:
            rec.set("rpm", rpm)
        if "per unit" in str(raw).lower() and n == 1:
            rec.flag("power_per_unit_count_unknown")


def _teu(rec, r):
    for c in ("capacity", "hull_no", "delivery_date", "dim_draft", "speed"):
        m = RE_TEU.search(str(r.get(c) or ""))
        if m:
            rec.set("TEU", to_float(m.group(1)), r.get(c), c, "" if c == "capacity" else "realign:teu")
            return


BLOCK = ("dim_length_oa", "dim_breadth", "dim_depth", "dim_draft", "ton_gross_tonnage", "ton_deadweight")
BLOCK_OUT = DIM_OUT + ("GT", "DWT")


def _fits(field, raw):
    """Does this raw cell hold a value of the kind `field` expects (or nothing)?"""
    cells = classify_cell(raw)
    if not cells:
        return True
    kind, val, tag = cells[0]
    if field in DIM_COLS:
        limit = 500 if field == "dim_length_oa" else 60
        return kind == "length" or (kind == "bare" and val < limit)
    if field == "ton_gross_tonnage":
        return kind in ("tonnage", "bare") and not tag.startswith("dwt")
    if field == "ton_deadweight":
        return kind in ("tonnage", "bare") and not tag.startswith("gt")
    return False


def single_tonnage(rec, x):
    """Is a lone, untagged tonnage the DWT or the GT? Only for tankers and
    bulk carriers, from its size relative to the cubic number L*B*D:
    DWT/LBD is about 0.4-0.6, GT/LBD about 0.25-0.32. 'DWT', 'GT' or None."""
    if rec.v.get("ship_class") not in ("Tanker", "Bulk carrier"):
        return None
    L, B, D = rec.v.get("LOA_m"), rec.v.get("B_m"), rec.v.get("D_m")
    if not (L and B and D):
        return None
    r = x / (L * B * D)
    if r >= 0.38:
        return "DWT"
    if r <= 0.33:
        return "GT"
    return None


def third_dimension(L, B, x):
    """Decide whether a lone third dimension x is the depth or the draught
    from proportions, with a wide no-call band. Merchant ships: L/D about
    10-13.5 and L/T about 15-20; D/B about 0.5-0.6 and T/B about 0.3-0.42.
    Returns 'D_m', 'T_m' or None (ambiguous)."""
    if L and x:
        r = L / x
        if r <= 13.5:
            return "D_m"
        if r >= 15.5:
            return "T_m"
        return None
    if B and x:
        r = x / B
        if r >= 0.47:
            return "D_m"
        if r <= 0.42:
            return "T_m"
    return None


def _offset_block(rec, columns, first_length_col):
    """The L..DWT block usually slides as a unit. Read it at the offset
    that puts the first length in dim_length_oa; accept it only if every
    in-range cell has the expected kind. Returns the outputs assigned."""
    k = columns.index(first_length_col) - columns.index("dim_length_oa")
    placed = []
    for field, out in zip(BLOCK, BLOCK_OUT):
        j = columns.index(field) + k
        placed.append((field, out, columns[j] if 0 <= j < len(columns) else None))
    in_range = [(f, o, c) for f, o, c in placed if c is not None]
    dims_ok = all(_fits(f, rec.raw.get(c)) for f, o, c in in_range if f in DIM_COLS)
    if not dims_ok or len([1 for f, o, c in in_range if f in DIM_COLS]) < 2:
        return set()
    vals = {o: (classify_cell(rec.raw.get(c)) or [(None, None, "")])[0][1]
            for f, o, c in in_range if f in DIM_COLS}
    if vals.get("LOA_m") and vals.get("B_m") and vals["LOA_m"] / vals["B_m"] < 2.5:
        return set()                       # first length is really the beam: LOA missing
    if vals.get("D_m") and vals.get("T_m") is None and vals.get("LOA_m"):
        if third_dimension(vals["LOA_m"], None, vals["D_m"]) != "D_m":
            return set()                   # position says depth, proportions disagree
    done = set()
    for f, o, c in in_range:
        raw = rec.raw.get(c)
        if not _fits(f, raw):
            continue                       # tonnage that doesn't fit: left to the token pass
        cells = classify_cell(raw)
        if not cells:
            if f in DIM_COLS:
                done.add(o)                # an empty slot is still a resolved slot
            continue
        kind, val, tag = cells[0]
        rec.set(o, val, raw, c, f"realign:offset{k:+d}")
        if f in DIM_COLS:
            _dim_tags(rec, o, tag)
        elif "approx" in tag:
            rec.flag("approx_tonnage")
        done.add(o)
    return done


def extract_shifted(rec, columns):
    """Rebuild numeric fields of a shifted row: first read the L..DWT block
    at a constant offset; whatever that cannot place is taken from the
    unit-tagged tokens in source order."""
    r = rec.raw
    start = columns.index(SCAN_FROM)
    toks = []
    for c in columns[start:]:
        if c == "delivery_date" and parse_date_year(r.get(c)) is not None:
            # a bare year here is the delivery year, not a tonnage
            toks.append((c, "date", parse_date_year(r.get(c)), "", r.get(c)))
            continue
        for kind, val, tag in classify_cell(r.get(c)):
            toks.append((c, kind, val, tag, r.get(c)))
    rec.flag("realigned_row")

    lengths = [t for t in toks if t[1] == "length"]
    first_len_col = columns.index(lengths[0][0]) if lengths else start
    done = _offset_block(rec, columns, lengths[0][0]) if lengths else set()
    if {"LOA_m", "B_m"} <= done:
        lengths = []                      # dimensions resolved by the offset read
    assign = []
    if lengths:
        vals = [t[2] for t in lengths]
        if len(vals) >= 2 and vals[0] / vals[1] < 2.5 and vals[0] < 100:
            rec.flag("loa_missing")        # first length is the beam
            slots = [("B_m", lengths[0])]
            rest = lengths[1:]
        elif len(vals) == 1:
            slots = [("LOA_m", lengths[0])] if vals[0] >= 40 else []
            rest = []
            if not slots:
                rec.flag("ambiguous_dimension")
        else:
            slots = [("LOA_m", lengths[0]), ("B_m", lengths[1])]
            rest = lengths[2:]
        if len(rest) >= 2:
            slots += [("D_m", rest[0]), ("T_m", rest[1])]
        elif len(rest) == 1:
            L = lengths[0][2] if slots and slots[0][0] == "LOA_m" else None
            B = next((t[2] for o, t in slots if o == "B_m"), None)
            which = third_dimension(L, B, rest[0][2])
            if which:
                slots.append((which, rest[0]))
                rec.flag("third_dimension_by_ratio")
            else:
                rec.flag("ambiguous_third_dimension")
        assign = slots
    for out, (c, _, val, tag, raw) in assign:
        rule = "realign:length_order"
        if out in ("D_m", "T_m") and "third_dimension_by_ratio" in rec.flags:
            rule += "; third_dimension_by_ratio"
        rec.set(out, val, raw, c, rule)
        _dim_tags(rec, out, tag)

    # Tonnages not placed by the offset read. Explicit DWT/GT tags win.
    # Otherwise: two or more values with a tonnage unit are GT then DWT in
    # source order; exactly one is the DWT, and the GT is the first bare
    # number before it (sources often print GT without a unit). A bare
    # number never beats a unit-carrying one for DWT (hull numbers are bare).
    used_cols = {a[3] for a in rec.audit}
    tons = [t for t in toks if t[0] not in used_cols and (
        t[1] == "tonnage" or (t[1] == "bare" and t[2] >= 1000 and columns.index(t[0]) > first_len_col))]

    def pick(t, rule):
        return (t[2], t[4], t[0], rule) if t else None

    gt = pick(next((t for t in tons if t[3].startswith("gt")), None), "realign:tonnage_tag")
    dwt = pick(next((t for t in tons if t[3].startswith("dwt")), None), "realign:tonnage_tag")
    pool = [t for t in tons if not t[3].startswith(("gt", "dwt"))]
    with_unit = [t for t in pool if t[1] == "tonnage"]
    need_gt = gt is None and "GT" not in rec.v
    need_dwt = dwt is None and "DWT" not in rec.v
    if need_gt and need_dwt:
        if len(with_unit) >= 2:
            gt, dwt = pick(with_unit[0], "realign:tonnage_order"), pick(with_unit[1], "realign:tonnage_order")
        elif len(with_unit) == 1:
            d = with_unit[0]
            before = [t for t in pool if t is not d and columns.index(t[0]) < columns.index(d[0])]
            others = before or [t for t in pool if t is not d]
            dwt = pick(d, "realign:tonnage_unit")
            gt = pick(others[0] if others else None, "realign:tonnage_bare_gt")
            if gt is None:
                dwt = None             # a lone value: decide below
                pool = [d]
        elif len(pool) >= 2:
            gt, dwt = pick(pool[0], "realign:tonnage_order"), pick(pool[1], "realign:tonnage_order")
        if gt is None and dwt is None and len(pool) == 1:
            which = single_tonnage(rec, pool[0][2])
            if which == "DWT":
                dwt = pick(pool[0], "realign:tonnage_by_ratio")
                rec.flag("tonnage_by_ratio")
            elif which == "GT":
                gt = pick(pool[0], "realign:tonnage_by_ratio")
                rec.flag("tonnage_by_ratio")
            else:
                rec.flag("ambiguous_tonnage")
    elif need_dwt:
        dwt = pick((with_unit or pool or [None])[0], "realign:tonnage_remaining")
    elif need_gt:
        gt = pick((pool or [None])[0], "realign:tonnage_remaining")
    if gt and "GT" not in rec.v:
        rec.set("GT", gt[0], gt[1], gt[2], gt[3])
    if dwt and "DWT" not in rec.v:
        rec.set("DWT", dwt[0], dwt[1], dwt[2], dwt[3])

    for kind, field in (("speed", "speed_kn"), ("date", "delivery_year")):
        hit = next((t for t in toks if t[1] == kind), None)
        if hit:
            rule = "" if (kind == "speed" and hit[0] == "speed") or (kind == "date" and hit[0] == "delivery_date") \
                else f"realign:{kind}"
            rec.set(field, hit[2], hit[4], hit[0], rule)
    pw = next((t for t in toks if t[1] == "power"), None)
    if pw:
        kw, n, rpm, note = pw[2]
        rule = "realign:power" if pw[0] != "engine_power_output" else ""
        if note:
            rule = (rule + "; " if rule else "") + f"unit:{note}"
        rec.set("power_kW", round(kw, 1), pw[4], pw[0], rule)
        rec.set("n_engines", n)
        if rpm:
            rec.set("rpm", rpm)
    src = next((t for t in toks if t[1] == "source"), None)
    raw_src = (r.get("source_file") or "").strip()
    if raw_src and RE_PDF.search(raw_src):
        rec.set("source_file", raw_src)
    elif src:
        rec.set("source_file", src[2], src[4], src[0], "realign:source")
    else:
        rec.set("source_file", "")
    _teu(rec, r)


# ----------------------------------------------------------------------
# Ship types
# ----------------------------------------------------------------------
TYPE_RULES = [  # (regex on lower-case raw type, ship_class, tool_type)
    (r"\blngc?\b|liquefied natural", "LNG carrier", ""),
    (r"lpg|nh3|ammonia|lco2|\bco2\b|liquefied (?:gas|hydrogen|petroleum)|hydrogen carrier|\blh2\b|ethylene|gas carrier|\bngh\b",
     "Gas carrier", ""),
    (r"ferry|ropax|ro-pax|passenger/car|car/passenger", "Ferry / RoPax", ""),
    (r"cruis|passenger (?:ship|vessel|liner)|large passenger|small passenger|^passenger", "Passenger / cruise",
     "Cruise Ship"),
    (r"yacht", "Yacht", "Superyacht"),
    (r"car carrier|car truck|car/truck|\bpcc\b|\bpctc\b|vehicle|automobile|car and truck|ro-?ro|ro/ro|"
     r"roll-on|rail carrier", "Car carrier / Ro-Ro", ""),
    (r"container|\bteu\b|box ship", "Container ship", "Container Ship"),
    (r"tanker|vlcc|ulcc|suezmax|aframax|crude|product|chemical|oil carrier|bitumen|asphalt|methanol|shuttle|"
     r"caprolactam|sulfur|sulphur", "Tanker", "Tanker"),
    (r"bulk|bulker|\bore\b|coal|chip carrier|woodchip|wood chip|cement|panamax|capesize|kamsarmax|supramax|"
     r"ultramax|handymax|handysize|dunkirkmax|newcastlemax|vloc|valemax|\blog\b|limestone|laker|fly ash|\d+bc\b",
     "Bulk carrier", "Bulk carrier"),
    (r"cargo|multi-?purpose|\bmpp\b|heavy[- ]lift|reefer|refrigerated|open[- ]hatch|general", "General cargo",
     "Cargo vessel"),
]


def classify_type(raw):
    s = (raw or "").strip().lower()
    if is_null(s):
        return "Unknown", ""
    for pattern, cls, tool in TYPE_RULES:
        if re.search(pattern, s):
            return cls, tool
    return "Other", ""


# ----------------------------------------------------------------------
# Plausibility flags (never edits)
# ----------------------------------------------------------------------
GT_DWT_BANDS = {"Tanker": (0.35, 0.85), "Bulk carrier": (0.35, 0.85),
                "Container ship": (0.6, 1.5), "General cargo": (0.3, 1.2)}


def plausibility(rec):
    v = rec.v
    L, B, D, T = (v.get(k) for k in DIM_OUT)
    dwt, gt, spd = v.get("DWT"), v.get("GT"), v.get("speed_kn")
    if L is not None and not 20 <= L <= 420:
        rec.flag("L_out_of_range")
    if B is not None and not 2.0 <= B <= 70.0:
        rec.flag("B_out_of_range")
    if L and B and not 3.0 <= L / B <= 10.0:
        rec.flag("L/B_out_of_range")
    if B and T and not 1.8 <= B / T <= 6.0:
        rec.flag("B/T_out_of_range")
    if T and D and T >= D:
        rec.flag("T>=D")
    if L and D and not 6.0 <= L / D <= 22.0:
        rec.flag("L/D_out_of_range")
    if L and B and T and dwt and dwt / (1.025 * L * B * T) > 0.9:
        rec.flag("DWT_coefficient_too_high")
    if spd is not None and not 5.0 <= spd <= 45.0:
        rec.flag("speed_out_of_range")
    y = v.get("delivery_year")
    if y is not None and not 1950 <= y <= 2026:
        rec.flag("year_out_of_range")
    band = GT_DWT_BANDS.get(v.get("ship_class"))
    if band and gt and dwt and not band[0] <= gt / dwt <= band[1]:
        rec.flag("GT/DWT_atypical_for_class")
    pw = v.get("power_kW")
    if pw and L and B and T and spd:
        disp = 1.025 * L * B * T * 0.75            # rough, Cb 0.75
        adm = disp ** (2.0 / 3.0) * spd ** 3 / pw
        if not 150.0 <= adm <= 1500.0:
            rec.flag("admiralty_coefficient_atypical")


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------
CLEAN_COLUMNS = ["ship_id", "boat_name", "vessel_type_raw", "ship_class", "tool_type", "builder", "owner",
                 "delivery_year", "LOA_m", "B_m", "D_m", "T_m", "T_kind", "GT", "DWT", "speed_kn",
                 "power_kW", "n_engines", "rpm", "TEU", "capacity_raw", "source_file", "split", "flags"]
NUMERIC = {"delivery_year", "LOA_m", "B_m", "D_m", "T_m", "GT", "DWT", "speed_kn", "power_kW",
           "n_engines", "rpm", "TEU"}


def ship_id(raw_row, columns):
    key = "\x1f".join(str(raw_row.get(c, "")) for c in columns)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean_row(raw, columns):
    rec = Cleaned(raw, ship_id(raw, columns))
    name = (raw.get("boat_name") or "").strip()
    rec.set("boat_name", name)
    rec.set("vessel_type_raw", (raw.get("vessel_type") or "").strip())
    cls, tool = classify_type(raw.get("vessel_type"))
    rec.set("ship_class", cls)
    rec.set("tool_type", tool)
    for f in ("builder", "owner"):
        val = (raw.get(f) or "").strip()
        rec.set(f, "" if is_null(val) else val)
    cap = (raw.get("capacity") or "").strip()
    rec.set("capacity_raw", "" if is_null(cap) else cap)
    if is_aligned(raw):
        extract_aligned(rec)
    else:
        extract_shifted(rec, columns)
    rec.v.setdefault("T_kind", "unknown" if rec.v.get("T_m") is not None else "")
    plausibility(rec)
    return rec


def reject_reason(rec):
    name = rec.v.get("boat_name", "")
    if is_null(name):
        return "no_name"
    if re.search(r"\bdesign\b|\bconcept\b", name, re.I):
        return "design_or_concept_not_a_built_ship"
    if rec.v.get("LOA_m") is None and rec.v.get("DWT") is None:
        return "no_length_and_no_deadweight"
    return ""


def dedupe(recs):
    """Merge duplicates: same normalised name, LOA within 0.5 m, same builder
    (first word). Keeps the row with a source file and fewer flags."""
    groups = OrderedDict()
    for r in recs:
        loa = r.v.get("LOA_m")
        key = (norm_name(r.v.get("boat_name")), round(loa * 2) / 2 if loa else None,
               norm_name((r.v.get("builder") or "").split(" ")[0]))
        groups.setdefault(key, []).append(r)
    kept, merged = [], []
    for grp in groups.values():
        best = sorted(grp, key=lambda r: (not r.v.get("source_file"), len(r.flags), r.id))[0]
        kept.append(best)
        for r in grp:
            if r is not best:
                merged.append((r, best.id))
    return kept, merged


def temporal_split(recs, cutoff=None, frac=0.30):
    years = sorted(r.v["delivery_year"] for r in recs
                   if r.v.get("tool_type") and r.v.get("delivery_year") is not None)
    if cutoff is None and years:
        best = None
        for y in sorted(set(years)):
            share = sum(1 for x in years if x >= y) / len(years)
            if best is None or abs(share - frac) < abs(best[1] - frac):
                best = (y, share)
        cutoff = best[0]
    for r in recs:
        y = r.v.get("delivery_year")
        r.v["split"] = "validate" if (cutoff is not None and y is not None and y >= cutoff) else "fit"
    return cutoff


def apply_overrides(recs, path):
    """Apply data/overrides.csv (columns: ship_id, field, value, note, reject).

    * field + value: set that clean field (blank value clears it). Numbers
      may use thousands separators ("37,160").
    * reject column non-empty (or field 'reject'): move the ship to the
      rejected list with reason "manual: <note>" (the note, else the reject
      text, else "not relevant").
    Returns (rejected, n_applied, problems); problems lists rows that could
    not be applied (unknown ship_id or field, non-numeric value), so a typo
    is reported in the summary instead of silently ignored.
    """
    if not os.path.exists(path):
        return [], 0, []
    by_id = {r.id: r for r in recs}
    rejected, n, problems = [], 0, []
    seen_reject = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            sid = (row.get("ship_id") or "").strip()
            field = (row.get("field") or "").strip()
            raw_val = (row.get("value") or "").strip()
            note = (row.get("note") or "").strip()
            reject = (row.get("reject") or "").strip()
            if not sid:
                continue
            if sid not in by_id:
                problems.append(f"line {line_no}: ship_id {sid} not among kept ships")
                continue
            rec = by_id[sid]
            if reject or field == "reject":
                if sid not in seen_reject:
                    seen_reject.add(sid)
                    rejected.append((rec, f"manual: {note or (raw_val if field == 'reject' else '') or reject}"))
                continue
            if not field:
                problems.append(f"line {line_no}: no field and no reject for {sid}")
                continue
            if field not in CLEAN_COLUMNS or field in ("ship_id", "split", "flags"):
                problems.append(f"line {line_no}: field {field!r} cannot be overridden")
                continue
            if field in NUMERIC and raw_val:
                try:
                    value = to_float(raw_val)
                except ValueError:
                    problems.append(f"line {line_no}: {field} value {raw_val!r} is not a number")
                    continue
            else:
                value = raw_val if field not in NUMERIC else None
            rec.set(field, value, rec.v.get(field), field, f"manual override: {note}".strip(": "))
            rec.flag("manual_override")
            n += 1
    return rejected, n, problems


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}" if abs(v) < 1e6 else f"{v:.0f}"
    return str(v)


def run(input_path="boat_database_V2.csv", out_dir="data", cutoff=None, seed=42, overrides=None):
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        raw_rows = list(reader)

    recs = [clean_row(r, columns) for r in raw_rows]
    seen, rejected, survivors = set(), [], []
    for r in recs:
        if r.id in seen:
            rejected.append((r, "exact_duplicate_row"))
            continue
        seen.add(r.id)
        why = reject_reason(r)
        if why:
            rejected.append((r, why))
        else:
            survivors.append(r)
    kept, merged = dedupe(survivors)
    for r, into in merged:
        rejected.append((r, f"duplicate_of:{into}"))

    overrides = overrides or os.path.join(out_dir, "overrides.csv")
    manual_rej, n_over, problems = apply_overrides(kept, overrides)
    if manual_rej:
        ids = {r.id for r, _ in manual_rej}
        kept = [r for r in kept if r.id not in ids]
        rejected += manual_rej
    for r in kept:                       # re-check after overrides
        r.flags = [f for f in r.flags if not f.endswith(("_out_of_range", "_too_high", "_atypical",
                                                          "_atypical_for_class", "T>=D"))]
        plausibility(r)
    cut = temporal_split(kept, cutoff)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "ships_clean.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CLEAN_COLUMNS)
        for r in kept:
            r.v["flags"] = ";".join(r.flags)
            r.v["ship_id"] = r.id
            w.writerow([_fmt(r.v.get(c)) for c in CLEAN_COLUMNS])
    with open(os.path.join(out_dir, "ships_audit.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ship_id", "field", "raw_value", "raw_column", "clean_value", "rule"])
        for r in kept:
            for a in r.audit:
                w.writerow([a[0], a[1], a[2] if a[2] is not None else "", a[3], _fmt(a[4]), a[5]])
    with open(os.path.join(out_dir, "ships_rejected.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ship_id", "reason"] + list(columns))
        for r, why in rejected:
            w.writerow([r.id, why] + [r.raw.get(c, "") for c in columns])
    rng = random.Random(seed)
    unflagged = [r for r in kept if not [f for f in r.flags if f != "realigned_row"]]
    sample = rng.sample(unflagged, min(50, len(unflagged)))
    flagged = [r for r in kept if [f for f in r.flags if f != "realigned_row"]]
    review_cols = ["ship_id", "boat_name", "ship_class", "source_file", "delivery_year", "LOA_m", "B_m", "D_m",
                   "T_m", "GT", "DWT", "speed_kn", "power_kW", "flags"]
    review_path = os.path.join(out_dir, "review_sample.csv")
    marks = read_review_marks(review_path)
    listed = {r.id for r in sample} | {r.id for r in flagged}
    previously = [r for r in kept if r.id in marks and r.id not in listed]
    mark_cols = ["verified", "correct_field", "correct_value", "note"]
    with open(review_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["why_listed"] + review_cols + mark_cols)
        for why, group in (("random", sample), ("flagged", flagged), ("previously_reviewed", previously)):
            for r in group:
                m = marks.get(r.id, {})
                w.writerow([why] + [_fmt(r.v.get(c)) for c in review_cols] + [m.get(c, "") for c in mark_cols])
    if not os.path.exists(overrides):
        with open(overrides, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["ship_id", "field", "value", "note", "reject"])

    n_verified = sum(1 for m in marks.values() if m.get("verified", "").strip())
    summary = build_summary(raw_rows, kept, rejected, merged, cut, n_over, input_path, problems, n_verified)
    with open(os.path.join(out_dir, "cleaning_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary)
    return kept, rejected, cut, summary


def read_review_marks(path):
    """{ship_id: {verified, correct_field, correct_value, note}} for rows the
    reviewer filled in, so regenerating review_sample.csv keeps them."""
    if not os.path.exists(path):
        return {}
    marks = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            m = {c: (row.get(c) or "").strip() for c in ("verified", "correct_field", "correct_value", "note")}
            if any(m.values()):
                marks[row.get("ship_id", "")] = m
    return marks


def build_summary(raw_rows, kept, rejected, merged, cutoff, n_over, input_path, problems=(), n_verified=0):
    lines = [f"Cleaning summary for {input_path}", ""]
    lines.append(f"Raw rows:                 {len(raw_rows)}")
    lines.append(f"Kept:                     {len(kept)}")
    reasons = Counter(why.split(":")[0] for _, why in rejected)
    lines.append(f"Rejected / merged:        {len(rejected)}  " + str(dict(reasons)))
    lines.append(f"Manual overrides applied: {n_over}")
    lines.append(f"Ships marked verified in review: {n_verified}")
    if problems:
        lines.append(f"Override rows NOT applied ({len(problems)}):")
        lines += [f"  {p}" for p in problems]
    realigned = sum(1 for r in kept if "realigned_row" in r.flags)
    lines.append(f"Rows rebuilt by unit (realigned): {realigned}")
    lines.append("")
    flags = Counter(f for r in kept for f in r.flags)
    lines.append("Flags (kept ships):")
    for f, n in flags.most_common():
        lines.append(f"  {f:34s} {n:5d}")
    lines.append("")
    lines.append(f"Temporal split cutoff: delivered >= {cutoff} -> validate")
    by = Counter((r.v.get("tool_type") or "(none)", r.v["split"]) for r in kept)
    tools = sorted({t for t, _ in by})
    lines.append(f"{'tool_type':16s}{'fit':>6s}{'validate':>10s}{'  with L,B,T,DWT (fit/val)':>28s}")
    for t in tools:
        comp = {s: sum(1 for r in kept if (r.v.get("tool_type") or "(none)") == t and r.v["split"] == s
                       and all(r.v.get(k) is not None for k in ("LOA_m", "B_m", "T_m", "DWT")))
                for s in ("fit", "validate")}
        lines.append(f"{t:16s}{by[(t, 'fit')]:6d}{by[(t, 'validate')]:10d}{comp['fit']:>16d}/{comp['validate']}")
    lines.append("")
    classes = Counter(r.v.get("ship_class") for r in kept)
    lines.append("Ship classes: " + ", ".join(f"{c} {n}" for c, n in classes.most_common()))
    other = Counter(r.v.get("vessel_type_raw") for r in kept if r.v.get("ship_class") in ("Other", "Unknown"))
    lines.append(f"Unmapped vessel_type strings ({len(other)}): "
                 + "; ".join(f"{t!r} x{n}" for t, n in other.most_common(40)))
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# Reading the clean dataset (shared by fit_basis.py and validate_model.py)
# ----------------------------------------------------------------------
# Lbp/LOA by tool type: a stated assumption (typical values; the source
# gives LOA). Validation also reports length errors at +/-1 % on these.
LBP_OVER_LOA = {"Tanker": 0.97, "Bulk carrier": 0.97, "Container Ship": 0.95,
                "Cargo vessel": 0.95, "Cruise Ship": 0.90, "Superyacht": 0.88}

# A plausibility flag removes the fields it casts doubt on from fits and
# comparisons; the ship itself stays in for its other fields.
FIELD_EXCLUDED_BY = {
    "LOA_m": ("L_out_of_range", "L/B_out_of_range", "L/D_out_of_range"),
    "B_m": ("B_out_of_range", "L/B_out_of_range", "B/T_out_of_range"),
    "D_m": ("T>=D", "L/D_out_of_range"),
    "T_m": ("T>=D", "B/T_out_of_range", "DWT_coefficient_too_high"),
    "DWT": ("DWT_coefficient_too_high", "GT/DWT_atypical_for_class"),
    "speed_kn": ("speed_out_of_range",),
    "power_kW": ("admiralty_coefficient_atypical", "power_per_unit_count_unknown"),
}


def load_clean(path=os.path.join("data", "ships_clean.csv")):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def field_value(row, field):
    """Float value of a clean-dataset field, or None if missing or flagged."""
    raw = row.get(field, "")
    if raw in ("", None):
        return None
    flags = set((row.get("flags") or "").split(";"))
    if flags & set(FIELD_EXCLUDED_BY.get(field, ())):
        return None
    return float(raw)


def lbp(row, ratio_shift=0.0):
    """Lbp from LOA with the type ratio (shifted by ratio_shift, e.g. +0.01),
    or the value as given when the source already stated Lbp."""
    loa = field_value(row, "LOA_m")
    if loa is None:
        return None
    if "length_is_lbp" in (row.get("flags") or ""):
        return loa
    return loa * (LBP_OVER_LOA.get(row.get("tool_type"), 0.96) * (1.0 + ratio_shift))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", default="boat_database_V2.csv")
    ap.add_argument("--out", default="data")
    ap.add_argument("--cutoff", type=int, default=None)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    _, _, _, summary = run(a.input, a.out, a.cutoff, a.seed)
    print(summary)


if __name__ == "__main__":
    main()
