"""Independent re-implementation of Operation_Uptime_Model.xlsx in plain Python.

Reads every input from the workbook's Assumptions tab (no formulas are read) and
recomputes the key outputs, so it can be compared with LibreOffice's recalculation
for any input combination.
"""
import math
from decimal import Decimal, ROUND_HALF_UP
import datetime as dt
from openpyxl import load_workbook

ROLES = ["Electricians", "Mechatronics", "Automation", "Supervisors"]
RS = {"Electricians": "E", "Mechatronics": "M", "Automation": "A", "Supervisors": "S"}


def xround(v):
    """Excel ROUND(v,0): half away from zero."""
    return float(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if v >= 0 else -xround(-v)


def _num(v):
    return v if isinstance(v, (int, float)) else 0.0


def read_inputs(path):
    wb = load_workbook(path)  # formulas, not values: inputs are constants
    A = wb["Assumptions"]
    x, chans = {}, []
    for r in range(1, A.max_row + 1):
        key = A.cell(r, 1).value
        if not key:
            continue
        if isinstance(key, str) and len(key) == 3 and key[0] == "C" and key[1:].isdigit():
            chans.append(dict(id=key, chan=A.cell(r, 2).value, role=A.cell(r, 3).value, basis=A.cell(r, 4).value,
                              unit=_num(A.cell(r, 5).value), rate=A.cell(r, 6).value, q=_num(A.cell(r, 7).value),
                              mx=_num(A.cell(r, 8).value), adj=_num(A.cell(r, 9).value), fixed=_num(A.cell(r, 10).value)))
        else:
            v = A.cell(r, 4).value
            if v is not None and key not in ("ID",):
                x[key] = v
    return x, chans


def _round_to(v, step):
    """Excel ROUND(v, -k) for step = 10**k, half away from zero."""
    return xround(v / step) * step


def _roundup_to(v, step):
    """Excel ROUNDUP(v, -k): away from zero."""
    return math.copysign(math.ceil(abs(v) / step - 1e-12), v) * step


def derive(path, x, chans):
    """Independent re-implementation of the derived inputs (cells that hold formulas on the Assumptions tab).
    Only cells that hold a formula are derived; a typed number (e.g. from a test edit) is kept as typed."""
    A = load_workbook(path)["Assumptions"]
    raw = {}
    for r in range(1, A.max_row + 1):
        k = A.cell(r, 1).value
        if isinstance(k, str):
            raw[k] = (A.cell(r, 4).value, A.cell(r, 7).value, A.cell(r, 8).value)
    isf = lambda v: isinstance(v, str) and v.startswith("=")
    RSI = {"E": "G5", "M": "G6", "A": "G7", "S": "G8"}
    conv = {s: x["P" + s] * x["O" + s] * x["A" + s] for s in "EMAS"}
    tot_open = sum(_num(x[g]) for g in RSI.values())
    # initiative inputs
    if isf(raw.get("I2Q", (None,))[0]):
        x["I2Q"] = x["QE"]
    for s, g in RSI.items():
        if isf(raw["I1R" + s][0]):
            x["I1R" + s] = (xround(x["STAFF"] * x["MSH"] * x["TURN"] * (_num(x[g]) / tot_open) * (1 / conv[s] - 1))
                            if conv[s] > 0 and tot_open > 0 else 0.0)
        if isf(raw["I1F" + s][0]):
            d = x["I1FQ"] * conv[s] * x["I1A"]
            x["I1F" + s] = xround(x["REFSH"] * _num(x[g]) / d) if d > 0 else 0.0
    if isf(raw["I2S"][0]):
        x["I2S"] = x["RD2"] / x["I2Q"] / x["I2P"] if x["I2Q"] * x["I2P"] > 0 else 0.0
    if isf(raw["I3X"][0]):
        d = x["I3Q"] * conv["M"] * x["I3A"]
        x["I3X"] = _roundup_to(x["G4"] * _num(x["G6"]) / d, 10) if d > 0 else 0.0
    # timeline for StepStone ad counts
    d_ = lambda v: v.date() if isinstance(v, dt.datetime) else v
    lastsign = d_(x["T1"]); dE = x["T3"] + x["T4"] + x["T5"]; dS = dE + x["T6"]
    lastAppE = lastsign - dt.timedelta(days=dE + x["T2"]); lastAppS = lastsign - dt.timedelta(days=dS + x["T2"])
    start = d_(x["G1"])
    for c in chans:
        rq, rmx = raw[c["id"]][1], raw[c["id"]][2]
        s = {"Electricians": "E", "Mechatronics": "M", "Automation": "A", "Supervisors": "S"}[c["role"]]
        n = int(c["id"][1:])
        if isf(rq):
            kind = "CXH" if n <= 4 or n >= 17 else ("CXS" if n in (15, 16) else "CXB")
            c["q"] = x["Q" + s] * x[kind]
        if isf(rmx):
            q = c["q"]; pool = x["PS" + s] * x["PI" + s] + x["PR" + s]
            if n <= 4:
                c["mx"] = xround(_num(x[RSI[s]]) * x["APV"] * x["CPS"])
            elif n <= 8:
                c["mx"] = _round_to(pool * x["RXP"] / q, 10) if q > 0 else 0.0
            elif n <= 12:
                last = lastAppS if s == "S" else lastAppE
                c["mx"] = max(0.0, _roundup_to(((last - start).days + 1) / x["SSW"], 1))
            elif n <= 14:
                c["mx"] = _round_to(pool * x["RXL"] / q, 10) if q > 0 else 0.0
            elif n <= 16:
                c["mx"] = _round_to(x["RD" + s] / q, 10) if q > 0 else 0.0
            else:
                c["mx"] = _round_to(pool * x["RXG"] / q, 10) if q > 0 else 0.0
    return x, chans


def compute(path):
    x, chans = read_inputs(path)
    x, chans = derive(path, x, chans)
    d = lambda v: v.date() if isinstance(v, dt.datetime) else v
    opn = {r: _num(x[f"G{5+i}"]) for i, r in enumerate(ROLES)}
    conv = {r: x["P" + RS[r]] * x["O" + RS[r]] * x["A" + RS[r]] for r in ROLES}
    W = [x[f"W{k}"] for k in range(1, 12)]
    out = {}

    # ---- timeline / capacity
    start, end = d(x["G1"]), d(x["G2"])
    first = start + dt.timedelta(days=x["T0"])
    lastsign = d(x["T1"])
    dE = x["T3"] + x["T4"] + x["T5"]; dS = dE + x["T6"]
    lastAE = lastsign - dt.timedelta(days=dE); lastAS = lastsign - dt.timedelta(days=dS)
    lastAppE = lastAE - dt.timedelta(days=x["T2"]); lastAppS = lastAS - dt.timedelta(days=x["T2"])
    window = max(0, (lastAE - first).days + 1)
    slots = x["G3"] * window / 7
    out.update(slots=slots, lastAppE=lastAppE, lastAppS=lastAppS)

    # ---- channel rows (same order as the Channels tab)
    rows = []
    for c in chans:
        b = c["basis"]; rate = _num(c["rate"])
        if b in ("CPC", "Slot"):
            cpa = max(0.0, c["unit"] / rate) if rate > 0 else 0.0
            mx = 0.0 if rate <= 0 else (c["mx"] * rate if b == "Slot" else c["mx"])
        else:
            cpa = max(0.0, c["unit"]); mx = c["mx"]
        rows.append(dict(id=c["id"], chan=c["chan"], role=c["role"], type="Channel", basis=b, cpa=cpa, q=c["q"], mx=mx,
                         adj=c["adj"], fixed=c["fixed"], slotsize=rate if b == "Slot" else None, unit=c["unit"], cap=None))
    for r in ROLES:
        s = RS[r]; rec = x["I1R" + s]; reapps = rec * x["I1C"]
        rows.append(dict(id=f"I1a-{s}", chan="I1a", role=r, type="Initiative", basis="CPA",
                         cpa=(rec * x["I1M"] / reapps) if reapps > 0 else 0.0, q=x["I1Q"], mx=reapps, adj=x["I1A"], fixed=0, slotsize=None, cap=None))
    for r in ROLES:
        s = RS[r]; ref = x["I1F" + s]; c1 = conv[r] * x["I1A"]
        bonus_full = ref * x["I1FQ"] * c1 * x["I1B"]
        rows.append(dict(id=f"I1b-{s}", chan="I1b", role=r, type="Initiative", basis="CPA",
                         cpa=(bonus_full / ref) if ref > 0 else 0.0, q=x["I1FQ"], mx=ref, adj=x["I1A"], fixed=0, slotsize=None, cap=None))
    rows.append(dict(id="I2-E", chan="I2", role="Electricians", type="Initiative", basis="CPA", cpa=x["I2C"], q=x["I2Q"],
                     mx=x["I2P"] * x["I2S"], adj=x["I2A"], fixed=x["I2F"], slotsize=None, cap=None))
    rows.append(dict(id="I3-M", chan="I3", role="Mechatronics", type="Initiative", basis="CPA",
                     cpa=x["I3C"] + x["I3H"] / 60 * x["I3W"], q=x["I3Q"], mx=x["I3X"], adj=x["I3A"], fixed=x["I3T"],
                     slotsize=None, cap=x["G4"] * x["G6"]))

    for i, rw in enumerate(rows):
        rw["row"] = 5 + i
        rw["L"] = conv[rw["role"]] * rw["adj"]
        rw["K"] = rw["mx"] * rw["q"]
        rw["N"] = rw["K"] * rw["L"] if rw["cap"] is None else min(rw["K"] * rw["L"], rw["cap"])
        rw["O"] = rw["cpa"] / rw["q"] if rw["q"] > 0 else 0.0
        rw["P"] = ((rw["N"] / rw["L"] / rw["q"] * rw["cpa"] + rw["fixed"]) / rw["N"]) if rw["N"] > 0 else 0.0
        rw["sort"] = rw["P"] + rw["row"] / 1e6
        paid = rw["type"] == "Channel" and rw["basis"] in ("CPC", "CPA") and opn[rw["role"]] > 0
        if paid:
            ntest = sum(1 for o in rows if o["role"] == rw["role"] and o["type"] == "Channel" and o["basis"] in ("CPC", "CPA"))
            cap_spend = opn[rw["role"]] / ntest / (rw["q"] * rw["L"]) * rw["cpa"] if rw["q"] * rw["L"] > 0 else 0.0
            rw["Z"] = min(x["B2"], rw["mx"] * rw["cpa"], cap_spend)
        else:
            rw["Z"] = 0.0
        rw["AE"] = rw["Z"] / rw["cpa"] if rw["cpa"] > 0 else 0.0
        rw["AF"] = rw["AE"] * rw["q"]
        rw["AG"] = rw["AF"] * rw["L"]
        rw["AH"] = max(0.0, rw["N"] - rw["AG"])
    for r in ROLES:
        rr = [rw for rw in rows if rw["role"] == r]
        need = opn[r] - sum(rw["AG"] for rw in rr)
        for rw in rr:
            cheaper = sum(o["AH"] for o in rr if o["sort"] < rw["sort"])
            rw["AI"] = min(rw["AH"], max(0.0, need - cheaper))
    for rw in rows:
        rw["U"] = rw["AG"] + rw["AI"]
        rw["V"] = rw["U"] / rw["L"] if rw["L"] > 0 else 0.0
        rw["W"] = rw["V"] / rw["q"] if rw["q"] > 0 else 0.0
        if rw["basis"] == "Slot":
            rw["X"] = math.ceil(rw["W"] / rw["slotsize"] - 1e-12) * max(0.0, rw["unit"]) if rw["slotsize"] else 0.0
        else:
            rw["X"] = rw["W"] * rw["cpa"]
        rw["Y"] = rw["fixed"] if rw["U"] > 0 else 0.0
        rw["AA"] = rw["X"] + rw["Y"]
        rw["AB"] = (rw["X"] + rw["Y"]) / rw["U"] if rw["U"] > 0 else None
    out["rows"] = rows

    # ---- budget
    hires_plan = sum(rw["U"] for rw in rows)
    qual = sum(rw["V"] for rw in rows)
    apps = sum(rw["W"] for rw in rows)
    planned = sum(rw["AA"] for rw in rows)
    B1 = x["B1"]
    reserve = planned / (1 - B1) * B1 if B1 < 1 else 0.0
    total = planned + reserve
    rec = math.ceil(total / x["B5"] - 1e-12) * x["B5"] if x["B5"] > 0 else total
    hpq = hires_plan / qual if qual > 0 else 0.0
    max_cap_hires = slots * hpq
    hires = min(hires_plan, max_cap_hires)
    out.update(planned=planned, reserve=reserve, total=total, rec=rec, hires_plan=hires_plan, hires=hires,
               qual=qual, apps=apps, util=(qual / slots if slots > 0 else (9.99 if qual > 0 else 0)), max_cap_hires=max_cap_hires,
               tests_total=sum(rw["Z"] for rw in rows))
    out["hires_by_role"] = {r: sum(rw["U"] for rw in rows if rw["role"] == r) for r in ROLES}
    out["spend_by_role"] = {r: sum(rw["AA"] for rw in rows if rw["role"] == r) for r in ROLES}

    # ---- scenarios
    levels = [1, 1 - x["B6"], 1 - x["B3"], 1 - x["B7"]]
    scen = []
    keys = {rw["row"]: (rw["AB"] if rw["AB"] is not None else 0) + (rw["row"] + 3) / 1e6 for rw in rows}
    for L in levels:
        avail = rec * L * (1 - B1)
        sav = max(0.0, planned - avail)
        hb = {r: 0.0 for r in ROLES}
        qs = 0.0
        for rw in rows:
            above = sum(o["AA"] for o in rows if keys[o["row"]] > keys[rw["row"]])
            cut = min(rw["AA"], max(0.0, sav - above))
            if rw["X"] > 0:
                h = rw["U"] * max(0.0, rw["X"] - min(cut, rw["X"])) / rw["X"]
            elif rw["AA"] > 0:
                h = rw["U"] * (1 - cut / rw["AA"])
            else:
                h = rw["U"]
            hb[rw["role"]] += h
            qs += h * rw["V"] / rw["U"] if rw["U"] > 0 else 0.0
        factor = min(1.0, slots / qs) if qs > 0 else 1.0
        hb = {r: v * factor for r, v in hb.items()}
        scen.append(dict(level=L, budget=rec * L, by_role=hb, total=sum(hb.values())))
    out["scen"] = scen

    # ---- sensitivity (Funnel rows 42-47)
    S1 = x["S1"]; O9 = qual; B9 = sum(opn.values())
    capr = {r: sum(rw["N"] for rw in rows if rw["role"] == r) for r in ROLES}
    def hires_possible(qn, slots_, f):
        lim_slots = slots_ / qn * B9 if qn > 0 else B9
        lim_chan = sum(min(opn[r], capr[r] * f) for r in ROLES)
        return min(B9, lim_slots, lim_chan)
    out["sens"] = [
        hires_possible(O9, slots, 1),
        hires_possible(O9 / (1 - S1), slots, 1 - S1),
        hires_possible(O9 / (1 - S1), slots, 1 - S1),
        hires_possible(O9, slots, 1 - S1),
        hires_possible(O9, slots, 1),
        hires_possible(O9, slots * (1 - S1), 1),
    ]

    # ---- initiative test bars (Initiatives rows 53-55)
    def rowv(id_, k): return sum(rw[k] for rw in rows if rw["id"] == id_)
    # weekly shares are re-spread over weeks that start on or before the last useful application (Weekly col D)
    useful = [(start + dt.timedelta(days=7 * k)) <= lastAppE for k in range(11)]
    tot_u = sum(w for w, u in zip(W, useful) if u)
    W = [(w / tot_u if (u and tot_u > 0) else 0.0) for w, u in zip(W, useful)]
    i12 = x["I1W1"] + x["I1W2"]; w12 = W[0] + W[1]
    pq1 = sum(rowv(f"I1a-{RS[r]}", "V") for r in ROLES) * i12 + sum(rowv(f"I1b-{RS[r]}", "V") for r in ROLES) * w12
    sh2 = W[0] * 4 / 7 + W[1] + W[2] * 3 / 7; pq2 = rowv("I2-E", "V") * sh2
    sh3 = W[1] + W[2]; pq3 = rowv("I3-M", "V") * sh3
    cpq2 = x["I2C"] / x["I2Q"] if x["I2Q"] > 0 else 0
    i3row = [rw for rw in rows if rw["id"] == "I3-M"][0]
    cpq3 = i3row["cpa"] / i3row["q"] if i3row["q"] > 0 else 0
    def bar(pq):
        p_ = max(1, math.floor(pq * x["TP1"] + 1e-9))
        return (p_, min(p_, max(1, math.ceil(pq * x["TK1"] - 1e-9))))
    out["tests"] = [
        dict(planq=pq1, budget=sum(x["I1R" + RS[r]] for r in ROLES) * x["I1M"], passq=bar(pq1)[0], killq=bar(pq1)[1]),
        dict(planq=pq2, budget=x["I2F"] + rowv("I2-E", "X") * sh2, passq=bar(pq2)[0], killq=bar(pq2)[1],
             passcpq=xround(cpq2 * x["TP2"] / 10) * 10, killcpq=max(xround(cpq2 * x["TP2"] / 10) * 10, xround(cpq2 * x["TK2"] / 10) * 10)),
        dict(planq=pq3, budget=x["I3T"] + rowv("I3-M", "X") * sh3, passq=bar(pq3)[0], killq=bar(pq3)[1],
             passcpq=xround(cpq3 * x["TP2"] / 10) * 10, killcpq=max(xround(cpq3 * x["TP2"] / 10) * 10, xround(cpq3 * x["TK2"] / 10) * 10)),
    ]
    out["openings"] = opn
    return out
