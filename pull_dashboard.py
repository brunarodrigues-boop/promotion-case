"""Read the dashboard's own configuration and describe what it actually serves.

Counted from the source at build time rather than remembered, because the
shape of this changes every week: campuses get added, a role gets scoped to a
new set of schools, a district joins.

Two populations are deliberately kept apart and must not be added together:

  Alpha campuses      the private network, rostered by email allowlist
  Public schools      12 partner schools in 4 districts, each with its own
                      programme type, subject set and daily XP target

Writes /tmp/promo/dashboard.json.
"""
import json
import os
import re
import subprocess
import sys

BACKEND = os.path.expanduser("~/Desktop/TimeBack/backend")
OUT = "/tmp/promo/dashboard.json"

# District is not in the config — the schools are keyed by their own acronyms.
# Mapped here from the school names, which is a judgement call and is labelled
# as one on the page rather than presented as data from the source.
DISTRICTS = {
    "jhes - hardeeville elementary school":            ("Jasper County, SC", "JHES"),
    "jhms - hardeeville junior senior high school":    ("Jasper County, SC", "JHMS"),
    "jres - ridgeland elementary school":              ("Jasper County, SC", "JRES"),
    "jrhs - ridgeland secondary academy of excellence": ("Jasper County, SC", "JRHS"),
    "afes - allendale fairfax elementary school":      ("Allendale County, SC", "AFES"),
    "a-drew academy":                                  ("Aldine ISD, TX", "A-Drew"),
    "a-hambrick middle school":                        ("Aldine ISD, TX", "A-Hambrick"),
    "a-jones middle school":                           ("Aldine ISD, TX", "A-Jones"),
    "a-lewis middle school":                           ("Aldine ISD, TX", "A-Lewis"),
    "aldine isd":                                      ("Aldine ISD, TX", "Aldine ISD"),
    "alpha school fort davis":                         ("Fort Davis, TX", "Fort Davis"),
    "sciencesis":                                      ("ScienceSIS", "ScienceSIS"),
}


def sh(cmd):
    return subprocess.run(cmd, cwd=BACKEND, shell=True, capture_output=True,
                          text=True, timeout=90).stdout.strip()


def slack_tools(backend):
    """The bot's tools, read from the agent rather than remembered.

    Read from source on purpose: this list grew from six to seven while the
    page was being written, and a hand-typed list would still say six.
    """
    src = open(os.path.join(backend, "slack_agent.py"), encoding="utf-8").read()
    blocks = re.findall(
        r'\{\s*"name":\s*"([a-z_]+)",\s*"description":\s*\((.*?)\),\s*"input_schema"(.*?)\n    \},',
        src, re.S)
    # Some tools carry their own worked phrasings ("Use for 'X'"); the deep
    # dive's examples live in the system prompt instead. Both are lifted from
    # source rather than invented, so a row with no example shows none.
    sysm = re.search(r'SYSTEM = """(.*?)"""', src, re.S)
    sys_examples = re.findall(r'"([^"]{8,60})"', sysm.group(1)) if sysm else []
    extra = {"student_deep_dive": [e for e in sys_examples if "deep dive" in e.lower()]}

    out = []
    for name, desc, schema in blocks:
        text = " ".join(re.findall(r'"([^"]*)"', desc))
        text = re.sub(r"\s+", " ", text).strip()
        # the descriptions carry their own worked phrasings: "Use for 'X', 'Y'"
        asks = re.findall(r"'([^']{6,70})'", text)
        what = re.split(r"\s*Use for\b", text)[0].strip().rstrip(".")
        props = re.findall(r'"([a-z_]+)":\s*\{"type"', schema)
        req = re.search(r'"required":\s*\[([^\]]*)\]', schema)
        out.append({
            "name": name,
            "what": what,
            "asks": (asks or extra.get(name, []))[:3],
            "params": props,
            "required": [x.strip().strip('"') for x in (req.group(1).split(",") if req else []) if x.strip()],
        })
    return out


def main():
    sys.path.insert(0, BACKEND)
    cwd = os.getcwd()
    os.chdir(BACKEND)
    try:
        import school_config as sc
    finally:
        os.chdir(cwd)

    P = sc.PUBLIC_SCHOOL_CONFIG
    emails = sc.SCHOOL_STUDENT_EMAILS

    schools = []
    for key in sorted(P):
        cfg = P[key]
        district, short = DISTRICTS.get(key, ("—", key))
        schools.append({
            "key": key, "short": short, "district": district,
            "students": len(emails.get(key) or []),
            "type": cfg.get("type"),
            "subjects": cfg.get("subjects") or [],
            "doom_subjects": cfg.get("doom_subjects") or [],
            "xp_target": cfg.get("daily_xp_target"),
        })

    districts = {}
    for s in schools:
        d = districts.setdefault(s["district"], {"schools": 0, "students": 0, "types": set()})
        d["schools"] += 1
        d["students"] += s["students"]
        d["types"].add(s["type"])
    districts = {k: {**v, "types": sorted(v["types"])} for k, v in districts.items()}

    main_py = open(os.path.join(BACKEND, "main.py"), encoding="utf-8").read()

    def block(name):
        m = re.search(rf"^{name}[^=]*= *\{{(.*?)^\}}", main_py, re.S | re.M)
        return len(re.findall(r'^\s+"', m.group(1), re.M)) if m else 0

    # Distinct access scopes: "all", a single school, or a composite like
    # "austin_l2+lf+plano+nova_austin".
    roles = re.search(r"^_ROLES[^=]*= *\{(.*?)^\}", main_py, re.S | re.M).group(1)
    scopes = re.findall(r':\s*"([^"]+)"', roles)
    composite = [s for s in scopes if "+" in s]
    dri = [s for s in scopes if s.startswith("dri_")]

    public_students = sum(s["students"] for s in schools)
    alpha_keys = [k for k in emails if k not in P]

    out = {
        "public": {
            "schools": len(schools),
            # One public key ("aldine isd") is a programme configuration with no
            # allowlist of its own, so it is configured but not rostered. The
            # distinction matters: 95 Alpha campuses + 12 public schools is 107,
            # but the campus list holds 106.
            "schools_rostered": sum(1 for s in schools if s["students"]),
            "students": public_students,
            "districts": districts,
            "by_school": schools,
            "programme_types": sorted({s["type"] for s in schools}),
            "xp_targets": sorted({s["xp_target"] for s in schools}),
        },
        "alpha": {
            "campuses": len(alpha_keys),
            "students": sum(len(emails[k]) for k in alpha_keys),
        },
        "total_campuses": len(emails),
        "total_rostered": sum(len(v) for v in emails.values()),
        "roles": {
            "password_roles": len(scopes),
            "distinct_scopes": len(set(scopes)),
            "composite_roles": len(composite),
            "composite_examples": composite[:3],
            "dri_roles": len(dri),
            "role_to_school_map": block("_ROLE_SCHOOL"),
            "token_ttl_hours": 12,
        },
        "surface": {
            "endpoints": int(sh("grep -rhoE '@router\\.(get|post|put|delete)' "
                                "routers/*.py main.py | wc -l") or 0),
            "report_endpoints": int(sh("grep -rhoE '@router\\.(get|post)\\(\"[^\"]+\"' "
                                       "routers/*.py | grep -icE 'report|pdf|alert'") or 0),
            "report_generators": int(sh("ls services/pdf/*.py | wc -l") or 0) - 2,
            "routers": int(sh("ls routers/*.py | wc -l") or 0),
            # one add_job in the file is commented out; counting it would
            # claim a job that does not run
            "scheduled_jobs": len(re.findall(r"^\s*_scheduler\.add_job\(",
                                             main_py, re.M)),
            "scheduled_job_names": sorted(set(re.findall(
                r"_scheduler\.add_job\(\s*\n\s+(_[a-z_]+),", main_py))),
            "cache_refresh_minutes": 30,
        },
        "slack_tools": slack_tools(BACKEND),
    }
    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)

    print(f"public schools {out['public']['schools']}, "
          f"{out['public']['students']:,} students, "
          f"{len(districts)} districts")
    for d, v in sorted(districts.items(), key=lambda x: -x[1]["students"]):
        print(f"   {d:<24} {v['schools']} schools  {v['students']:>5,} students  "
              f"{'/'.join(v['types'])}")
    print(f"alpha campuses {out['alpha']['campuses']}, "
          f"{out['alpha']['students']:,} students")
    print(f"roles: {out['roles']['password_roles']} password roles, "
          f"{out['roles']['distinct_scopes']} distinct scopes, "
          f"{out['roles']['composite_roles']} composite, "
          f"{out['roles']['role_to_school_map']} role→school entries")
    print(f"slack bot: {len(out['slack_tools'])} tools — "
          f"{', '.join(t['name'] for t in out['slack_tools'])}")
    print(f"surface: {out['surface']['endpoints']} endpoints, "
          f"{out['surface']['report_endpoints']} report endpoints, "
          f"{out['surface']['routers']} routers, "
          f"{out['surface']['scheduled_jobs']} scheduled jobs")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
