"""The team figures the case tab rests on: caseload, and who files into the log.

This is the one input the page had no producer for. Every other figure on the
page could be rebuilt from a script in this repo; the eighteen on the first tab
— the ask paragraph, the headline stat row, the caseload claims and the
caveats — came from a team.json that was written by hand and then lost when
/tmp was cleared. Unauditable and unrebuildable is the pair of properties this
whole repo exists to avoid, so it is a script now.

TWO SOURCES, JOINED ON EMAIL.

  caseload   ~/Desktop/dri-workload/dris.json — live enrolled students per DRI,
             shared campuses split evenly, produced by pull_dris.py
  filings    the alpha_dri_interventions source, via the InsForge CLI, same
             route and same rules as pull_interventions.sh

Joined on lowercased email, never on name. The two sources disagree on the
spelling of three of the sixteen people — "Chris Voigt" against "Christopher
Voigt", "Hari Soragaon" against "Hariprasad Soragaon", "Joshua Albar" against
"Joshua Lance Martin Albar". Name matching silently drops those three and the
adoption claim comes out at 11 of 16 instead of 14.

WHO COUNTS AS A DRI. The sixteen in dris.json, which is the caseload sheet the
team is actually organised by — not `position = 'Campus DRI'` in team_members,
which is 13 of them: my own row reads "AI-driven Learning Analyst", and two
people who file into the campus log (a Curriculum DRI and an Academic Lead)
carry no campus caseload at all.

Only the campus_dri log is used for filings. The two sections are independent
logs and are never totalled, per the source's published rules.

Writes /tmp/promo/team.json.
"""
import json
import os
import re
import subprocess
import sys

DASH = os.path.expanduser("~/Desktop/alpha-academic-dashboard")
DRIS = os.path.expanduser("~/Desktop/dri-workload/dris.json")
OUT = "/tmp/promo/team.json"
ME = "bruna.rodrigues@alpha.school"

Q = """
select json_build_object(
 'first_entry', (select min(created_at)::date::text from intervention_requests),
 'campuses_covered', (select count(distinct campus) from intervention_requests
                      where campus is not null and campus <> ''),
 'creators', (select count(distinct created_by) from intervention_requests),
 'completers', (select count(distinct completed_by) from intervention_requests
                where completed_by is not null),
 'curriculum_filers', (select count(distinct ir.created_by) from intervention_requests ir
                       join team_members tm on tm.id = ir.created_by
                       where ir.section = 'subject_dri' and tm.position = 'Curriculum DRI'),
 'campus_filers', (select json_agg(json_build_object('email', lower(tm.email),
                                                     'name', tm.name, 'n', f.n) order by f.n desc)
                   from (select created_by, count(*) n from intervention_requests
                         where section = 'campus_dri' group by 1) f
                   join team_members tm on tm.id = f.created_by)
)::text
"""


def query(sql):
    """The CLI renders a table; the cell holds the JSON. Same route as pull_interventions.sh."""
    r = subprocess.run(["npx", "-y", "@insforge/cli", "db", "query", sql],
                       cwd=DASH, capture_output=True, text=True, timeout=300)
    plain = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout)
    for line in plain.splitlines():
        m = re.search(r"\{.*\}", line)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
    raise SystemExit(f"no JSON in CLI output — not writing.\n{plain[:600]}\n{r.stderr[:400]}")


def ordinal_rank(seq, key):
    return next(i for i, v in enumerate(seq, 1) if v == key)


def main():
    d = json.load(open(DRIS))
    dris = sorted(d["dris"], key=lambda x: -x["students"])
    by_email = {x["email"].lower(): x for x in dris}
    if ME not in by_email:
        raise SystemExit(f"{ME} is not in {DRIS} — the caseload claims cannot be built")

    q = query(Q)
    filings = {f["email"]: f["n"] for f in (q["campus_filers"] or [])}

    # Adoption: DRIs on the caseload sheet who have filed at least one campus row.
    filed = {e: n for e, n in filings.items() if e in by_email}
    silent = [x for x in dris if x["email"].lower() not in filed]

    # A partial join is the failure mode this repo keeps hitting: it would read
    # as DRIs who never filed, which is exactly the claim being made.
    if not filed or len(filed) < 2:
        raise SystemExit(f"only {len(filed)} of {len(dris)} DRIs matched on email — "
                         f"the join is broken, not the adoption. Not writing.")

    mine = by_email[ME]
    students = [x["students"] for x in dris]
    total = sum(students)
    # Rank among everyone who files into the campus log, not just the sixteen —
    # the caveat it backs is "I am not the heaviest user of my own log".
    order = sorted(filings.values(), reverse=True)

    tm = {
        # caseload, from dris.json
        "n_dris": len(dris),
        "team_campuses": d["n_campuses"],
        "team_students": round(total),
        "my_students": round(mine["students"]),
        "my_campuses": mine["n_campuses"],
        "my_caseload_rank": ordinal_rank([x["email"].lower() for x in dris], ME),
        "top3_share": round(100 * sum(students[:3]) / total),
        "spread": round(students[0] / students[-1], 1) if students[-1] else None,
        # the log, from the intervention source
        "dri_filers": len(filed),
        "curriculum_filers": q["curriculum_filers"],
        "creators": q["creators"],
        "completers": q["completers"],
        "campuses_covered": q["campuses_covered"],
        "first_entry": q["first_entry"],
        "top_filer": max(filed.values()),
        "min_filer": min(filed.values()),
        "my_filings": filings.get(ME, 0),
        "my_rank": ordinal_rank(order, filings.get(ME, 0)),
        # Not yet on the page, but the honest form of the adoption claim: who
        # has not filed, and how many children they are responsible for.
        "silent_dris": [{"name": x["name"], "students": round(x["students"]),
                         "campuses": x["n_campuses"],
                         "caseload_rank": [y["email"].lower() for y in dris]
                                          .index(x["email"].lower()) + 1} for x in silent],
        "silent_top_rank": min(([y["email"].lower() for y in dris]
                                .index(x["email"].lower()) + 1) for x in silent) if silent else None,
        "silent_students": round(sum(x["students"] for x in silent)),
        "caseload_generated": d["generated"],
    }

    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(tm, open(OUT, "w"), indent=1)

    print(f"wrote {OUT}")
    print(f"  {tm['dri_filers']} of {tm['n_dris']} DRIs have filed; "
          f"{len(silent)} have not ({tm['silent_students']:,} students)")
    for s in tm["silent_dris"]:
        print(f"     silent: {s['name']} — {s['students']:,} students")
    print(f"  me: {tm['my_students']:,} students, caseload rank {tm['my_caseload_rank']}; "
          f"{tm['my_filings']} filings, rank {tm['my_rank']}")
    print(f"  filings range {tm['min_filer']}-{tm['top_filer']}, "
          f"top3 carry {tm['top3_share']}%, spread {tm['spread']}x")


if __name__ == "__main__":
    main()
