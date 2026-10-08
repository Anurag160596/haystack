# Model test report: Operation_Uptime_Model.xlsx

**Result: 141/141 scenarios passed · 2107/2107 checks passed · deck-vs-model 45/45.**

## How the model is tested

Each scenario copies the model, changes inputs on the Assumptions tab, recalculates in LibreOffice, and checks:
1. **Zero formula errors** across all ~2,800 formulas.
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
4. **Agreement with an independent oracle** (`oracle.py`): a separate plain-Python re-implementation that reads the same inputs and recomputes 59 outputs. These cover spend, reserve, budget, hires by role, slots, qualified, applications, the four budget scenarios by role, the six sensitivity cases and the three initiative test bars.

`test_deck.py` checks that 45 headline figures on the slides equal the model's values. A negative test against a deliberately altered model fails 17 of them, so the check is real.

## Robustness features

- **Input validation, two layers.** Excel data-validation rules reject out-of-range entries when typed: shares 0–100%, counts and costs ≥ 0, reserve 0–99%, dates inside the campaign. Summary C19 re-checks every input by formula, which also catches pasted values. Any invalid input turns the Budget and Weekly tie-out flags to '✗ invalid input: …'.
- **Test hires can never exceed openings.** Each role's €750 tests are capped so their expected hires stay within its openings.
- **Costs are clamped at zero**, so a negative typo can't create negative spend.
- **Divide-by-zero guards everywhere** a denominator can be zero: capacity, openings, conversion, apply rates, empty ATS, rounding step.
- **Live Summary labels**: the hardest role is recomputed from channel coverage, and the capacity label follows the input.

## Bugs the tests found (all fixed)

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
| `base` | Recommended plan as delivered | ✅ 15/15 |
| `capacity_45` | Client can only assess 45/week (binding) | ✅ 15/15 |
| `capacity_100` | Client can assess 100/week (slack) | ✅ 15/15 |
| `capacity_0` | No recruiter capacity at all | ✅ 15/15 |
| `elec_pass_40` | Electrician assessment pass rate 40% | ✅ 15/15 |
| `elec_accept_0` | No electrician ever accepts (conversion = 0) | ✅ 15/15 |
| `all_accept_100` | Every offer accepted | ✅ 15/15 |
| `elec_open_0` | Electrician openings = 0 | ✅ 15/15 |
| `elec_open_200` | Electrician openings = 200 (channels can't cover) | ✅ 15/15 |
| `all_open_0` | All openings = 0 | ✅ 15/15 |
| `polish_cap_0` | Polish sources not allowed | ✅ 15/15 |
| `polish_cap_100` | Polish sources uncapped | ✅ 15/15 |
| `tests_0` | No test tranches | ✅ 15/15 |
| `tests_5000` | Very large test tranches (€5,000 per cell) | ✅ 15/15 |
| `test_split_0` | All test spend in week 2 | ✅ 15/15 |
| `test_split_1` | All test spend in week 1 | ✅ 15/15 |
| `reserve_0` | No reserve | ✅ 15/15 |
| `reserve_50` | 50% reserve | ✅ 15/15 |
| `cut_0` | Budget-cut scenario 0% | ✅ 15/15 |
| `cut_100` | Budget-cut scenario 100% (no money) | ✅ 15/15 |
| `i2_rejected` | Client rejects construction electricians (I2 share qualified 0) | ✅ 15/15 |
| `apply_rate_0` | Programmatic electricians apply rate 0 and StepStone electricians 0 apps/ad | ✅ 15/15 |
| `max_apps_0` | LinkedIn automation has no volume | ✅ 15/15 |
| `free_channel` | Programmatic mechatronics costs nothing | ✅ 15/15 |
| `q_100` | Programmatic electricians 100% qualified | ✅ 15/15 |
| `no_rediscovery` | ATS export empty and no referrals | ✅ 15/15 |
| `deadline_1nov` | Last signing date 1 Nov (window closes before it opens) | ✅ 14/14 |
| `deadline_23dec` | Last signing date 23 Dec | ✅ 15/15 |
| `supervisors_impossible` | Supervisor extra round 60 days: no supervisor can sign in time | ✅ 15/15 |
| `weights_bad` | Weekly spend shares sum to 131% | ✅ 15/15 |
| `i1_waves_bad` | Rediscovery wave shares sum to 90% | ✅ 15/15 |
| `round_step_1` | Recommended budget not rounded | ✅ 15/15 |
| `capacity_1` | Recruiters can assess 1 qualified applicant a week | ✅ 15/15 |
| `capacity_1000_open3x` | Capacity 1,000/week and 3× the openings | ✅ 15/15 |
| `open_1_each` | 1 opening per role (test hires exceed it) | ✅ 15/15 |
| `mech_open_1` | 1 mechatronics opening (fractional Polish cap) | ✅ 15/15 |
| `q_001_all` | Every channel and initiative 1% qualified | ✅ 15/15 |
| `i3_minutes_0` | Polish pre-screen calls take no time | ✅ 15/15 |
| `t2_0` | Application assessed the same day | ✅ 15/15 |
| `weights_week1` | All regular spend in week 1 | ✅ 15/15 |
| `i1_all_week1` | All rediscovery re-applications in week 1 | ✅ 15/15 |
| `round_100k` | Budget rounded to €100k steps | ✅ 15/15 |
| `automation_no_volume` | Automation: every source has zero volume | ✅ 15/15 |
| `reserve_99` | Reserve 99% of total | ✅ 15/15 |
| `reserve_100` | Reserve 100% (invalid) | ✅ 14/14 |
| `combo_cap45_cut` | Capacity 45 and the budget scenarios | ✅ 15/15 |
| `cap2_cut50` | Capacity 2/week with a 50% budget cut | ✅ 15/15 |
| `elec500_mech0` | 500 electrician openings, no mechatronics openings | ✅ 15/15 |
| `mech_auto_0_g4_40` | Polish cap 40% with no mechatronics or automation openings | ✅ 15/15 |
| `all_apply_1` | Every CPC channel converts 100% of clicks | ✅ 15/15 |
| `i2q_1` | Every construction electrician qualifies | ✅ 15/15 |
| `stepstone_1app` | StepStone ads bring 1 application each | ✅ 15/15 |
| `deadline_first_assess` | Last assessment falls on the first assessment day | ✅ 15/15 |
| `t0_0` | Assessments start on launch day | ✅ 15/15 |
| `b2_1euro` | €1 test tranches | ✅ 15/15 |
| `levels_all_100` | All scenario levels at 100% | ✅ 15/15 |
| `w_all_week6` | All regular spend in week 6 (after the supervisor cut-off) | ✅ 15/15 |
| `open_1000_cap1000` | 1,000 openings per role, capacity 1,000/week | ✅ 15/15 |
| `round_step_0` | Rounding step 0 (no rounding) | ✅ 15/15 |
| `neg_open_elec` | Typo: electrician openings −5 | ✅ 14/14 |
| `rate_above_1` | Typo: electrician pass rate 150% | ✅ 14/14 |
| `channel_q_above_1` | Typo: programmatic electricians 120% qualified | ✅ 14/14 |
| `negative_cost` | Typo: Meta mechatronics cost −€12 per application | ✅ 14/14 |
| `deadline_after_end` | Last signing date after the campaign ends (5 Jan 2027) | ✅ 14/14 |
| `negative_capacity` | Typo: capacity −10/week | ✅ 14/14 |
| `cap3_open1` | Capacity 3/week, 1 opening per role | ✅ 15/15 |
| `pass_all_1` | Everyone qualified passes the assessment | ✅ 15/15 |
| `offer_all_1` | Everyone who passes gets an offer | ✅ 15/15 |
| `q_all_1` | Every channel 100% qualified (test hires must stay ≤ openings) | ✅ 15/15 |
| `b2_100k` | €100,000 test tranches (capped at openings) | ✅ 15/15 |
| `i1c_1` | Every past applicant re-applies | ✅ 15/15 |
| `i1b_0` | No referral bonus | ✅ 15/15 |
| `i2s_0` | No construction electrician applies | ✅ 15/15 |
| `i3x_0` | No Polish applications | ✅ 15/15 |
| `t345_0` | Interview, offer and signature are instant | ✅ 15/15 |
| `t1_31dec` | Last signing date 31 Dec | ✅ 15/15 |
| `w_even_1_6` | Spend split evenly over weeks 1–6 | ✅ 15/15 |
| `b4_half_b2_0` | Test split 50/50 with no tests | ✅ 15/15 |
| `i1a_0` | Initiative-1 conversion adjustment 0 | ✅ 15/15 |
| `i1w_even` | Rediscovery waves 1/3 each | ✅ 15/15 |
| `combo_stress` | Capacity 45 + electrician pass 40% + 30% cut + I2 rejected | ✅ 15/15 |

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

Result: 60/60 passed, 900/900 checks.

## Re-running

```
python3 tests/run_tests.py            # all scenarios (≈5 min)
python3 tests/run_tests.py --only base,capacity_45
python3 tests/test_deck.py             # deck vs model
```

## Finding worth knowing

When recruiter capacity binds, a smaller budget can produce as many or more hires: the cut removes the most expensive sources, which here also convert worst, freeing slots for better candidates. The model shows this, and Budget B43 notes it: a capacity-bound plan should be re-optimised for hires per assessment slot.
