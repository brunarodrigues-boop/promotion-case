"""Rebuild the three OneRoster caches pull_dris.py reads.

They live in /tmp and are therefore not durable — the machine clears them and
the DRI caseload refresh stops with a FileNotFoundError that says nothing about
what produced the file. Nothing in dri-workload builds them, so this does.

  /tmp/all_orgs.json         every org
  /tmp/all_students.json     every student, with roles, status and email
  /tmp/students_per_org.json {org sourcedId: live enrolled students}

"Live enrolled" is the same definition pull_dris.py uses and it matters: an
active user record, at least one active role, and that role's end date not yet
passed. A student is counted once, under the org on their live role, so there is
no double counting across campuses.
"""
import json
import os
import sys
import time

BACKEND = os.path.expanduser("~/Desktop/TimeBack/backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from dotenv import load_dotenv                                   # noqa: E402
load_dotenv(os.path.expanduser("~/Desktop/TimeBack/.env"))
import data_client as dc                                          # noqa: E402

PAGE = 1000          # 3000 returns a 502 from this API
TRIES = 5
TODAY = time.strftime("%Y-%m-%d")


def main():
    hdrs = {"Authorization": f"Bearer {dc.get_token()}"}

    orgs = dc.get_orgs(hdrs)
    json.dump(orgs, open("/tmp/all_orgs.json", "w"))
    print(f"orgs: {len(orgs):,}")

    # Retry, and refuse to write a short file. Writing whatever came back is
    # how an outage becomes a roster of zero students that looks like data.
    students, offset, total = [], 0, None
    while True:
        batch = None
        for attempt in range(TRIES):
            r = dc.get(hdrs, "/ims/oneroster/rostering/v1p2/students",
                       {"limit": PAGE, "offset": offset}) or {}
            batch = r.get("users")
            if batch:
                total = r.get("totalCount") or total
                break
            time.sleep(min(2 ** attempt, 10))
        if not batch:
            raise SystemExit(f"students: no rows at offset {offset} after {TRIES} tries — "
                             f"refusing to write a partial cache")
        students.extend(batch)
        print(f"  students {len(students):,}/{total:,}", flush=True)
        if total and len(students) >= total:
            break
        offset += len(batch)

    if total and len(students) < total:
        raise SystemExit(f"students: got {len(students):,} of {total:,} — not writing")
    json.dump(students, open("/tmp/all_students.json", "w"))
    print(f"students: {len(students):,}")

    # One count per org, over live roles only.
    per = {}
    live = 0
    for u in students:
        if u.get("status") != "active":
            continue
        for role in u.get("roles") or []:
            if role.get("status") != "active":
                continue
            end = (role.get("endDate") or "").strip()
            if end and end <= TODAY:
                continue
            org = (role.get("org") or {}).get("sourcedId")
            if org:
                per[org] = per.get(org, 0) + 1
                live += 1
            break                      # a student counts once, on their live role
    json.dump(per, open("/tmp/students_per_org.json", "w"))
    print(f"live enrolled: {live:,} across {len(per):,} orgs")


if __name__ == "__main__":
    main()
