"""Test suite for Operation_Uptime_Model.xlsx.

For every case: copy the model, change inputs on the Assumptions tab, recalculate with
LibreOffice, then check (1) zero formula errors, (2) the model's own tie-out flags,
(3) logical invariants, and (4) agreement with an independent Python oracle (oracle.py).

Usage: python3 run_tests.py [path/to/model.xlsx] [--only name,name]
"""
import sys, os, json, shutil, subprocess, glob, datetime as dt, tempfile
from openpyxl import load_workbook
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = next((a for a in sys.argv[1:] if a.endswith(".xlsx")), os.path.join(HERE, "..", "Operation_Uptime_Model.xlsx"))
ONLY = None
if "--only" in sys.argv:
    ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(","))
RECALC = (glob.glob("/root/.claude/skills/synced/*/xlsx/scripts/recalc.py") + glob.glob("/mnt/skills/public/xlsx/scripts/recalc.py"))[0]
ROLES = oracle.ROLES
D = dt.datetime

def _current(key):
    """Current value of an Assumptions input in the delivered model (used where a case moves spend between weeks)."""
    A_ = load_workbook(MODEL, data_only=True)["Assumptions"]
    return next(A_.cell(r, 4).value for r in range(1, A_.max_row + 1) if A_.cell(r, 1).value == key)
_W6 = _current("W6")

# name, description, {input ID or (channel ID, column letter): value}, expected flags
CASES = [
 ("base", "Recommended plan as delivered", {}, {}),
 ("capacity_45", "Client can only assess 45/week (binding)", {"G3": 45}, {}),
 ("capacity_100", "Client can assess 100/week (slack)", {"G3": 100}, {}),
 ("capacity_0", "No recruiter capacity at all", {"G3": 0}, {}),
 ("elec_pass_40", "Electrician assessment pass rate 40%", {"PE": 0.40}, {}),
 ("elec_accept_0", "No electrician ever accepts (conversion = 0)", {"AE": 0}, {}),
 ("all_accept_100", "Every offer accepted", {"AE": 1, "AM": 1, "AA": 1, "AS": 1}, {}),
 ("elec_open_0", "Electrician openings = 0", {"G5": 0}, {}),
 ("elec_open_200", "Electrician openings = 200 (channels can't cover)", {"G5": 200}, {}),
 ("all_open_0", "All openings = 0", {"G5": 0, "G6": 0, "G7": 0, "G8": 0}, {}),
 ("polish_cap_0", "Polish sources not allowed", {"G4": 0}, {}),
 ("polish_cap_100", "Polish sources uncapped", {"G4": 1}, {}),
 ("tests_0", "No test tranches", {"B2": 0}, {}),
 ("tests_5000", "Very large test tranches (€5,000 per cell)", {"B2": 5000}, {}),
 ("test_split_0", "All test spend in week 2", {"B4": 0}, {}),
 ("test_split_1", "All test spend in week 1", {"B4": 1}, {}),
 ("reserve_0", "No reserve", {"B1": 0}, {}),
 ("reserve_50", "50% reserve", {"B1": 0.5}, {}),
 ("cut_0", "Budget-cut scenario 0%", {"B3": 0}, {}),
 ("cut_100", "Budget-cut scenario 100% (no money)", {"B3": 1}, {}),
 ("i2_rejected", "Client rejects construction electricians (I2 share qualified 0)", {"I2Q": 0}, {}),
 ("apply_rate_0", "Programmatic electricians apply rate 0 and StepStone electricians 0 apps/ad", {("C05", "F"): 0, ("C09", "F"): 0}, {}),
 ("max_apps_0", "LinkedIn automation has no volume", {("C13", "H"): 0}, {}),
 ("free_channel", "Programmatic mechatronics costs nothing", {("C06", "E"): 0}, {}),
 ("q_100", "Programmatic electricians 100% qualified", {("C05", "G"): 1}, {}),
 ("no_rediscovery", "ATS export empty and no referrals", {"I1RE": 0, "I1RM": 0, "I1RA": 0, "I1RS": 0, "I1FE": 0, "I1FM": 0, "I1FA": 0, "I1FS": 0}, {}),
 ("deadline_1nov", "Last signing date 1 Nov (window closes before it opens)", {"T1": D(2026, 11, 1)}, {"weekly_ok": False, "matrix_ok": False}),
 ("deadline_23dec", "Last signing date 23 Dec", {"T1": D(2026, 12, 23)}, {}),
 ("supervisors_impossible", "Supervisor extra round 60 days: no supervisor can sign in time", {"T6": 60}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "supervisors cannot apply"}),
 ("weights_bad", "Weekly spend shares sum to 131%", {"W6": 0.5}, {"weekly_ok": False, "flag_contains": "shares must sum"}),
 ("i1_waves_bad", "Rediscovery wave shares sum to 90%", {"I1W3": 0.15}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "shares must sum"}),
 ("round_step_1", "Recommended budget not rounded", {"B5": 1}, {}),
 ("capacity_1", "Recruiters can assess 1 qualified applicant a week", {"G3": 1}, {}),
 ("capacity_1000_open3x", "Capacity 1,000/week and 3× the openings", {"G3": 1000, "G5": 90, "G6": 135, "G7": 45, "G8": 30}, {}),
 ("open_1_each", "1 opening per role (test hires exceed it)", {"G5": 1, "G6": 1, "G7": 1, "G8": 1}, {}),
 ("mech_open_1", "1 mechatronics opening (fractional Polish cap)", {"G6": 1}, {}),
 ("q_001_all", "Every channel and initiative 1% qualified", {**{("C%02d" % n, "G"): 0.01 for n in range(1, 21)}, "I1Q": 0.01, "I1FQ": 0.01, "I2Q": 0.01, "I3Q": 0.01}, {}),
 ("i3_minutes_0", "Polish pre-screen calls take no time", {"I3H": 0}, {}),
 ("t2_0", "Application assessed the same day", {"T2": 0}, {}),
 ("weights_week1", "All regular spend in week 1", {"W1": 1, "W2": 0, "W3": 0, "W4": 0, "W5": 0, "W6": 0}, {}),
 ("i1_all_week1", "All rediscovery re-applications in week 1", {"I1W1": 1, "I1W2": 0, "I1W3": 0}, {}),
 ("round_100k", "Budget rounded to €100k steps", {"B5": 100000}, {}),
 ("automation_no_volume", "Automation: every source has zero volume", {("C03", "H"): 0, ("C07", "H"): 0, ("C11", "H"): 0, ("C13", "H"): 0, ("C19", "H"): 0, "I1RA": 0, "I1FA": 0}, {}),
 ("reserve_99", "Reserve 99% of total", {"B1": 0.99}, {}),
 ("reserve_100", "Reserve 100% (invalid)", {"B1": 1}, {"budget_ok": False, "weekly_ok": False, "matrix_ok": True, "flag_contains": "reserve share"}),
 ("combo_cap45_cut", "Capacity 45 and the budget scenarios", {"G3": 45, "B3": 0.3}, {}),
 ("cap2_cut50", "Capacity 2/week with a 50% budget cut", {"G3": 2, "B3": 0.5}, {}),
 ("elec500_mech0", "500 electrician openings, no mechatronics openings", {"G5": 500, "G6": 0}, {}),
 ("mech_auto_0_g4_40", "Polish cap 40% with no mechatronics or automation openings", {"G4": 0.4, "G6": 0, "G7": 0}, {}),
 ("all_apply_1", "Every CPC channel converts 100% of clicks", {**{("C%02d" % n, "F"): 1.0 for n in (5, 6, 7, 8, 13, 14, 17, 18, 19, 20)}}, {}),
 ("i2q_1", "Every construction electrician qualifies", {"I2Q": 1}, {}),
 ("stepstone_1app", "StepStone ads bring 1 application each", {("C09", "F"): 1, ("C10", "F"): 1, ("C11", "F"): 1, ("C12", "F"): 1}, {}),
 ("deadline_first_assess", "Last assessment falls on the first assessment day", {"T1": D(2026, 11, 8)}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "no application can sign"}),
 ("t0_0", "Assessments start on launch day", {"T0": 0}, {}),
 ("b2_1euro", "€1 test tranches", {"B2": 1}, {}),
 ("levels_all_100", "All scenario levels at 100%", {"B3": 0, "B6": 0, "B7": 0}, {}),
 ("w_all_week6", "All regular spend in week 6 (after the supervisor cut-off)", {"W1": 0, "W2": 0, "W3": 0, "W4": 0, "W5": 0, "W6": 1}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "supervisor cut-off"}),
 ("open_1000_cap1000", "1,000 openings per role, capacity 1,000/week", {"G3": 1000, "G5": 1000, "G6": 1000, "G7": 1000, "G8": 1000}, {}),
 ("round_step_0", "Rounding step 0 (no rounding)", {"B5": 0}, {}),
 ("neg_open_elec", "Typo: electrician openings −5", {"G5": -5}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("rate_above_1", "Typo: electrician pass rate 150%", {"PE": 1.5}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("channel_q_above_1", "Typo: programmatic electricians 120% qualified", {("C05", "G"): 1.2}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("negative_cost", "Typo: Meta mechatronics cost −€12 per application", {("C16", "E"): -12}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("deadline_after_end", "Last signing date after the campaign ends (5 Jan 2027)", {"T1": D(2027, 1, 5)}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("negative_capacity", "Typo: capacity −10/week", {"G3": -10}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("cap3_open1", "Capacity 3/week, 1 opening per role", {"G3": 3, "G5": 1, "G6": 1, "G7": 1, "G8": 1}, {}),
 ("pass_all_1", "Everyone qualified passes the assessment", {"PE": 1, "PM": 1, "PA": 1, "PS": 1}, {}),
 ("offer_all_1", "Everyone who passes gets an offer", {"OE": 1, "OM": 1, "OA": 1, "OS": 1}, {}),
 ("q_all_1", "Every channel 100% qualified (test hires must stay ≤ openings)", {**{("C%02d" % n, "G"): 1.0 for n in range(1, 21)}}, {}),
 ("b2_100k", "€100,000 test tranches (capped at openings)", {"B2": 100000}, {}),
 ("i1c_1", "Every past applicant re-applies", {"I1C": 1}, {}),
 ("i1b_0", "No referral bonus", {"I1B": 0}, {}),
 ("i2s_0", "No construction electrician applies", {"I2S": 0}, {}),
 ("i3x_0", "No Polish applications", {"I3X": 0}, {}),
 ("t345_0", "Interview, offer and signature are instant", {"T3": 0, "T4": 0, "T5": 0}, {}),
 ("t1_31dec", "Last signing date 31 Dec", {"T1": D(2026, 12, 31)}, {}),
 ("w_even_1_6", "Spend split evenly over weeks 1–6", {"W1": 1/6, "W2": 1/6, "W3": 1/6, "W4": 1/6, "W5": 1/6, "W6": 1 - 5/6}, {}),
 ("b4_half_b2_0", "Test split 50/50 with no tests", {"B4": 0.5, "B2": 0}, {}),
 ("i1a_0", "Initiative-1 conversion adjustment 0", {"I1A": 0}, {}),
 ("i1w_even", "Rediscovery waves 1/3 each", {"I1W1": 1/3, "I1W2": 1/3, "I1W3": 1 - 2/3}, {}),
 ("i3x_negative", "Typo: Polish max applications −100", {"I3X": -100}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("threshold_negative", "Typo: Tracker scale-up threshold −1", {"R3": -1}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("campaign_end_before_start", "Campaign end before its start", {"G2": D(2026, 10, 1)}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("spend_after_cutoff_wk7", "All regular spend in week 7 (after the 24 Nov cut-off), no supervisors", {"G8": 0, "W1": 0, "W2": 0, "W3": 0, "W4": 0, "W5": 0, "W6": 0, "W7": 1}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "no spend share falls before the last useful application"}),
 ("spend_partly_late", "10 pts of weekly spend typed into week 7: re-spread over weeks 1–6, plan still ties", {"W6": _W6 - 0.10, "W7": 0.10}, {}),
 ("lags_one_day_longer", "Every lag one day longer (cut-off moves into week 5): week-6 share re-spread", {"T2": 7, "T3": 9, "T4": 4, "T5": 8}, {}),
 ("start_one_day_later", "Campaign starts Wed 21 Oct: week 6 now starts after the cut-off", {"G1": D(2026, 10, 21)}, {}),
 ("spend_after_cutoff_wk11", "All regular spend in week 11, no supervisors", {"G8": 0, "W1": 0, "W2": 0, "W3": 0, "W4": 0, "W5": 0, "W6": 0, "W11": 1}, {"weekly_ok": False, "matrix_ok": False, "flag_contains": "no spend share falls before the last useful application"}),
 ("t0_100", "First assessment 100 days after launch", {"T0": 100}, {"weekly_ok": False, "flag_contains": "assessments start"}),
 ("fractional_openings", "Fractional openings (2.5 electricians)", {"G5": 2.5}, {}),
 ("tp_tk_equal", "Initiative pass and kill thresholds both 100% (contradictory)", {"TP1": 1, "TK1": 1}, {"budget_ok": False, "weekly_ok": False, "flag_contains": "invalid input"}),
 ("tp_tk_close", "Kill threshold just below pass (59% vs 60%), kill cost bar equal to pass", {"TK1": 0.59, "TK2": 1.5}, {}),
 ("combo_stress", "Capacity 45 + electrician pass 40% + 30% cut + I2 rejected", {"G3": 45, "PE": 0.40, "I2Q": 0}, {}),
]

import random
_rng = random.Random(20261020)
for _k in range(1, 61):
    _e = {"G3": _rng.randint(30, 80), "B1": round(_rng.uniform(0, 0.3), 3), "B2": _rng.choice([0, 300, 750, 1500]),
          "B3": round(_rng.uniform(0, 0.6), 2), "G4": round(_rng.uniform(0, 1), 2)}
    for _s in "EMAS":
        _e["P" + _s] = round(_rng.uniform(0.3, 0.8), 3)
        _e["A" + _s] = round(_rng.uniform(0.4, 0.95), 3)
    for _g, _base in zip(("G5", "G6", "G7", "G8"), (30, 45, 15, 10)):
        _e[_g] = _rng.randint(0, _base * 2)
    for _c in ["C%02d" % n for n in range(5, 21)]:
        if _rng.random() < 0.5:
            _e[(_c, "G")] = round(_rng.uniform(0.03, 0.4), 3)
    _e["I2Q"] = _rng.choice([0, 0.1, 0.15, 0.25])
    CASES.append((f"fuzz_{_k:02d}", "Random combination of capacity, conversions, openings, tests, reserve, Polish cap, share qualified (seeded)", _e, {}))

TOL = 0.02  # absolute tolerance on hires / counts; relative 1e-6 on money


def close(a, b, rel=1e-6, abs_=TOL):
    a = a or 0; b = b or 0
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return False
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def apply_edits(path, edits):
    wb = load_workbook(path)
    A = wb["Assumptions"]
    idx = {A.cell(r, 1).value: r for r in range(1, A.max_row + 1) if A.cell(r, 1).value}
    for k, v in edits.items():
        if isinstance(k, tuple):
            A[f"{k[1]}{idx[k[0]]}"].value = v
        else:
            A[f"D{idx[k]}"].value = v
    wb.save(path)


def recalc(path):
    r = subprocess.run(["python3", RECALC, path, "120"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "recalc_failed", "stdout": r.stdout[-500:], "stderr": r.stderr[-500:]}


def run_case(name, desc, edits, expect, tmpdir):
    path = os.path.join(tmpdir, f"{name}.xlsx")
    shutil.copy(MODEL, path)
    apply_edits(path, edits)
    rc = recalc(path)
    checks = []
    def chk(label, ok, detail=""):
        checks.append(dict(check=label, ok=bool(ok), detail=detail))
    chk("recalculates with 0 formula errors", rc.get("status") == "success" and rc.get("total_errors", 1) == 0,
        json.dumps(rc.get("error_summary", rc))[:300])
    if rc.get("status") not in ("success", "errors_found"):
        return dict(name=name, desc=desc, checks=checks)
    wb = load_workbook(path, data_only=True)
    Bg, F, C, Wk, I, T = (wb[n] for n in ["Budget", "Funnel", "Channels", "Weekly", "Initiatives", "Tracker"])
    o = oracle.compute(path)

    # ---- model's own tie-out flags
    exp_bg = expect.get("budget_ok", True)
    chk(f"Budget flag is {'✓' if exp_bg else '✗ (expected for invalid input)'}", str(Bg["B40"].value).startswith("✓") == exp_bg, str(Bg["B40"].value))
    exp_mx = expect.get("matrix_ok", True)
    chk(f"Weekly matrix flag is {'✓' if exp_mx else '✗ (expected for invalid input)'}", str(Wk["B55"].value).startswith("✓") == exp_mx, str(Wk["B55"].value))
    if "flag_contains" in expect:
        chk("Weekly flag explains the problem", expect["flag_contains"] in str(Wk["S15"].value), str(Wk["S15"].value))
    wk_ok = str(Wk["S15"].value).startswith("✓")
    exp_wk = expect.get("weekly_ok", True)
    chk(f"Weekly tie-out flag is {'✓' if exp_wk else '✗ (expected for invalid input)'}", wk_ok == exp_wk, str(Wk["S15"].value))

    # ---- oracle comparisons
    cmpv = [
        ("planned spend", Bg["C9"].value, o["planned"], 1e-6, 0.5),
        ("reserve", Bg["C10"].value, o["reserve"], 1e-6, 0.5),
        ("recommended budget", Bg["C12"].value, o["rec"], 1e-9, 0.5),
        ("expected hires (capacity-capped)", Bg["C13"].value, o["hires"], 1e-6, TOL),
        ("assessment slots", F["B22"].value, o["slots"], 1e-6, TOL),
        ("qualified applicants", F["B23"].value, o["qual"], 1e-6, TOL),
        ("applications", F["M9"].value, o["apps"], 1e-6, 0.5),
        ("max hires within capacity", F["B26"].value, o["max_cap_hires"], 1e-6, TOL),
        ("test tranches total", Bg["C8"].value, o["tests_total"], 1e-6, 0.5),
    ]
    for i, r in enumerate(ROLES):
        cmpv.append((f"hires: {r}", Bg[f"G{21+i}"].value, o["hires_by_role"][r], 1e-6, TOL))
        cmpv.append((f"spend: {r}", Bg[f"F{21+i}"].value, o["spend_by_role"][r], 1e-6, 0.5))
    for j, s in enumerate(o["scen"]):
        col = "DEFG"
        cmpv.append((f"scenario {s['level']:.0%}: total hires", Bg[f"H{45+j}"].value, s["total"], 1e-6, TOL))
        for i, r in enumerate(ROLES):
            cmpv.append((f"scenario {s['level']:.0%}: {r}", Bg[f"{col[i]}{45+j}"].value, s["by_role"][r], 1e-6, TOL))
    for j, v in enumerate(o["sens"]):
        cmpv.append((f"sensitivity row {42+j}: hires possible", F[f"D{42+j}"].value, v, 1e-6, TOL))
    for j, t in enumerate(o["tests"]):
        r_ = 53 + j
        cmpv.append((f"initiative test {j+1}: planned qualified", I[f"E{r_}"].value, t["planq"], 1e-6, TOL))
        cmpv.append((f"initiative test {j+1}: budget", I[f"D{r_}"].value, t["budget"], 1e-6, 0.5))
        cmpv.append((f"initiative test {j+1}: pass bar", I[f"G{r_}"].value, t["passq"], 0, 0))
        cmpv.append((f"initiative test {j+1}: kill bar", I[f"I{r_}"].value, t["killq"], 0, 0))
        if "passcpq" in t:
            cmpv.append((f"initiative test {j+1}: pass cost/qualified", I[f"H{r_}"].value, t["passcpq"], 0, 0))
            cmpv.append((f"initiative test {j+1}: kill cost/qualified", I[f"J{r_}"].value, t["killcpq"], 0, 0))
    bad = [f"{lab}: model {mv!r} vs oracle {ov!r}" for lab, mv, ov, rel, ab in cmpv if not close(mv, ov, rel, ab)]
    chk(f"matches independent oracle ({len(cmpv)} outputs)", not bad, "; ".join(bad[:6]))

    # ---- invariants
    overlap = [j + 1 for j, r_ in enumerate((53, 54, 55))
               if isinstance(I[f"G{r_}"].value, (int, float)) and isinstance(I[f"I{r_}"].value, (int, float)) and I[f"I{r_}"].value > I[f"G{r_}"].value]
    overlap += [j + 1 for j, r_ in enumerate((54, 55))
                if isinstance(I[f"H{r_}"].value, (int, float)) and isinstance(I[f"J{r_}"].value, (int, float)) and I[f"J{r_}"].value < I[f"H{r_}"].value]
    chk("initiative kill bars never overlap pass bars", not overlap, str(overlap))
    U = {r: sum((C.cell(rr, 21).value or 0) for rr in range(5, 35) if C.cell(rr, 3).value == r) for r in ROLES}
    opn = o["openings"]
    over = [r for r in ROLES if U[r] > max(opn[r], 0) + 1e-6]
    chk("hires never exceed openings (strict, test hires included)", not over, str(over))
    zero = [r for r in ROLES if opn[r] == 0 and U[r] > 1e-9]
    chk("roles with no openings get no hires and no tests", not zero, str(zero))
    short_ok = all(close(C.cell(39 + i, 5).value, max(0, opn[r] - U[r]) if opn[r] - U[r] > 0.05 else 0) for i, r in enumerate(ROLES))
    chk("shortfall column = openings − planned hires", short_ok)
    neg = [f"{C.cell(rr,1).value}:{C.cell(4,c).value}" for rr in range(5, 35) for c in (21, 22, 23, 24, 25, 27)
           if isinstance(C.cell(rr, c).value, (int, float)) and C.cell(rr, c).value < -1e-9]
    chk("no negative hires, applications or spend", not neg, str(neg[:5]))
    pl = sum((C.cell(rr, 21).value or 0) for rr in range(5, 35) if C.cell(rr, 1).value == "I3-M")
    pcap = oracle.read_inputs(path)[0]["G4"] * opn["Mechatronics"]
    chk("Polish hires ≤ 40%-rule cap", pl <= pcap + 1e-9, f"{pl} vs cap {pcap}")
    c13 = Bg["C13"].value or 0
    chk("expected hires ≤ plan hires and ≤ capacity limit", c13 <= o["hires_plan"] + 1e-6 and c13 <= (F["B26"].value or 0) + 1e-6)
    if exp_wk:
        chk("weekly signatures total = expected hires", close(Wk["V15"].value, c13))
    tot = [Bg[f"H{45+j}"].value or 0 for j in range(4)]
    lv = [Bg[f"B{45+j}"].value or 0 for j in range(4)]
    order = sorted(range(4), key=lambda j: -lv[j])
    mono = all(tot[order[k]] >= tot[order[k + 1]] - 1e-6 for k in range(3))
    SOFF = 53  # scenario engine sits under Budget (old Scenarios row r -> Budget row r+53)
    factors = [Bg.cell(47 + SOFF, c).value if isinstance(Bg.cell(47 + SOFF, c).value, (int, float)) else 1.0 for c in range(6, 10)]
    if all(isinstance(f_, (int, float)) and f_ >= 0.9999 for f_ in factors):
        chk("scenario hires never rise when the budget falls (capacity not binding)", mono, str(list(zip(lv, tot))))
    else:
        # capacity binds: hires may rise as low-conversion sources are cut; check the cap instead
        qrow = [Bg.cell(46 + SOFF, c).value or 0 for c in range(6, 10)]
        slots = F["B22"].value or 0
        capped = all(f_ <= 1 + 1e-9 and (q_ * f_ <= slots + 1e-6) for f_, q_ in zip(factors, qrow))
        chk("scenarios never assess more qualified than there are slots (capacity binding)", capped, str(list(zip(qrow, factors))))
    if exp_bg:
        chk("scenario at 100% budget = expected hires (capacity-capped)", close(Bg["H45"].value, c13), f"{Bg['H45'].value} vs {c13}")
    trk = T["N44"].value or 0
    chk("Tracker forecast with no actuals = planned hires", close(trk, sum(min(opn[r], U[r]) for r in ROLES)), f"{trk} vs {sum(min(opn[r], U[r]) for r in ROLES)}")
    return dict(name=name, desc=desc, checks=checks)


def main():
    tmpdir = tempfile.mkdtemp(prefix="uptime_tests_")
    results = []
    for name, desc, edits, expect in CASES:
        if ONLY and name not in ONLY:
            continue
        res = run_case(name, desc, edits, expect, tmpdir)
        n_ok = sum(c["ok"] for c in res["checks"]); n = len(res["checks"])
        res["passed"] = n_ok == n
        print(f"{'PASS' if res['passed'] else 'FAIL'}  {name:24s} {n_ok}/{n}")
        for c in res["checks"]:
            if not c["ok"]:
                print(f"      ✗ {c['check']}: {c['detail'][:400]}")
        results.append(res)
    passed = sum(r["passed"] for r in results)
    checks = sum(len(r["checks"]) for r in results); ok = sum(c["ok"] for r in results for c in r["checks"])
    print(f"\nCASES {passed}/{len(results)} passed · CHECKS {ok}/{checks} passed")
    if ONLY is None:  # partial runs must not overwrite the full results file
        json.dump(results, open(os.path.join(HERE, "test_results.json"), "w"), indent=1, default=str)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
