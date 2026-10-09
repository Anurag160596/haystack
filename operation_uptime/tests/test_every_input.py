"""One-at-a-time sweep: change every single input on the Assumptions tab, one by one.

For each input: copy the model, move that one value, recalculate with LibreOffice, then
  1. run the full check set from run_tests.py (0 formula errors, tie-out flags, invariants,
     agreement with the independent oracle on 59 outputs);
  2. measure reach: how many output cells across all tabs changed, and how the headline
     numbers moved (recommended budget, planned spend, expected hires, qualified needed);
  3. for inputs with a known economic direction, check the headline moved the right way.

Inputs whose shares must sum to 100% (weekly spend W1–W11, rediscovery waves I1W1–3) are
moved as a pair (one share down, the next up) so the plan stays valid.
A tie-out flag that fires is accepted only when it names the problem (the model is telling
the user why the input is invalid); otherwise the case fails.

Usage: python3 test_every_input.py   → writes every_input_results.json and prints a table.
"""
import sys, os, json, shutil, tempfile, datetime as dt
from openpyxl import load_workbook
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_tests as rt

HERE = os.path.dirname(os.path.abspath(__file__))
OUTS = ["Summary", "Funnel", "Initiatives", "Channels", "Budget", "Weekly", "Tracker"]
CHCOLS = {"E": "cost / unit price", "F": "rate (CPC→apply or apps per ad)", "G": "share qualified",
          "H": "max applications", "I": "downstream adjustment", "J": "fixed cost"}
WEIGHT_PAIRS = {**{f"W{k}": f"W{k+1}" for k in range(1, 6)}, "W6": "W5",
                **{f"W{k}": "W6" for k in range(7, 12)}, "I1W1": "I1W2", "I1W2": "I1W3", "I1W3": "I1W2"}


def inputs(path):
    A = load_workbook(path)["Assumptions"]
    out = []
    for r in range(1, A.max_row + 1):
        k = A.cell(r, 1).value
        if not isinstance(k, str) or k == "ID" or A.cell(r, 4).value is None:
            continue
        if A.cell(r, 4).value in ("CPC", "CPA", "Slot", "Free"):  # channel row: six numeric inputs
            for col in "EFGHIJ":
                v_ = A[f"{col}{r}"].value
                if v_ is None or (isinstance(v_, str) and v_.startswith("=")):   # unused, or calculated from evidence inputs
                    continue
                out.append(((k, col), f"{k} {A.cell(r, 2).value[:28]} / {A.cell(r, 3).value}: {CHCOLS[col]}",
                            A[f"{col}{r}"].value, "%" if col == "G" or (col == "F" and A.cell(r, 4).value == "CPC") else ""))
        elif isinstance(A.cell(r, 4).value, str) and A.cell(r, 4).value.startswith("="):
            continue   # derived input: a live formula on the evidence inputs, which are swept themselves
        else:
            out.append((k, f"{k} {A.cell(r, 2).value}", A.cell(r, 4).value, A.cell(r, 5).value))
    return out


def move(key, val, unit):
    """Return the edit dict for a realistic one-input change."""
    k = key if isinstance(key, str) else None
    if k in WEIGHT_PAIRS:
        return "pair", None
    if isinstance(val, dt.datetime):
        if k == "G1": return "shift", val + dt.timedelta(days=1)
        if k == "G2": return "shift", val - dt.timedelta(days=3)
        return "shift", val + dt.timedelta(days=2)
    if unit == "days":
        return "+1 day", val + 1
    if unit == "%" or (k and k[:1] in "QPOA" and len(k) == 2) or (k and k[:2] == "PI"):
        return ("down 20%", val * 0.8) if val > 0 else ("0 → 10%", 0.1)
    if val == 0:
        return "0 → 1", 1
    return "up 20%", val * 1.2


def snapshot(path):
    wb = load_workbook(path, data_only=True)
    vals = {}
    for n in OUTS:
        for row in wb[n].iter_rows():
            for c in row:
                if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                    vals[f"{n}!{c.coordinate}"] = c.value
                elif isinstance(c.value, str) and n in ("Summary", "Funnel", "Channels", "Weekly", "Budget"):
                    vals[f"{n}!{c.coordinate}"] = c.value
    B, F = wb["Budget"], wb["Funnel"]
    head = dict(rec=B["C12"].value, planned=B["C9"].value, hires=B["C13"].value, qneed=F["K9"].value,
                slots=F["B22"].value, tests=B["C8"].value, qual=F["B23"].value)
    flags = dict(input_check=str(wb["Summary"]["C19"].value), budget=str(B["B40"].value),
                 weekly=str(wb["Weekly"]["S15"].value), matrix=str(wb["Weekly"]["B55"].value))
    return vals, head, flags


# expected direction of a headline when the input moves as in move()
def direction(key, how):
    """(headline, sign) the headline must move by when the input moves as described in `how`."""
    up = not how.startswith("down")
    s = 1 if up else -1
    k = key if isinstance(key, str) else key[1]
    if isinstance(key, str):
        if k == "G3": return ("slots", s)                                   # more capacity → more slots
        if k in ("G5", "G6", "G7", "G8"): return ("planned", s)             # more openings → more spend
        if len(k) == 2 and k[0] in "PAO" and k[1] in "EMAS": return ("qneed", -s)  # lower pass/offer/accept → more qualified needed
        if k == "B1": return ("rec", s)                                     # bigger reserve → bigger budget
        if k == "B2": return ("tests", s)                                   # bigger test tranche → more test spend
        if k in ("T2", "T3", "T4", "T5", "T6"): return ("slots", -s)        # longer lags → fewer usable slots (or equal)
    else:
        if k == "E": return ("planned", s)                                  # dearer channel never makes the plan cheaper
    return None


def main():
    tmp = tempfile.mkdtemp(prefix="uptime_oat_")
    base = os.path.join(tmp, "base.xlsx")
    shutil.copy(rt.MODEL, base); rt.recalc(base)
    bvals, bhead, _ = snapshot(base)
    allin = inputs(rt.MODEL)
    vals_by_key = {k: v for k, _, v, _ in allin}
    results = []
    for i, (key, label, val, unit) in enumerate(allin):
        how, new = move(key, val, unit)
        if how == "pair":
            other = WEIGHT_PAIRS[key]
            d = 0.02
            a, b = vals_by_key[key], vals_by_key[other]
            if a >= d: edits, how = {key: a - d, other: b + d}, f"−2 pts (to {other})"
            else: edits, how = {key: a + d, other: b - d}, f"+2 pts (from {other})"
        else:
            edits = {key: new}
        name = f"oat_{i:03d}"
        res = rt.run_case(name, label, edits, {}, tmp)
        path = os.path.join(tmp, f"{name}.xlsx")
        try:
            v, head, flags = snapshot(path)
        except Exception as e:
            v, head, flags = {}, {}, {"error": str(e)}
        changed = sum(1 for c in set(bvals) | set(v) if bvals.get(c) != v.get(c) and not (
            isinstance(bvals.get(c), (int, float)) and isinstance(v.get(c), (int, float)) and abs(bvals[c] - v[c]) <= 1e-9 * max(1, abs(bvals[c]))))
        # flag checks: accept a fired flag only if it explains itself
        fired = {n: t for n, t in flags.items() if n != "error" and not t.startswith("✓")}
        explained = all(t.startswith("✗") and len(t) > 15 for t in fired.values())
        checks = [c for c in res["checks"] if not ("flag is ✓" in c["check"] and fired and explained)]
        if fired and explained:
            checks.append(dict(check="fired flag names the problem", ok=True, detail="; ".join(fired.values())[:200]))
        dirn = direction(key, how)
        if dirn and head:
            m, s = dirn
            ok = (head[m] - bhead[m]) * s >= -1e-6 * max(1, abs(bhead[m]))
            checks.append(dict(check=f"{m} moves the right way", ok=ok, detail=f"{bhead[m]} → {head[m]}"))
        passed = all(c["ok"] for c in checks)
        delta = {k_: (head.get(k_, 0) or 0) - (bhead[k_] or 0) for k_ in ("rec", "planned", "hires", "qneed")} if head else {}
        results.append(dict(key=key if isinstance(key, str) else f"{key[0]}:{key[1]}", label=label, change=how,
                            edits={str(k_): str(v_) for k_, v_ in edits.items()}, cells_changed=changed,
                            delta=delta, flags=fired, passed=passed, checks=checks))
        bad = [c for c in checks if not c["ok"]]
        print(f"{'PASS' if passed else 'FAIL'} {results[-1]['key']:9s} {how:22s} cells Δ {changed:5d}  "
              f"budget Δ {delta.get('rec', 0):+9.0f}  hires Δ {delta.get('hires', 0):+6.2f}"
              + (f"  FLAG: {list(fired.values())[0][:60]}" if fired else "")
              + ("".join(f"\n      ✗ {c['check']}: {c['detail'][:300]}" for c in bad)), flush=True)
    json.dump(results, open(os.path.join(HERE, "every_input_results.json"), "w"), indent=1, default=str)
    n = len(results); p = sum(r["passed"] for r in results)
    dead = [r["key"] for r in results if r["cells_changed"] == 0]
    print(f"\nINPUTS {p}/{n} passed · checks {sum(c['ok'] for r in results for c in r['checks'])}/{sum(len(r['checks']) for r in results)} · no visible effect: {dead}")
    return 0 if p == n else 1


if __name__ == "__main__":
    sys.exit(main())
