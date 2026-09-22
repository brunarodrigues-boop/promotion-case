"""Re-derive every figure on the page by a second route and compare.

The point is not to re-run the same code and get the same answer — that proves
nothing. Each check here recomputes the number a different way (a different
aggregation, a different query, a raw recount) and fails loudly if the two
disagree. A figure that only one code path can produce is a figure nobody has
checked.

Run: python3 audit.py
"""
import collections
import json
import os
import re
import statistics
import subprocess
import sys

PROMO = "/tmp/promo"
RAW = os.path.expanduser("~/Desktop/dri-workload/tickets_raw.json")
CACHE = os.path.expanduser("~/Desktop/timeback-trackers/alpha_app_accuracy_cache.json")
DASH = os.path.expanduser("~/Desktop/alpha-academic-dashboard")

PASS, FAIL = [], []


def check(name, got, want, tol=0):
    ok = (abs(got - want) <= tol) if isinstance(got, (int, float)) and \
         isinstance(want, (int, float)) else (got == want)
    (PASS if ok else FAIL).append((name, got, want))
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} recomputed={got!s:<14} stored={want}")


def sql(q):
    r = subprocess.run(["npx", "-y", "@insforge/cli", "db", "query", q],
                       cwd=DASH, capture_output=True, text=True, timeout=180)
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        raise SystemExit(f"query failed: {r.stdout[-400:]}")
    return json.loads(m.group(0))


print("\n=== 1 · ACCURACY (recount straight from the per-student cache) ===")
acc = json.load(open(f"{PROMO}/accuracy.json"))
recs = json.load(open(CACHE))
have = [r for r in recs if r.get("per")]
c = sum(v[0] for r in have for v in r["per"].values())
t = sum(v[1] for r in have for v in r["per"].values())
check("answered questions", t, acc["overall"]["answered"])
check("correct answers", c, acc["overall"]["correct"])
check("pooled accuracy %", round(100 * c / t, 1), acc["overall"]["pooled_acc"])
check("students with activity", len(have), acc["overall"]["students"])
check("roster size", len(recs), acc["overall"]["roster"])
check("distinct apps", len({k.split("||")[1] for r in have for k in r["per"]}),
      acc["overall"]["n_apps"])
check("distinct subjects", len({k.split("||")[0] for r in have for k in r["per"]}),
      acc["overall"]["n_subjects"])
# the by-app table must add back up to the whole
check("by_app answered sums to total", sum(d["answered"] for d in acc["by_app"]), t)
check("by_subject answered sums to total",
      sum(d["answered"] for d in acc["by_subject"]), t)
# a grade total is a different slice and must also reconcile
check("by_grade answered sums to total",
      sum(d["answered"] for d in acc["by_grade"]), t)
# every percentage must be derivable from its own correct/answered
bad = [d["key"] for d in acc["by_app"]
       if abs(round(100 * d["correct"] / d["answered"], 1) - d["acc"]) > 0.05]
check("every by_app % matches its own counts", len(bad), 0)

print("\n=== 2 · INTERVENTIONS (re-queried from the source, different shape) ===")
iv = json.load(open(f"{PROMO}/interventions.json"))
q = sql("""select json_build_object(
 'campus_rows',(select count(*) from intervention_requests where section='campus_dri'),
 'campus_students',(select count(distinct email) from intervention_requests where section='campus_dri'),
 'campus_cases',(select count(*) from (select email,subject,grade from intervention_requests where section='campus_dri' group by 1,2,3) a),
 'completed',(select count(*) from intervention_requests where section='campus_dri' and completed),
 'curric_rows',(select count(*) from intervention_requests where section='subject_dri'),
 'all_rows',(select count(*) from intervention_requests),
 'median_h',(select round((percentile_cont(0.5) within group (order by (extract(epoch from completed_at)-extract(epoch from created_at))/3600.0))::numeric,1)
             from intervention_requests where section='campus_dri' and completed and completed_at>=created_at),
 'own_min',(select sum(minutes_spent) from intervention_requests where section='campus_dri' and entry_kind='manual_work' and minutes_spent>0),
 'ans_min',(select sum(completion_minutes) from intervention_requests where completion_minutes>0)
)::text""")
check("campus touches", q["campus_rows"], iv["campus"]["touches"])
check("campus distinct students", q["campus_students"], iv["campus"]["students"])
check("campus folded cases", q["campus_cases"], iv["campus"]["cases"])
check("campus completed", q["completed"], iv["campus"]["completed"])
check("curriculum touches", q["curric_rows"], iv["curriculum"]["touches"])
check("median turnaround h", float(q["median_h"]), iv["turnaround"]["median_h"], 0.05)
check("campus own effort h", round(q["own_min"] / 60, 1), iv["effort"]["campus_own_h"], 0.05)
check("curriculum answer effort h", round(q["ans_min"] / 60, 1),
      iv["effort"]["curriculum_answer_h"], 0.05)
# the two logs must partition the table exactly — proof they are disjoint
check("the two logs partition the table",
      q["campus_rows"] + q["curric_rows"], q["all_rows"])

print("\n=== 3 · THE STORE'S OWN CONSTRAINTS (should be zero) ===")
v = sql("""select json_build_object(
 'cm_outside_requests',(select count(*) from intervention_requests where completion_minutes is not null and not (section='campus_dri' and entry_kind='intervention_request')),
 'ms_on_requests',(select count(*) from intervention_requests where minutes_spent is not null and section='campus_dri' and entry_kind='intervention_request'),
 'negative_turnaround',(select count(*) from intervention_requests where section='campus_dri' and completed and completed_at<created_at),
 'completed_without_ts',(select count(*) from intervention_requests where completed and completed_at is null)
)::text""")
for k, n in v.items():
    check(f"violations: {k}", n, 0)

print("\n=== 4 · HELPDESK (recount from the raw pull) ===")
tk = json.load(open(f"{PROMO}/tickets2.json"))
raw = json.load(open(RAW))
check("alpha cases", len(raw["cases"]), tk["alpha_total"])
check("category counts sum to total", sum(s["n"] for s in tk["categories"].values()),
      tk["alpha_total"])
check("group counts sum to total", sum(s["n"] for s in tk["groups"].values()),
      tk["alpha_total"])
uncl = (tk["categories"]["No signal in the subject"]["n"]
        + tk["categories"]["Topic named, ask unclear"]["n"])
check("coverage %", round(100 * (tk["alpha_total"] - uncl) / tk["alpha_total"], 1),
      tk["coverage_pct"], 0.05)
# the pull must not have hit its own cap again
inst = raw.get("scanned", 0)
check("pull did not stop on a round cap", inst % 5000 != 0 or inst == 0, True)
# a ticket may hold exactly one category
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify_tickets as CT                                        # noqa: E402
seen = collections.Counter()
for case in raw["cases"]:
    g, cat, _ = CT.classify(CT.normalise(case.get("subject", ""), case.get("preview", "")))
    seen[cat] += 1
check("independent re-classification matches",
      sum(seen.values()), tk["alpha_total"])
mismatch = [k for k in seen if seen[k] != tk["categories"][k]["n"]]
check("every category count reproduces", len(mismatch), 0)

print("\n=== 5 · REPOSITORY FIGURES ===")


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                          text=True, timeout=90).stdout.strip()


tb = os.path.expanduser("~/Desktop/TimeBack")
shortlog = 0
for line in sh("git shortlog -sn --all", tb).splitlines():
    n, _, who = line.strip().partition("\t")
    if who.strip().lower() in ("bruna rodrigues", "brunar999", "brunarodrigues-boop"):
        shortlog += int(n)
logcount = len([1 for l in sh("git log --all --format=%an", tb).splitlines()
                if l.strip().lower() in ("bruna rodrigues", "brunar999", "brunarodrigues-boop")])
check("my commits: shortlog vs log agree", shortlog, logcount)

print("\n" + "=" * 78)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for name, got, want in FAIL:
    print(f"   FAIL  {name}: recomputed {got}, stored {want}")
sys.exit(1 if FAIL else 0)
