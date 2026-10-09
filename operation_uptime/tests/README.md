# Model test report: Operation_Uptime_Model.xlsx

**Result: 153/153 scenarios, 2436/2436 checks · every input moved one at a time: 183/183 inputs, 2970/2970 checks · Tracker rules live: 17/17 · deck-vs-model 45/45.**

## How the model is tested

Each scenario copies the model, changes inputs on the Assumptions tab, recalculates in LibreOffice, and checks:
1. **Zero formula errors** across all ~3,000 formulas.
2. **The model's own tie-out flags**: budget, weekly plan and channel × week matrix. For invalid inputs the test expects the flag to fire and to name the problem.
3. **Invariants**:
   - hires never exceed openings (strict, including test hires)
   - roles with no openings get no hires
   - shortfall = openings − hires
   - no negative hires, applications or spend
   - Polish hires ≤ the 40% cap
   - expected hires ≤ plan and ≤ the capacity limit
   - weekly signatures = expected hires
   - when capacity doesn't bind, scenario hires never rise as the budget falls
   - when capacity binds, scenarios never assess more qualified applicants than there are slots
   - the 100% scenario = expected hires
   - with no actuals, the Tracker forecasts the plan
   - initiative kill bars never overlap pass bars
4. **Agreement with an independent oracle** (`oracle.py`): a separate plain-Python re-implementation that reads the same inputs and recomputes 59 outputs. These cover spend, reserve, budget, hires by role, slots, qualified, applications, the four budget scenarios by role, the six sensitivity cases and the three initiative test bars.

`test_deck.py` checks that 45 headline figures on the slides equal the model's values. A negative test against a deliberately altered model fails 17 of them, so the check is real.

## Every input, one at a time (`test_every_input.py`)

Each of the 183 inputs (every Assumptions value and every typed channel value) is moved on its own. The 35 derived cells (channel qualified shares and caps, rediscovery and referral volumes, I2/I3 sizes) are live formulas on the evidence inputs in Assumptions §6a, so moving those inputs moves them:
- counts, costs and volumes up 20%, shares down 20%, day inputs +1 day, dates shifted by a few days;
- weekly and rediscovery shares (which must sum to 100%) move 2 points to a neighbouring week.

Each time the model recalculates and must pass the full check set above: zero formula errors, tie-out flags, invariants and the 59-output oracle. A fired flag is accepted only when it names the problem. Where the economic direction is known, the headline must move the right way. Examples: more openings → more spend; lower pass rate → more qualified needed; dearer channel → plan never cheaper; longer lags → never more slots. The report also records how many output cells each input moves.

Inputs that change nothing at the base plan, and why:
- **G2 (campaign end):** not binding, because the 18 Dec signing date (T1) comes first.
- **G9 (recognition time):** information only.
- **R1–R13, F3 and F4:** Tracker rules and flag thresholds (F1 and F2 move a pool read-out at base).
- **SSW (days per StepStone ad):** 30 → 36 days still gives 2 ads for the 36-day window, so nothing changes.
- **TK1 (kill significance level):** moving 1% to 0.8% does not cross a Poisson quantile, so the kill bars stay the same. The bars change when the level crosses a quantile (the test cases with other levels cover this). These act only once actuals exist or a threshold is crossed; see below.

## Tracker rules live (`test_tracker_rules.py`)

A realistic week of actuals is typed into the Tracker: ten channel cells (one clear performer, one dud) and role-level interview, offer and signing results. Each rule R1–R13 and threshold F1–F4 is then moved, and the test confirms that a decision, re-forecast or flag changes. Example: raising R6 from €750 to €1,500 turns the Polish corridor (€900 spent, 0 qualified, ≥3 expected) from SWITCH OFF to HOLD. R13 is tested with slack capacity, because a week that is already 'Full' (F4) cannot also be under-paced.

## Robustness features

- **Input validation, two layers.** Excel data-validation rules reject out-of-range entries when typed: shares 0–100%, counts and costs ≥ 0, reserve 0–99%, dates inside the campaign. Summary C19 re-checks every numeric input by formula; the list is generated automatically, so no input can be missed. It also catches pasted values. Any invalid input turns the Budget and Weekly tie-out flags to '✗ invalid input: …'.
- **Test hires can never exceed openings.** Each role's €750 tests are capped so their expected hires stay within its openings.
- **Weekly spend can never fall after the cut-off.** Shares typed into weeks that start after the last useful application are re-spread over the earlier weeks, for both E/M/A and supervisors, and Weekly S15 says how much was moved. Changing a date or lag therefore never strands spend. Explicit flags remain for impossible schedules: no week before the cut-off, assessments starting after the last assessment day, or supervisors unable to sign in time.
- **Whole days only** for the lag inputs (T0, T2–T6), by Excel validation and by the Summary C19 input check.
- **Initiative test bars can't contradict each other.** Kill bars are capped at the pass bars, and the input check requires kill thresholds below pass thresholds.
- **Summary C20 shows the plan/schedule check**, so impossible schedules are visible on the front tab.
- **Costs are clamped at zero**, so a negative typo can't create negative spend.
- **Divide-by-zero guards everywhere** a denominator can be zero: capacity, openings, conversion, apply rates, empty ATS, rounding step.
- **Live Summary labels**: the hardest role is recomputed from channel coverage, and the capacity label follows the input.

## Independent reviewers' edge cases

Four independent review passes wrote 60+ edge cases of their own. Re-run against the current model, all pass, except cases whose expected result was written before a fix the reviewer requested. For example, a 100% reserve and negative openings are now correctly flagged as invalid input.

## Every input sourced or derived

Each of the 134 inputs carries a linked benchmark, a written derivation or a statistical convention on the Assumptions tab. Checking the old values against the research corrected several of them:
- **Qualified share by role:** IAB's measured 25% for production occupations and 23% for specialists (was 10–22% judgement).
- **Channel quality:** the IAB decisive ÷ used index.
- **Channel volume caps:** Trendence reach × the in-market pool (BA employment × Gallup's 11% actively searching).
- **Rediscovery pool:** 700 → 211, because consented applicant data is kept for at most about a year. BA data puts maintenance trades at 7.8% of production occupations.
- **Polish language pass:** Eurostat, 22% → 14%.
- **Relocators:** Destatis and IAB mobility rates.
- **Initiative test bars:** Poisson quantiles at the 5% and 1% significance levels.
- **Scale-up trigger:** a one-sided 95% test.
- **Capacity flags:** Bagust et al., BMJ 1999 (verified on PubMed): risk above 85% use, regular shortages at 90%.

The recommended budget moved from €102.5k to €117.5k as a result.

## Bugs the tests found (all fixed)

- **Moving a date or lag by one day stranded the week-6 spend.** Found by the one-at-a-time sweep: week 6 starts on the cut-off day, so a one-day shift left 25% of spend after the last useful application, and its hires were lost. Shares are now re-spread automatically (see above).
- **Fractional days were accepted** (e.g. 6.4 days), which the dates then carried silently. Found by the sweep; day inputs are now whole days only.

- **Budget-cut scenarios under-cut in rare cases.** A text criterion (`">"&key`) truncated the number to 15 digits, so a row could count itself as more expensive than itself. Found by a random scenario. All rank and cut comparisons now use exact SUMPRODUCT.
- **A StepStone ad with 0 applications per ad divided by zero**, and the error cascaded through 338 cells. Now guarded.
- **The Tracker's 'no actuals' forecast scaled from openings instead of planned hires**, overstating it when channels can't cover the openings (270 vs 126). Fixed.
- **Supervisor referral bonuses in weeks 10–11 fell outside the 9-week cash matrix.** The matrix now covers all 11 weeks.
- **Divide-by-zero guards added** for zero capacity, zero openings, zero conversion, an empty ATS, rejected initiatives and deadlines before the campaign.
- **Budget-cut scenarios ignored the capacity cap.** Found by an independent reviewer's own edge cases. Scenario hires are now scaled by assessment slots ÷ qualified, the same rule as Budget C13.
- **A reserve share of 100% or more was accepted silently.** It is now flagged in Budget B40 and Weekly S15.
- **Test tranches ran for roles with zero openings.** Tests now run only where a role has openings.
- **Edge-case divisions by zero:** all-zero openings in the total rows, and a rounding step of 0. Both guarded.
- **Infeasible inputs now produce explicit flags**, e.g. 'supervisors cannot apply in time', 'no spend share falls before the supervisor cut-off' and 'shares must sum to 100%'.

## Named scenarios

| Scenario | What it tests | Checks |
|---|---|---|
| `base` | Recommended plan as delivered | ✅ 16/16 |
| `capacity_45` | Client can only assess 45/week (binding) | ✅ 16/16 |
| `capacity_100` | Client can assess 100/week (slack) | ✅ 16/16 |
| `capacity_0` | No recruiter capacity at all | ✅ 16/16 |
| `elec_pass_40` | Electrician assessment pass rate 40% | ✅ 16/16 |
| `elec_accept_0` | No electrician ever accepts (conversion = 0) | ✅ 16/16 |
| `all_accept_100` | Every offer accepted | ✅ 16/16 |
| `elec_open_0` | Electrician openings = 0 | ✅ 16/16 |
| `elec_open_200` | Electrician openings = 200 (channels can't cover) | ✅ 16/16 |
| `all_open_0` | All openings = 0 | ✅ 16/16 |
| `polish_cap_0` | Polish sources not allowed | ✅ 16/16 |
| `polish_cap_100` | Polish sources uncapped | ✅ 16/16 |
| `tests_0` | No test tranches | ✅ 16/16 |
| `tests_5000` | Very large test tranches (€5,000 per cell) | ✅ 16/16 |
| `test_split_0` | All test spend in week 2 | ✅ 16/16 |
| `test_split_1` | All test spend in week 1 | ✅ 16/16 |
| `reserve_0` | No reserve | ✅ 16/16 |
| `reserve_50` | 50% reserve | ✅ 16/16 |
| `cut_0` | Budget-cut scenario 0% | ✅ 16/16 |
| `cut_100` | Budget-cut scenario 100% (no money) | ✅ 16/16 |
| `i2_rejected` | Client rejects construction electricians (I2 share qualified 0) | ✅ 16/16 |
| `apply_rate_0` | Programmatic electricians apply rate 0 and StepStone electricians 0 apps/ad | ✅ 16/16 |
| `max_apps_0` | LinkedIn automation has no volume | ✅ 16/16 |
| `free_channel` | Programmatic mechatronics costs nothing | ✅ 16/16 |
| `q_100` | Programmatic electricians 100% qualified | ✅ 16/16 |
| `no_rediscovery` | ATS export empty and no referrals | ✅ 16/16 |
| `deadline_1nov` | Last signing date 1 Nov (window closes before it opens) | ✅ 15/15 |
| `deadline_23dec` | Last signing date 23 Dec | ✅ 16/16 |
| `supervisors_impossible` | Supervisor extra round 60 days: no supervisor can sign in time | ✅ 16/16 |
| `weights_bad` | Weekly spend shares sum to 131% | ✅ 16/16 |
| `i1_waves_bad` | Rediscovery wave shares sum to 90% | ✅ 16/16 |
| `round_step_1` | Recommended budget not rounded | ✅ 16/16 |
| `capacity_1` | Recruiters can assess 1 qualified applicant a week | ✅ 16/16 |
| `capacity_1000_open3x` | Capacity 1,000/week and 3× the openings | ✅ 16/16 |
| `open_1_each` | 1 opening per role (test hires exceed it) | ✅ 16/16 |
| `mech_open_1` | 1 mechatronics opening (fractional Polish cap) | ✅ 16/16 |
| `q_001_all` | Every channel and initiative 1% qualified | ✅ 16/16 |
| `i3_minutes_0` | Polish pre-screen calls take no time | ✅ 16/16 |
| `t2_0` | Application assessed the same day | ✅ 16/16 |
| `weights_week1` | All regular spend in week 1 | ✅ 16/16 |
| `i1_all_week1` | All rediscovery re-applications in week 1 | ✅ 16/16 |
| `round_100k` | Budget rounded to €100k steps | ✅ 16/16 |
| `automation_no_volume` | Automation: every source has zero volume | ✅ 16/16 |
| `reserve_99` | Reserve 99% of total | ✅ 16/16 |
| `reserve_100` | Reserve 100% (invalid) | ✅ 15/15 |
| `combo_cap45_cut` | Capacity 45 and the budget scenarios | ✅ 16/16 |
| `cap2_cut50` | Capacity 2/week with a 50% budget cut | ✅ 16/16 |
| `elec500_mech0` | 500 electrician openings, no mechatronics openings | ✅ 16/16 |
| `mech_auto_0_g4_40` | Polish cap 40% with no mechatronics or automation openings | ✅ 16/16 |
| `all_apply_1` | Every CPC channel converts 100% of clicks | ✅ 16/16 |
| `i2q_1` | Every construction electrician qualifies | ✅ 16/16 |
| `stepstone_1app` | StepStone ads bring 1 application each | ✅ 16/16 |
| `deadline_first_assess` | Last assessment falls on the first assessment day | ✅ 16/16 |
| `t0_0` | Assessments start on launch day | ✅ 16/16 |
| `b2_1euro` | €1 test tranches | ✅ 16/16 |
| `levels_all_100` | All scenario levels at 100% | ✅ 16/16 |
| `w_all_week6` | All regular spend in week 6 (after the supervisor cut-off) | ✅ 16/16 |
| `open_1000_cap1000` | 1,000 openings per role, capacity 1,000/week | ✅ 16/16 |
| `round_step_0` | Rounding step 0 (no rounding) | ✅ 16/16 |
| `neg_open_elec` | Typo: electrician openings −5 | ✅ 15/15 |
| `rate_above_1` | Typo: electrician pass rate 150% | ✅ 15/15 |
| `channel_q_above_1` | Typo: programmatic electricians 120% qualified | ✅ 15/15 |
| `negative_cost` | Typo: Meta mechatronics cost −€12 per application | ✅ 15/15 |
| `deadline_after_end` | Last signing date after the campaign ends (5 Jan 2027) | ✅ 15/15 |
| `negative_capacity` | Typo: capacity −10/week | ✅ 15/15 |
| `cap3_open1` | Capacity 3/week, 1 opening per role | ✅ 16/16 |
| `pass_all_1` | Everyone qualified passes the assessment | ✅ 16/16 |
| `offer_all_1` | Everyone who passes gets an offer | ✅ 16/16 |
| `q_all_1` | Every channel 100% qualified (test hires must stay ≤ openings) | ✅ 16/16 |
| `b2_100k` | €100,000 test tranches (capped at openings) | ✅ 16/16 |
| `i1c_1` | Every past applicant re-applies | ✅ 16/16 |
| `i1b_0` | No referral bonus | ✅ 16/16 |
| `i2s_0` | No construction electrician applies | ✅ 16/16 |
| `i3x_0` | No Polish applications | ✅ 16/16 |
| `t345_0` | Interview, offer and signature are instant | ✅ 16/16 |
| `t1_31dec` | Last signing date 31 Dec | ✅ 16/16 |
| `w_even_1_6` | Spend split evenly over weeks 1–6 | ✅ 16/16 |
| `b4_half_b2_0` | Test split 50/50 with no tests | ✅ 16/16 |
| `i1a_0` | Initiative-1 conversion adjustment 0 | ✅ 16/16 |
| `i1w_even` | Rediscovery waves 1/3 each | ✅ 16/16 |
| `i3x_negative` | Typo: Polish max applications −100 | ✅ 15/15 |
| `threshold_negative` | Typo: Tracker scale-up threshold −1 | ✅ 15/15 |
| `campaign_end_before_start` | Campaign end before its start | ✅ 15/15 |
| `spend_after_cutoff_wk7` | All regular spend in week 7 (after the 24 Nov cut-off), no supervisors | ✅ 16/16 |
| `spend_partly_late` | 10 pts of weekly spend typed into week 7: re-spread over weeks 1–6, plan still ties | ✅ 16/16 |
| `lags_one_day_longer` | Every lag one day longer (cut-off moves into week 5): week-6 share re-spread | ✅ 16/16 |
| `start_one_day_later` | Campaign starts Wed 21 Oct: week 6 now starts after the cut-off | ✅ 16/16 |
| `spend_after_cutoff_wk11` | All regular spend in week 11, no supervisors | ✅ 16/16 |
| `t0_100` | First assessment 100 days after launch | ✅ 16/16 |
| `fractional_openings` | Fractional openings (2.5 electricians) | ✅ 16/16 |
| `tp_tk_equal` | Initiative pass and kill thresholds both 100% (contradictory) | ✅ 15/15 |
| `tp_tk_close` | Kill threshold just below pass (59% vs 60%) | ✅ 16/16 |
| `combo_stress` | Capacity 45 + electrician pass 40% + 30% cut + I2 rejected | ✅ 16/16 |

## Random scenarios

60 seeded random combinations (seed 20261020) vary these together:
- capacity 30–80/week
- pass and acceptance rates per role
- openings 0–2× the brief
- test size €0–1,500
- reserve 0–30%
- budget cut 0–60%
- Polish cap 0–100%
- share qualified on half the paid cells
- whether the construction-electrician profile is accepted

Result: 60/60 passed, 960/960 checks.

## Re-running

```
python3 tests/run_tests.py            # all scenarios (≈5 min)
python3 tests/run_tests.py --only base,capacity_45
python3 tests/test_deck.py             # deck vs model
```

## Finding worth knowing

When recruiter capacity binds, a smaller budget can produce as many or more hires: the cut removes the most expensive sources, which here also convert worst, freeing slots for better candidates. The model shows this, and Budget B43 notes it: a capacity-bound plan should be re-optimised for hires per assessment slot.
