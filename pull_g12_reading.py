"""Current K-8 students who have mastered a Grade 12 Reading test.

Mastery is the dashboard's own threshold, 89.5%, on a test-level result.

Two judgement calls, both made explicit because they change the answer:

WHICH TESTS COUNT. Filtering on `metadata.subject = 'Reading'` alone is not
safe. At grade 12 the subject label also carries `Reading-notqced`,
`Reading-notQCed`, `Reading-unit`, `Reading-athena` and `Reading-ISEE`, and
those hold a mix of real tests and engineering artefacts — "Testing preview",
"Hottext Test", "Full Flow". So the rule is the test *name*: the real grade-12
reading instruments are `Alpha ELA STAAR G12.<year>` and
`Alpha Standardized Reading G12.<n>`. Two genuine STAAR results sit under
`Reading-notqced` and are included; the artefacts are not, and neither is
`Alpha Standardized Language G12.4`, which is Language.

WHICH STUDENTS COUNT. "Current" is live enrolment as OneRoster defines it — an
active user record, at least one active role, and that role's end date not yet
passed. Grade is the student's own grade level. Test accounts are dropped.

Writes /tmp/promo/g12_reading_k8.csv and .json.
"""
import collections
import csv
import json
import os
import re
import sys
import time

BACKEND = os.path.expanduser("~/Desktop/TimeBack/backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
from dotenv import load_dotenv                                    # noqa: E402
load_dotenv(os.path.expanduser("~/Desktop/TimeBack/.env"))
import data_client as dc                                          # noqa: E402

MASTERY = 89.5
TODAY = time.strftime("%Y-%m-%d")
K8 = {"K", "KG", "0", "1", "2", "3", "4", "5", "6", "7", "8"}
STUDENTS = "/tmp/all_students.json"
OUT_JSON = "/tmp/promo/g12_reading_k8.json"
OUT_CSV = os.path.expanduser("~/Desktop/K8 students who mastered G12 Reading.csv")

# The real grade-12 reading instruments, by name.
REAL_TEST = re.compile(r"^\s*Alpha\s+(ELA\s+STAAR|Standardized\s+Reading)\s+G12\.", re.I)


def live(u):
    if u.get("status") != "active":
        return False
    for r in u.get("roles") or []:
        if r.get("status") != "active":
            continue
        end = (r.get("endDate") or "").strip()
        if end and end <= TODAY:
            continue
        return True
    return False


def page(hdrs, flt):
    rows, offset = [], 0
    while True:
        r = dc.get(hdrs, "/ims/oneroster/gradebook/v1p2/assessmentResults/",
                   {"filter": flt, "limit": 1000, "offset": offset}) or {}
        batch = r.get("assessmentResults") or []
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(rows) >= (r.get("totalCount") or 0):
            break
    return rows


def main():
    hdrs = {"Authorization": f"Bearer {dc.get_token()}"}

    # Every test-level result at grade 12, whatever the subject label says.
    rows = page(hdrs, "metadata.resultType='assessment' AND metadata.grade='12'")
    print(f"grade-12 test-level results: {len(rows):,}")

    reading = [x for x in rows if REAL_TEST.match((x.get("metadata") or {}).get("testName") or "")]
    print(f"  on a real G12 reading test: {len(reading)}")
    dropped = collections.Counter(
        (x.get("metadata") or {}).get("subject")
        for x in rows
        if not REAL_TEST.match((x.get("metadata") or {}).get("testName") or "")
        and "read" in ((x.get("metadata") or {}).get("subject") or "").lower())
    if dropped:
        print(f"  reading-labelled rows dropped as not a real G12 test: {dict(dropped)}")

    # Best score per student.
    best = {}
    for x in reading:
        md = x.get("metadata") or {}
        sid = (x.get("student") or {}).get("sourcedId")
        email = (md.get("studentEmail") or "").lower().strip()
        score = x.get("score")
        if score is None:
            continue
        key = sid or email
        if key not in best or score > best[key]["score"]:
            best[key] = {
                "score": round(float(score), 1), "sid": sid, "result_email": email,
                "test": md.get("testName"), "test_type": md.get("testType"),
                "subject_label": md.get("subject"),
                "date": (x.get("scoreDate") or "")[:10],
                "correct": md.get("correctQuestions"), "total": md.get("totalQuestions"),
            }
    mastered = [v for v in best.values() if v["score"] >= MASTERY]
    print(f"  students with a score: {len(best)}   mastered >= {MASTERY}%: {len(mastered)}")

    users = json.load(open(STUDENTS))
    by_sid = {u["sourcedId"]: u for u in users}
    by_email = {}
    for u in users:
        e = (u.get("email") or "").lower().strip()
        if e:
            by_email.setdefault(e, u)

    resolved, unresolved = [], []
    for m in mastered:
        u = by_sid.get(m["sid"]) or by_email.get(m["result_email"])
        if not u:
            unresolved.append(m)
            continue
        grades = u.get("grades") or []
        m.update({
            "name": f"{u.get('givenName','')} {u.get('familyName','')}".strip(),
            "email": (u.get("email") or "").lower().strip(),
            "grade": grades[0] if grades else None,
            "current": live(u),
            "test_account": (u.get("metadata") or {}).get("isTestUser") in (True, "true"),
        })
        resolved.append(m)
    if unresolved:
        print(f"  WARNING: {len(unresolved)} not found on the roster")

    k8 = [m for m in resolved
          if str(m["grade"]) in K8 and m["current"] and not m["test_account"]]
    k8.sort(key=lambda m: (int(m["grade"]) if str(m["grade"]).isdigit() else -1, m["name"]))

    excl = collections.Counter()
    for m in resolved:
        if m["test_account"]:
            excl["test account"] += 1
        elif not m["current"]:
            excl["no longer enrolled"] += 1
        elif str(m["grade"]) not in K8:
            excl[f"grade {m['grade']}"] += 1
    print(f"  excluded: {dict(excl)}")

    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump({"generated": TODAY, "mastery_threshold": MASTERY,
               "k8": k8, "all_mastered": resolved}, open(OUT_JSON, "w"), indent=1)

    cols = ["email", "name", "grade", "score", "correct", "total", "test",
            "test_type", "date"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Student email", "Name", "Grade", "Score %", "Correct",
                    "Questions", "Test", "Test type", "Date mastered"])
        for m in k8:
            w.writerow([m.get(c, "") for c in cols])

    print(f"\n==> {len(k8)} current K-8 students have mastered G12 Reading")
    print(f"    by grade: {dict(collections.Counter('G'+str(m['grade']) for m in k8))}")
    print(f"    wrote {OUT_CSV}")
    for m in k8:
        print(f"      G{m['grade']:<2} {m['email']:<46} {m['score']:>5.1f}%  {m['test']}")


if __name__ == "__main__":
    main()
