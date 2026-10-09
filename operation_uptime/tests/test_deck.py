"""Checks that every headline figure on the deck equals the model's value.

Usage: python3 test_deck.py [model.xlsx] [deck.pptx]
"""
import sys, os, subprocess
from openpyxl import load_workbook
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "Operation_Uptime_Model.xlsx")
DECK = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "Operation_Uptime_Deck.pptx")
text = subprocess.run(["markitdown", DECK], capture_output=True, text=True).stdout
slides = text.split("<!-- Slide number:")
wb = load_workbook(MODEL, data_only=True)
B, F, I = wb["Budget"], wb["Funnel"], wb["Initiatives"]
k = lambda v, d=1: "€" + f"{v/1000:.{d}f}k"
e0 = lambda v: "€" + f"{round(v):,}"
n0 = lambda v: f"{round(v):,}"
R = ["Electricians", "Mechatronics", "Automation", "Supervisors"]
checks = [
 ("slide count = 8", len(slides) - 1 == 8),
 ("Part 5 summary is slide 1", "PART 5" in slides[1].upper()),
 ("recommended budget", k(B["C12"].value) in slides[1]),
 ("planned spend", k(B["C9"].value) in slides[1]),
 ("reserve", k(B["C12"].value - B["C9"].value) in slides[1]),
 ("media cost per hire", e0(B["C14"].value) in slides[1]),
 ("all-in cost per hire", e0(B["C15"].value) in slides[1]),
 ("slot utilisation", f"{round(F['B24'].value*100)}%" in slides[1]),
 ("assessment slots", n0(F["B22"].value) in slides[1] and n0(F["B22"].value) in slides[2]),
 ("qualified in plan", n0(F["B23"].value) in slides[2]),
 ("applications in plan", n0(F["M9"].value) in slides[2]),
 ("last useful application E/M/A", F["B19"].value.strftime("%d %b").lstrip("0") in slides[1] or F["B19"].value.strftime("%d %b") in slides[1]),
 ("30%-cut hires", f"~{round(B['H46'].value)}" in slides[1] and f"~{round(B['H46'].value)}" in slides[6]),
 ("30%-cut budget", k(B["C46"].value, 2) in slides[6]),
 ("sensitivity hires (pass ×0.7)", f"~{round(F['D43'].value)}" in slides[3]),
 ("sensitivity qualified needed", n0(F["B43"].value) in slides[3]),
]
for i, r in enumerate(R):
    checks += [(f"{r}: spend", k(B[f"F{21+i}"].value) in slides[1] and k(B[f"F{21+i}"].value) in slides[5]),
               (f"{r}: cost per hire", e0(B[f"H{21+i}"].value) in slides[1]),
               (f"{r}: qualified needed (Part 1)", n0(F[f"K{5+i}"].value) in slides[2]),
               (f"{r}: applications needed (Part 1)", n0(F[f"L{5+i}"].value) in slides[2])]
for j in range(2):
    checks.append((f"scenario {j}: total hires", f"| {round(B[f'H{45+j}'].value)} |" in slides[6] or f"| **{round(B[f'H{45+j}'].value)}** |" in slides[6]))
for j, r in enumerate((53, 54, 55)):
    checks.append((f"initiative {j+1}: pass bar", f"≥{I[f'G{r}'].value} qualified" in slides[7]))
    checks.append((f"initiative {j+1}: kill bar", f"<{I[f'I{r}'].value}" in slides[7]))
    checks.append((f"initiative {j+1}: test window", I[f"B{r}"].value.split(" (")[0] in slides[7]))
ok = sum(c[1] for c in checks)
for name, passed in checks:
    if not passed:
        print("FAIL", name)
print(f"DECK CHECKS {ok}/{len(checks)} passed")
sys.exit(0 if ok == len(checks) else 1)
