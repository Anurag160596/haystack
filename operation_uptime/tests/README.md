# Model test report: Operation_Uptime_Model.xlsx

**Result: 93/93 scenarios passed · 1301/1301 checks passed · deck-vs-model 45/45.**

## How the model is tested

Each scenario copies the model, changes inputs on the Assumptions tab, recalculates in LibreOffice, and checks:
1. **Zero formula errors** across all ~2,800 formulas.
2. **The model's own tie-out flags**: budget, weekly plan and channel × week matrix. For invalid inputs the test expects the flag to fire and to name the problem.
3. **Invariants**:
   - hires never exceed openings
   - shortfall = openings − hires
   - no negative hires, applications or spend
   - Polish hires ≤ the 40% cap
   - expected hires ≤ plan and ≤ the capacity limit
   - weekly signatures = expected hires
   - scenario hires never rise when the budget falls
   - the 100% scenario = the plan
   - with no actuals, the Tracker forecasts the plan
4. **Agreement with an independent oracle** (`oracle.py`): a separate plain-Python re-implementation that reads the same inputs and recomputes 59 outputs. These cover spend, reserve, budget, hires by role, slots, qualified, applications, the four budget scenarios by role, the six sensitivity cases and the three initiative test bars.

`test_deck.py` checks that 45 headline figures on the slides equal the model's values. A negative test against a deliberately altered model fails 17 of them, so the check is real.

## Bugs the tests found (all fixed)

- **Budget-cut scenarios under-cut in rare cases.** A text criterion (`">"&key`) truncated the number to 15 digits, so a row could count itself as more expensive than itself. Found by a random scenario. All rank and cut comparisons now use exact SUMPRODUCT.
- **A StepStone ad with 0 applications per ad divided by zero**, and the error cascaded through 338 cells. Now guarded.
- **The Tracker's 'no actuals' forecast scaled from openings instead of planned hires**, overstating it when channels can't cover the openings (270 vs 126). Fixed.
- **Supervisor referral bonuses in weeks 10–11 fell outside the 9-week cash matrix.** The matrix now covers all 11 weeks.
- **Divide-by-zero guards added** for zero capacity, zero openings, zero conversion, an empty ATS, rejected initiatives and deadlines before the campaign.
- **Infeasible inputs now produce explicit flags**, e.g. 'supervisors cannot apply in time' and 'shares must sum to 100%'.

## Named scenarios

| Scenario | What it tests | Checks |
|---|---|---|
| `base` | Recommended plan as delivered | ✅ 14/14 |
| `capacity_45` | Client can only assess 45/week (binding) | ✅ 14/14 |
| `capacity_100` | Client can assess 100/week (slack) | ✅ 14/14 |
| `capacity_0` | No recruiter capacity at all | ✅ 14/14 |
| `elec_pass_40` | Electrician assessment pass rate 40% | ✅ 14/14 |
| `elec_accept_0` | No electrician ever accepts (conversion = 0) | ✅ 14/14 |
| `all_accept_100` | Every offer accepted | ✅ 14/14 |
| `elec_open_0` | Electrician openings = 0 | ✅ 14/14 |
| `elec_open_200` | Electrician openings = 200 (channels can't cover) | ✅ 14/14 |
| `all_open_0` | All openings = 0 | ✅ 14/14 |
| `polish_cap_0` | Polish sources not allowed | ✅ 14/14 |
| `polish_cap_100` | Polish sources uncapped | ✅ 14/14 |
| `tests_0` | No test tranches | ✅ 14/14 |
| `tests_5000` | Very large test tranches (€5,000 per cell) | ✅ 14/14 |
| `test_split_0` | All test spend in week 2 | ✅ 14/14 |
| `test_split_1` | All test spend in week 1 | ✅ 14/14 |
| `reserve_0` | No reserve | ✅ 14/14 |
| `reserve_50` | 50% reserve | ✅ 14/14 |
| `cut_0` | Budget-cut scenario 0% | ✅ 14/14 |
| `cut_100` | Budget-cut scenario 100% (no money) | ✅ 14/14 |
| `i2_rejected` | Client rejects construction electricians (I2 share qualified 0) | ✅ 14/14 |
| `apply_rate_0` | Programmatic electricians apply rate 0 and StepStone electricians 0 apps/ad | ✅ 14/14 |
| `max_apps_0` | LinkedIn automation has no volume | ✅ 14/14 |
| `free_channel` | Programmatic mechatronics costs nothing | ✅ 14/14 |
| `q_100` | Programmatic electricians 100% qualified | ✅ 14/14 |
| `no_rediscovery` | ATS export empty and no referrals | ✅ 14/14 |
| `deadline_1nov` | Last signing date 1 Nov (window closes before it opens) | ✅ 13/13 |
| `deadline_23dec` | Last signing date 23 Dec | ✅ 14/14 |
| `supervisors_impossible` | Supervisor extra round 60 days: no supervisor can sign in time | ✅ 14/14 |
| `weights_bad` | Weekly spend shares sum to 131% | ✅ 14/14 |
| `i1_waves_bad` | Rediscovery wave shares sum to 90% | ✅ 14/14 |
| `round_step_1` | Recommended budget not rounded | ✅ 14/14 |
| `combo_stress` | Capacity 45 + electrician pass 40% + 30% cut + I2 rejected | ✅ 14/14 |

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

Result: 60/60 passed, 840/840 checks.

## Re-running

```
python3 tests/run_tests.py            # all scenarios (≈5 min)
python3 tests/run_tests.py --only base,capacity_45
python3 tests/test_deck.py             # deck vs model
```
