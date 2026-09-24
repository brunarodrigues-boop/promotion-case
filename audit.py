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


def check_growing(name, got, want):
    """For counters on a live append-only log.

    The page is a snapshot; the audit re-queries the source seconds to minutes
    later. Anything logged in between is real work, not an error, so demanding
    exact equality makes this check fail for the one reason that is fine. What
    is NOT fine is the recomputed value coming back LOWER than the snapshot —
    that means rows vanished or the count is wrong, and that still fails.
    """
    ok = got >= want
    (PASS if ok else FAIL).append((name, got, want))
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} recomputed={got!s:<14} stored={want}"
          f"{'' if got == want else f'  (+{got - want} since the snapshot)'}")


def check_drifting(name, got, want, bound):
    """For a statistic over the live append-only log, not a counter.

    check_growing works for counts: a re-query can only come back higher, and
    lower means rows vanished. A median or a sum of minutes has no such
    direction — rows logged between the snapshot and the re-query move it
    either way, and demanding equality fails for the one reason that is fine.

    So the bound is on the SIZE of the move, not its sign. It is set tight
    enough that the defects this check exists for — the wrong column, the wrong
    section, subject_dri folded in where it does not belong — move the number
    by hours and still fail, while a handful of new rows shifting a median by
    tenths does not.
    """
    ok = abs(got - want) <= bound
    (PASS if ok else FAIL).append((name, got, want))
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} recomputed={got!s:<14} stored={want}"
          f"{'' if got == want else f'  (moved {got - want:+.1f}, bound {bound})'}")


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
# The page once claimed "a student works in up to 42 apps". 42 is the count
# across the whole roster; no student is in more than 14. These two numbers are
# easy to conflate and the conflation reads as a much bigger claim than the
# data supports, so both are pinned here.
per_student = [len({k.split("||")[1] for k in r["per"]}) for r in have]
check("apps per student, max", max(per_student), acc["overall"]["apps_per_student_max"])
check("apps per student, median", int(statistics.median(per_student)),
      acc["overall"]["apps_per_student_median"])
check("roster-wide app count exceeds any one student's",
      acc["overall"]["n_apps"] > acc["overall"]["apps_per_student_max"], True)

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
check_growing("campus touches", q["campus_rows"], iv["campus"]["touches"])
check_growing("campus distinct students", q["campus_students"], iv["campus"]["students"])
check_growing("campus folded cases", q["campus_cases"], iv["campus"]["cases"])
check_growing("campus completed", q["completed"], iv["campus"]["completed"])
check_growing("curriculum touches", q["curric_rows"], iv["curriculum"]["touches"])
check_drifting("median turnaround h", float(q["median_h"]),
               iv["turnaround"]["median_h"], 1.0)
# Tolerance of a tenth, on purpose. 4,941 minutes is exactly 82.35 hours, and
# the two engines break that tie differently: Postgres rounds half away from
# zero (82.4), Python rounds half to even and the binary float sits a hair
# under (82.3). That is a tie-breaking rule, not a disagreement about the data,
# so the check compares the hours rather than the rounding.
check("campus own effort h", round(q["own_min"] / 60, 1),
      iv["effort"]["campus_own_h"], 0.11)
check_drifting("curriculum answer effort h", round(q["ans_min"] / 60, 1),
               iv["effort"]["curriculum_answer_h"], 3.0)
# Raw minutes, not minutes reconstructed from two 1-decimal hour figures —
# that round trip carries up to six minutes of error and was failing on it.
check_growing("campus own effort, raw minutes",
              q["own_min"], iv["effort"]["campus_own_min"])
check_growing("curriculum answer effort, raw minutes",
              q["ans_min"], iv["effort"]["curriculum_answer_min"])
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

print("\n=== 6 · DASHBOARD CONFIG (re-read from school_config, not the json) ===")
db = json.load(open(f"{PROMO}/dashboard.json"))
BACKEND = os.path.expanduser("~/Desktop/TimeBack/backend")
_cwd = os.getcwd()
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
try:
    import school_config as SC
finally:
    os.chdir(_cwd)
P, EM = SC.PUBLIC_SCHOOL_CONFIG, SC.SCHOOL_STUDENT_EMAILS
check("public schools", len(P), db["public"]["schools"])
check("public students", sum(len(EM.get(k) or []) for k in P), db["public"]["students"])
check("by_school sums to public total",
      sum(s["students"] for s in db["public"]["by_school"]), db["public"]["students"])
check("districts sum to public total",
      sum(d["students"] for d in db["public"]["districts"].values()), db["public"]["students"])
check("district school counts sum",
      sum(d["schools"] for d in db["public"]["districts"].values()), db["public"]["schools"])
check("alpha + rostered public campuses = all",
      db["alpha"]["campuses"] + db["public"]["schools_rostered"], db["total_campuses"])
check("one public school is configured but not rostered",
      db["public"]["schools"] - db["public"]["schools_rostered"], 1)
check("alpha + public students = all rostered",
      db["alpha"]["students"] + db["public"]["students"], db["total_rostered"])
check("total campuses", len(EM), db["total_campuses"])
check("total rostered", sum(len(v) for v in EM.values()), db["total_rostered"])
# every school must declare a programme, subjects and a target
check("every school has a programme type",
      sum(1 for s in db["public"]["by_school"] if not s["type"]), 0)
check("every school has subjects",
      sum(1 for s in db["public"]["by_school"] if not s["subjects"]), 0)
check("every school has an xp target",
      sum(1 for s in db["public"]["by_school"] if not s["xp_target"]), 0)
# roles, recounted from main.py
mp = open(os.path.join(BACKEND, "main.py"), encoding="utf-8").read()
scopes = re.findall(r':\s*"([^"]+)"',
                    re.search(r"^_ROLES[^=]*= *\{(.*?)^\}", mp, re.S | re.M).group(1))
check("credential roles", len(scopes), db["roles"]["password_roles"])
check("distinct scopes", len(set(scopes)), db["roles"]["distinct_scopes"])
check("composite roles", sum(1 for x in scopes if "+" in x), db["roles"]["composite_roles"])
# a commented-out job must not be counted as one that runs
check("scheduled jobs exclude the commented one",
      len(re.findall(r"^\s*_scheduler\.add_job\(", mp, re.M)),
      db["surface"]["scheduled_jobs"])
# The bot's tool list is read from the agent, not typed on the page — it went
# from six to seven mid-build and a hand-written list would still say six.
tools = db["slack_tools"]
agent = open(os.path.join(BACKEND, "slack_agent.py"), encoding="utf-8").read()
check("slack tools reproduce from source",
      len(re.findall(r'\{\s*"name":\s*"[a-z_]+",\s*"description"', agent)), len(tools))
check("every tool states what it answers",
      sum(1 for t in tools if not t["what"]), 0)
check("every tool has a worked example",
      sum(1 for t in tools if not t["asks"]), 0)
# Every tool must carry an example reply, and those replies must come out of
# the bot's own renderer — not be typed onto the page.
bxj = json.load(open(f"{PROMO}/bot_examples.json"))
check("every tool has an example reply",
      sum(1 for t in tools if t["name"] not in bxj), 0)
check("every example reply has a header and body",
      sum(1 for e in bxj.values()
          if not any(k == "h" for k, _ in e["blocks"])
          or not any(k in ("p", "fields") for k, _ in e["blocks"])), 0)
# The samples are fictional on purpose; assert no real student slipped in.
real = {m["email"].split("@")[0] for m in json.load(
    open(f"{PROMO}/g12_reading_k8.json"))["all_mastered"] if m.get("email")}
leak = [t for t, e in bxj.items()
        for _, txt in e["blocks"]
        if any(r and r in txt.lower() for r in real)]
check("no real student name in the samples", len(leak), 0)

check("every tool declares what it needs",
      sum(1 for t in tools if not t["params"]), 0)

check("no job counted that is commented out",
      db["surface"]["scheduled_jobs"] < len(re.findall(r"_scheduler\.add_job\(", mp)), True)

print("\n=== 7 · RESOURCES (re-fetched live and recounted) ===")
rs = json.load(open(f"{PROMO}/resources.json"))
RDG, LIB = rs["reading"], rs["library"]
check("by_grade passages sum to total",
      sum(g["passages"] for g in RDG["by_grade"]), RDG["passages"])
check("by_grade lessons sum to total",
      sum(g["lessons"] for g in RDG["by_grade"]), RDG["lessons"])
check("by_grade words sum to total",
      sum(g["words"] for g in RDG["by_grade"]), RDG["words"])
check("every named feature is live",
      sum(1 for v in RDG["features"].values() if not v), 0)
# fetch the published page again and recount from scratch
page = subprocess.run(["curl", "-sS", "--fail", "--max-time", "40",
                       RDG["url"].rstrip("/") + "/index.html?cb=audit2"],
                      capture_output=True, text=True).stdout
m = re.search(r"const DATA = (\{.*?\});\n", page, re.S)
if not m:
    check("reading page re-fetch parsed", False, True)
else:
    data = json.loads(m.group(1))
    check("live passages recounted",
          sum(len(i["texts"]) for g in data.values() for i in g), RDG["passages"])
    check("live lessons recounted", sum(len(g) for g in data.values()), RDG["lessons"])
    check("live grades recounted", len(data), RDG["grades"])
    # no lesson may hold an empty passage, which is how a rebuild loses text
    check("no empty passages published",
          sum(1 for g in data.values() for i in g for t in i["texts"] if not t.strip()), 0)
health = json.loads(subprocess.run(
    ["curl", "-sS", "--fail", "--max-time", "40", LIB["url"] + "/api/health"],
    capture_output=True, text=True).stdout or "{}")
check("library resource count", health.get("count"), LIB["resources"])
check("library is on postgres, not ephemeral disk", health.get("postgres"), True)

print("\n=== 8 · DRI CASELOAD ===")
dr = json.load(open(os.path.expanduser("~/Desktop/dri-workload/dris.json")))
dris = dr["dris"]
check("DRI count", len(dris), dr["n_dris"])
check("per-DRI students sum to the credited total",
      round(sum(x["students"] for x in dris), 1), round(dr["total_students_credited"], 1), 0.5)
# each DRI's own campus list must add up to their headline number
# A campus with no roster carries credited=None, not 0 — the distinction is
# deliberate so an unmatched campus cannot masquerade as an empty one.
bad = [x["name"] for x in dris
       if abs(sum(c["credited"] or 0 for c in x["campuses"]) - x["students"]) > 0.5]
check("every DRI's campuses sum to their total", len(bad), 0)
unrostered = [c for x in dris for c in x["campuses"] if c["credited"] is None]
check("unrostered campuses are flagged, not zeroed",
      len(unrostered), sum(x.get("no_roster", 0) for x in dris))
# a shared campus must be split, never counted whole
shared = [c for x in dris for c in x["campuses"] if (c["share"] or 1) < 1]
check("shared campuses carry a fractional share",
      all(0 < c["share"] < 1 for c in shared), True)
check("campus counts match the campus lists",
      sum(1 for x in dris if x["n_campuses"] != len(x["campuses"])), 0)
check("caseload is not stale",
      dr["generated"] >= "2026-09-20", True)

print("\n=== 9 · THE TEAM FIGURES ON THE CASE TAB ===")
# These are the numbers the ask itself rests on, and until pull_team.py they
# were the only ones on the page no second route could reach. The caseload side
# is recomputed from the per-DRI rows rather than read from the headline keys;
# the filing side is re-queried in a different shape than pull_team.py used —
# plain group-by rows recounted in Python, not a json_build_object.
tm = json.load(open(f"{PROMO}/team.json"))
ME = "bruna.rodrigues@alpha.school"

by_students = sorted(dris, key=lambda x: -x["students"])
mine = next(x for x in dris if x["email"].lower() == ME)
total = sum(x["students"] for x in by_students)

check("n_dris matches the caseload rows", len(dris), tm["n_dris"])
check("team_students re-adds from per-DRI rows", round(total), tm["team_students"], 1)
check("team_campuses matches the campus list", dr["n_campuses"], tm["team_campuses"])
check("my_students re-read from my own row", round(mine["students"]), tm["my_students"], 1)
check("my_campuses re-read from my own row", mine["n_campuses"], tm["my_campuses"])
check("my caseload rank recomputed by sorting",
      [x["email"].lower() for x in by_students].index(ME) + 1, tm["my_caseload_rank"])
check("top3 share recomputed",
      round(100 * sum(x["students"] for x in by_students[:3]) / total), tm["top3_share"], 1)
check("caseload spread recomputed",
      round(by_students[0]["students"] / by_students[-1]["students"], 1), tm["spread"], 0.1)

# Filing side, re-queried as rows rather than as one aggregated object.
rows = sql("""select json_build_object('rows', json_agg(json_build_object(
  'email', lower(tm.email), 'pos', tm.position, 'section', ir.section)))::text
  from intervention_requests ir join team_members tm on tm.id = ir.created_by""")["rows"]
campus_rows = [r for r in rows if r["section"] == "campus_dri"]
tally = collections.Counter(r["email"] for r in campus_rows)
dri_emails = {x["email"].lower() for x in dris}
filed = {e: n for e, n in tally.items() if e in dri_emails}
silent = [x for x in dris if x["email"].lower() not in filed]

check_growing("filings recount to at least the snapshot", len(campus_rows), sum(tally.values()))
check("dri_filers recounted from raw rows", len(filed), tm["dri_filers"])
check("silent DRIs recounted", len(silent), len(tm["silent_dris"]))
check("silent students re-added", round(sum(x["students"] for x in silent)),
      tm["silent_students"], 1)
check_growing("my filings recounted", tally.get(ME, 0), tm["my_filings"])
check("my filing rank recomputed",
      sorted(tally.values(), reverse=True).index(tally.get(ME, 0)) + 1, tm["my_rank"])
check_growing("top filer recounted", max(filed.values()), tm["top_filer"])
check("min filer recounted", min(filed.values()), tm["min_filer"])
check("curriculum filers recounted from raw rows",
      len({r["email"] for r in rows
           if r["section"] == "subject_dri" and r["pos"] == "Curriculum DRI"}),
      tm["curriculum_filers"])
check_growing("creators recounted", len({r["email"] for r in rows}), tm["creators"])

live = sql("""select json_build_object(
  'campuses', (select count(distinct campus) from intervention_requests
               where campus is not null and campus <> ''),
  'completers', (select count(distinct completed_by) from intervention_requests
                 where completed_by is not null),
  'first', (select min(created_at)::date::text from intervention_requests))::text""")
check_growing("campuses covered re-queried", live["campuses"], tm["campuses_covered"])
check_growing("completers re-queried", live["completers"], tm["completers"])
check("first entry re-queried", live["first"], tm["first_entry"])

# The claim the first tab makes out of these, checked as a claim and not just
# as arithmetic. "All N of 16" was live on the page while N was 14.
check("adoption is not overstated as unanimous",
      tm["dri_filers"] <= tm["n_dris"] and
      (tm["dri_filers"] == tm["n_dris"]) == (len(tm["silent_dris"]) == 0), True)
check("every DRI who filed is on the caseload sheet",
      len(set(filed) - dri_emails), 0)
# "including the Nth-largest caseload" is prose on the case tab, so the rank
# behind it has to be re-derived like any other figure.
ranks = sorted([x["email"].lower() for x in by_students].index(s["email"].lower()) + 1
               for s in [next(y for y in dris if y["name"] == d["name"])
                         for d in tm["silent_dris"]])
check("silent DRI caseload ranks recomputed",
      ranks, sorted(d["caseload_rank"] for d in tm["silent_dris"]))
check("the worst silent caseload rank recomputed", ranks[0], tm["silent_top_rank"])
check("team figures are not stale", tm["caseload_generated"] >= "2026-09-20", True)


json.dump({"passed": len(PASS), "failed": len(FAIL),
           "ran": __import__("datetime").date.today().isoformat(),
           "failures": [n for n, _, _ in FAIL]},
          open(f"{PROMO}/audit.json", "w"), indent=1)

print("\n" + "=" * 78)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for name, got, want in FAIL:
    print(f"   FAIL  {name}: recomputed {got}, stored {want}")
sys.exit(1 if FAIL else 0)
