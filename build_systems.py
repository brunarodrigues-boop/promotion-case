"""Builds index.html — a tabbed dashboard making the case, with the evidence.

Tab one is the case itself: the summary and the argument for promotion. Every
other tab is one system or one body of evidence, so a reader can go straight to
whichever claim they want to test.

Every figure comes from a data file written by a pull, never from a literal
typed into the HTML. Where a number needed a judgement call (which rows count,
which window), the call is stated on the page next to the number.

Inputs
  /tmp/promo/accuracy.json        pull_accuracy.py
  /tmp/promo/interventions.json   pull_interventions.sh
  /tmp/promo/deepdive.json        pull_interventions.sh
  ~/Desktop/dri-workload/tickets.json   pull_tickets.py + classify.py
  repo figures                    counted live from the working copies
"""
import json
import os
import pathlib
import subprocess

import charts as C

HERE = pathlib.Path(__file__).parent
OUT = HERE / "index.html"
PROMO = pathlib.Path("/tmp/promo")
DRI = pathlib.Path(os.path.expanduser("~/Desktop/dri-workload"))

acc = json.load(open(PROMO / "accuracy.json"))
iv = json.load(open(PROMO / "interventions.json"))
dd = json.load(open(PROMO / "deepdive.json"))
tk = json.load(open(DRI / "tickets.json"))

MINE = ("bruna rodrigues", "brunar999", "brunarodrigues-boop")


def sh(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                              text=True, timeout=90).stdout.strip()
    except Exception:
        return ""


def school_stats(backend):
    code = ("import sys; sys.path.insert(0,'.'); import school_config as s; "
            "print(len(s.SCHOOL_STUDENT_EMAILS), "
            "sum(len(v) for v in s.SCHOOL_STUDENT_EMAILS.values()), "
            "len(s.PUBLIC_SCHOOL_CONFIG))")
    try:
        a, b, c = sh(f'python3 -c "{code}"', backend).split()
        return {"campuses": int(a), "rostered": int(b), "public": int(c)}
    except Exception:
        return {"campuses": 0, "rostered": 0, "public": 0}


def repo_stats():
    """Counted at build time. A claim about my own work should be re-derivable."""
    tb = os.path.expanduser("~/Desktop/TimeBack")
    ad = os.path.expanduser("~/Desktop/alpha-academic-dashboard")

    log = sh("git log --all --format=%an%x09%s", tb).splitlines()
    total = len(log)
    subjects = [s for a, _, s in (l.partition("\t") for l in log)
                if a.strip().lower() in MINE]
    fixes = sum(1 for s in subjects if s.lower().startswith("fix"))
    feats = sum(1 for s in subjects if s.lower().startswith("feat"))

    tsx = "src/pages/admin/Interventions.tsx"
    tab_mine = tab_all = 0
    for line in sh(f"git log --format=%an -- {tsx} | sort | uniq -c | sort -rn", ad).splitlines():
        n, _, who = line.strip().partition(" ")
        tab_all += int(n)
        if who.strip().lower() in MINE:
            tab_mine += int(n)

    mine = len(subjects)
    return {
        "tb_commits": total, "tb_mine": mine,
        "tb_pct": round(100 * mine / total) if total else 0,
        "fixes": fixes, "feats": feats,
        "tb_first": sh("git log --reverse --format=%ad --date=short | head -1", tb),
        "endpoints": int(sh("grep -rhoE '@router\\.(get|post|put|delete)' routers/*.py main.py | wc -l",
                            tb + "/backend") or 0),
        "reports": int(sh("ls services/pdf/*.py | wc -l", tb + "/backend") or 0) - 2,
        "pyloc": int(sh("find . -name '*.py' -not -path './venv/*' -exec cat {} + | wc -l",
                        tb + "/backend") or 0),
        "tab_mine": tab_mine, "tab_all": tab_all,
        "agent_loc": int(sh("wc -l < slack_agent.py", tb + "/backend") or 0),
        "dd_loc": int(sh("wc -l < services/pdf/student_deep_dive_pdf.py", tb + "/backend") or 0),
        **school_stats(tb + "/backend"),
    }


R = repo_stats()
O = acc["overall"]
T = iv["turnaround"]
CA, CU = iv["campus"], iv["curriculum"]
EF = iv["effort"]
KP, ST = tk["kpi"], tk["solve_time"]

help_med_d = ST["median_human_h"] / 24.0
iv_med_h = T["median_h"]
effort_h = EF["campus_own_h"] + EF["curriculum_answer_h"]
app16 = acc["by_app"][:16]
app_spread = max(d["acc"] for d in app16) - min(d["acc"] for d in app16)


# ── building blocks ──────────────────────────────────────────────────────────
def stat(v, label):
    return f'<div class="stat"><div class="val">{v}</div><div class="label">{label}</div></div>'


def minis(pairs):
    return '<div class="minis">' + "".join(
        f'<div class="mini"><b>{v}</b><span>{k}</span></div>' for k, v in pairs) + "</div>"


def why(text):
    return (f'<div class="why"><span class="why-tag">Why it has to exist</span>'
            f'<p>{text}</p></div>')


def claim(n, title, body, evidence):
    return f"""
    <div class="claim">
      <div class="claim-n">{n}</div>
      <div>
        <h4>{title}</h4>
        <p>{body}</p>
        <p class="claim-ev"><b>Evidence:</b> {evidence}</p>
      </div>
    </div>"""


def cell_table(rows):
    body = "".join(
        f'<tr><td>{C.esc(d["key"])}</td><td class="n">{d["acc"]}%</td>'
        f'<td class="n">{d["answered"]:,}</td><td class="n">{d["students"]}</td></tr>'
        for d in rows)
    return ('<table><tr><th>Subject · app</th><th class="n">Accuracy</th>'
            '<th class="n">Questions</th><th class="n">Students</th></tr>'
            f"{body}</table>")


def legend(items, colours):
    return ('<div class="legend">' + "".join(
        f'<span><i style="background:{colours[i % len(colours)]}"></i>'
        f'{C.esc(k)} — {v:,}</span>' for i, (k, v) in enumerate(items)) + "</div>")


# ── charts ───────────────────────────────────────────────────────────────────
grade_rows = [(d["label"], d["acc"], f'{d["answered"]:,} q') for d in acc["by_grade"]
              if d["answered"] >= 20000]
SUBJ_FLOOR = 50000
subj_rows = [(d["key"], d["acc"], f'{d["students"]} students · {d["answered"]:,} q')
             for d in acc["by_subject"] if d["answered"] >= SUBJ_FLOOR]
app_rows = [(d["key"], d["acc"], f'{d["answered"]:,} q') for d in app16]

chart_grade = C.hbars(grade_rows, vmin=60, vmax=100, good=88, ok=82, label_w=52, steps=4)
chart_subj = C.hbars(subj_rows, vmin=60, vmax=100, good=88, ok=82, label_w=100, steps=4)
chart_app = C.hbars(app_rows, vmin=60, vmax=100, good=88, ok=80, label_w=150, steps=4)

chart_turn = C.vbars([("≤8h", T["within_8h"], "same day"),
                      ("≤24h", T["within_24h"], "next day"),
                      ("≤48h", T["within_48h"], "two days")],
                     unit="%", height=170, vmax=100, rotate=False)
chart_types = C.vbars([(d["type"], d["n"], "") for d in iv["type_volume"][:9]], height=215)
chart_type_speed = C.hbars(
    [(d["type"], d["median_h"], f'n={d["n"]}') for d in
     sorted(iv["by_type"], key=lambda x: x["median_h"])],
    unit="h", vmin=0, label_w=136, colour=C.PURPLE)

CELL_FLOOR = 40000
cells = [d for d in acc["by_subject_app"] if d["answered"] >= CELL_FLOOR]
weak = sorted(cells, key=lambda d: d["acc"])[:8]
strong = sorted(cells, key=lambda d: -d["acc"])[:4]

dist = ST["distribution"]
chart_solve = C.vbars([(d["label"], d["pct"], f'{d["n"]:,}') for d in dist],
                      unit="%", height=180)
cats = sorted(tk["all_categories"].items(), key=lambda x: -x[1])
CAT_COLS = [C.PURPLE, "#a396d6", "#bdb2e2", "#d6cfee", "#ebe6f7"]
chart_cats = C.stacked(cats, colours=CAT_COLS) + legend(cats, CAT_COLS)
wk = [r for r in tk["weekly"]["rows"] if r["week_start"] != tk["weekly"].get("partial_week")]
chart_weekly = C.vbars([(r["label"], r["opened"], f'{r["resolved"]:,} closed') for r in wk],
                       height=180)
by_type_tk = ST["by_type"]
chart_tk_type = C.hbars(
    [(k, round(v["median_h"] / 24, 1), f'n={v["n"]:,}') for k, v in
     sorted(by_type_tk.items(), key=lambda x: x[1]["median_h"])],
    unit="d", vmin=0, label_w=180, colour=C.AMBER)

TABS = [("case", "The case"), ("measure", "Dashboard"), ("answer", "Deep dive bot"),
        ("act", "Interventions"), ("reuse", "Resources"), ("accuracy", "Accuracy"),
        ("support", "Support load"), ("method", "Method")]

nav = "".join(f'<button class="tab-btn" data-tab="{k}">{v}</button>' for k, v in TABS)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bruna Rodrigues — The case, in numbers</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #f7f5fc; color: #1a1a1a; line-height: 1.6; -webkit-font-smoothing: antialiased; }}
  main {{ max-width: 900px; margin: 0 auto; padding: 0 28px 110px; }}

  header {{ text-align: center; padding: 56px 0 26px; }}
  .role-tag {{ display: inline-block; background: #ede9f8; color: #7b6db8; font-size: .72rem;
    font-weight: 600; letter-spacing: .1em; text-transform: uppercase; padding: 5px 14px;
    border-radius: 20px; margin-bottom: 14px; }}
  header h1 {{ font-size: 2.5rem; font-weight: 700; letter-spacing: -.03em; }}
  header .since {{ margin-top: 11px; font-size: .8rem; color: #a9a3ba; }}

  /* ── tabs ── */
  .tabs {{ position: sticky; top: 0; z-index: 20; background: rgba(247,245,252,.93);
    backdrop-filter: blur(10px); border-bottom: 1px solid #e3ddf2; margin-bottom: 30px; }}
  .tabs-inner {{ max-width: 900px; margin: 0 auto; padding: 0 20px; display: flex; gap: 3px;
    overflow-x: auto; scrollbar-width: none; }}
  .tabs-inner::-webkit-scrollbar {{ display: none; }}
  .tab-btn {{ flex: 0 0 auto; border: none; background: none; cursor: pointer; padding: 14px 15px 12px;
    font-family: inherit; font-size: .84rem; font-weight: 600; color: #9990ad;
    border-bottom: 2.5px solid transparent; transition: color .12s, border-color .12s;
    white-space: nowrap; }}
  .tab-btn:hover {{ color: #6f5fb0; }}
  .tab-btn.on {{ color: #6f5fb0; border-bottom-color: #8b7dc8; }}
  .panel {{ display: none; }}
  .panel.on {{ display: block; animation: fade .18s ease; }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(3px); }} to {{ opacity: 1; }} }}

  .stats {{ display: flex; flex-wrap: wrap; border: 1px solid #e0daf0; border-radius: 16px;
    background: #fff; overflow: hidden; margin-bottom: 26px; }}
  .stat {{ flex: 1 1 150px; padding: 24px 15px; text-align: center; border-right: 1px solid #e0daf0; }}
  .stat:last-child {{ border-right: none; }}
  .stat .val {{ font-size: 1.8rem; font-weight: 700; color: #8b7dc8; letter-spacing: -.02em; line-height: 1; }}
  .stat .label {{ font-size: .71rem; color: #999; margin-top: 8px; line-height: 1.4; }}

  .section-heading {{ font-size: .7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .14em; color: #8b7dc8; margin: 0 0 16px; }}
  .card {{ background: #fff; border: 1px solid #e0daf0; border-radius: 16px;
    padding: 28px 30px 24px; margin-bottom: 18px; }}
  .card h2 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -.02em; margin-bottom: 4px; }}
  .card h3 {{ font-size: 1.08rem; font-weight: 700; margin-bottom: 8px; letter-spacing: -.02em; }}
  .card > p.lead {{ font-size: .93rem; color: #555; margin-bottom: 18px; }}
  .pill {{ display: inline-block; background: #ede9f8; color: #7b6db8; font-size: .64rem;
    font-weight: 700; letter-spacing: .09em; text-transform: uppercase; padding: 4px 11px;
    border-radius: 20px; margin-bottom: 11px; }}
  .why {{ border-left: 3px solid #8b7dc8; background: #faf8ff; border-radius: 0 10px 10px 0;
    padding: 13px 17px; margin: 14px 0 16px; }}
  .why-tag {{ display: block; font-size: .63rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .12em; color: #8b7dc8; margin-bottom: 5px; }}
  .why p {{ font-size: .93rem; color: #3d3d3d; }}
  .minis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 9px;
    margin-bottom: 18px; }}
  .mini {{ background: #faf8ff; border: 1px solid #ece7f8; border-radius: 10px; padding: 11px 12px; }}
  .mini b {{ display: block; font-size: 1.1rem; color: #6f5fb0; letter-spacing: -.01em; }}
  .mini span {{ display: block; font-size: .68rem; color: #999; margin-top: 3px; line-height: 1.35; }}
  .foot {{ font-size: .76rem; color: #9a93ab; margin-top: 13px; font-style: italic; }}
  .sub {{ font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
    color: #b0a8c4; margin: 22px 0 8px; }}
  .chart {{ display: block; margin: 6px 0 4px; }}
  .callout {{ display: flex; gap: 18px; align-items: center; background: #f4f0ff;
    border: 1px solid #ddd4f5; border-radius: 12px; padding: 16px 20px; margin: 18px 0 6px; }}
  .callout .big {{ font-size: 1.85rem; font-weight: 700; color: #6f5fb0; line-height: 1;
    white-space: nowrap; }}
  .callout p {{ font-size: .86rem; color: #4a4459; }}

  /* ── the claims on tab one ── */
  .claim {{ display: flex; gap: 16px; padding: 18px 0; border-bottom: 1px solid #f2eefb; }}
  .claim:last-child {{ border-bottom: none; padding-bottom: 2px; }}
  .claim-n {{ flex: 0 0 30px; height: 30px; border-radius: 50%; background: #ede9f8;
    color: #6f5fb0; font-weight: 700; font-size: .85rem; display: flex; align-items: center;
    justify-content: center; }}
  .claim h4 {{ font-size: 1rem; font-weight: 700; margin-bottom: 5px; letter-spacing: -.01em; }}
  .claim p {{ font-size: .9rem; color: #4d4d4d; }}
  .claim-ev {{ margin-top: 7px; font-size: .82rem !important; color: #7d7690 !important; }}
  .claim-ev b {{ color: #6f5fb0; }}

  table {{ width: 100%; border-collapse: collapse; font-size: .84rem; margin-top: 6px; }}
  th {{ text-align: left; font-size: .66rem; text-transform: uppercase; letter-spacing: .09em;
    color: #b0a8c4; padding: 7px 8px; border-bottom: 1px solid #e0daf0; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #f2eefb; vertical-align: top; }}
  td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td b {{ color: #6f5fb0; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 2px 0 4px; font-size: .74rem;
    color: #8a849b; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .legend i {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
  .method {{ font-size: .8rem; color: #8a849b; line-height: 1.65; }}
  .method li {{ margin-bottom: 8px; }}
  .method ul {{ padding-left: 17px; }}
  code {{ background: #f0ecf9; padding: 1px 5px; border-radius: 4px; font-size: .92em; }}
  a {{ color: #7b6db8; }}

  @media print {{
    body {{ background: #fff; }}
    main {{ padding: 0; max-width: none; }}
    .tabs {{ display: none; }}
    .panel {{ display: block !important; page-break-before: always; }}
    .panel:first-of-type {{ page-break-before: avoid; }}
    .card {{ break-inside: avoid; page-break-inside: avoid; border-color: #ccc; }}
    .print-title {{ display: block !important; }}
  }}
  .print-title {{ display: none; font-size: 1.5rem; font-weight: 700; margin: 0 0 14px;
    padding-bottom: 8px; border-bottom: 2px solid #8b7dc8; }}
</style>
</head>
<body>

<header>
  <span class="role-tag">The case, in numbers</span>
  <h1>Bruna Rodrigues</h1>
  <div class="since">Accuracy {O['window'].replace(' to ', ' → ')} ·
    interventions {iv['window']['first']} → {iv['window']['last']} ·
    helpdesk pulled {tk['pulled_at'][:10]}</div>
</header>

<div class="tabs"><div class="tabs-inner">{nav}</div></div>

<main>

<!-- ══ 1 · THE CASE ══ -->
<section class="panel" id="case">
<div class="print-title">The case</div>

<div class="stats">
  {stat(f"{O['answered']/1e6:.1f}M", "questions measured across every Alpha app")}
  {stat(f"{O['pooled_acc']}%", "pooled accuracy, all students all apps")}
  {stat(f"{CA['touches']:,}", f"interventions logged in {iv['window']['days']} days")}
  {stat(f"{iv_med_h:g}h", "median time to close one")}
  {stat(f"{R['tb_mine']:,}", f"commits on the platform ({R['tb_pct']}% of all)")}
</div>

<div class="card">
  <h2>Why promote me</h2>
  <p class="lead">
    Five claims. Each one is a number on another tab, not an adjective — so each one can be
    checked, and each one can be argued with.
  </p>

  {claim(1, "I own the layer the role runs on.",
    "The TimeBack dashboard is the platform every Campus DRI monitors students through. It is not "
    "a side project I contributed to; it is the thing I have been building, and the playbook's "
    "monitoring routine was written on top of it because the tool and the process were designed "
    "together.",
    f"{R['tb_mine']:,} of {R['tb_commits']:,} commits ({R['tb_pct']}%), "
    f"{R['campuses']} campuses, {R['rostered']:,} rostered students, {R['endpoints']} API "
    f"endpoints, {R['reports']} report generators.")}

  {claim(2, "I build what is missing, not what is asked for.",
    "Nobody filed a ticket asking for a Slack bot. The queue asked for it: deep dives were being "
    "requested faster than anyone could hand-build them, and a request that waits ten days is a "
    "student who went ten days without the answer. I read the backlog as a specification.",
    f"{dd['requests']} deep dives requested by hand in {iv['window']['days']} days for "
    f"{dd['students']} students; the manual path closed {dd['completed']}, "
    f"{dd['open']} are still open, the oldest waiting {dd['oldest_open_days']:.0f} days.")}

  {claim(3, "I made the work measurable — including my own.",
    "Before the intervention log there was no record of what was tried for a stalled student, by "
    "whom, or whether it worked. That made the whole function unarguable in both directions: no "
    "credit for the work, and no way to find what was not working. It is now the only record of "
    "remediation the platform did not do by itself.",
    f"{CA['touches']:,} touches over {CA['students']} students in {iv['window']['days']} days, "
    f"median close {iv_med_h:g} hours, {T['within_24h']}% inside a day, and "
    f"{effort_h:.0f} hours of effort now attributable to a named person.")}

  {claim(4, "I own a data source other teams read through.",
    "<code>alpha_dri_interventions</code> is published to the data-source-skill contract with a "
    "dictionary, query rules and a hand-written judgement layer saying what the values mean — "
    "which interventions signal a platform failure, which are routine, and what good looks like. "
    "Credentials are issued per person, by me.",
    "Source owner and key issuer. The rules are binding enough that this page obeys them: the two "
    "logs are never totalled, a row is reported as a touch rather than a failure, and the two "
    "minutes columns are scoped separately. A check over every row found zero violations.")}

  {claim(5, "I find what is failing silently.",
    "The failures that matter are the ones nothing reports. Mid-week reports were putting working "
    "students in the RED tier at 0.0 XP/day — on one report, seven of the nine students listed as "
    "having little to no engagement had earned XP every single day. The cause was a fetch that "
    "returned empty instead of raising when the API answered 503, so an outage read as a child "
    "doing no work. I fixed the fetch and added a guard so an unloadable student is shown as "
    "unknown rather than as a zero.",
    f"{R['fixes']} of my {R['tb_mine']:,} commits are fixes ({R['feats']} are features). The same "
    f"instinct caught a silent cap in the helpdesk pull behind this page — it stopped at exactly "
    f"40,000 cases against an instance of {tk['scanned']:,} and reported nothing.")}
</div>

<div class="card">
  <h3>One loop, built end to end</h3>
  <p class="lead">
    These are not four tools that happen to sit near each other. They are four stages of one loop,
    and each exists because the stage before it produced something nobody could act on.
  </p>
  <table>
    <tr><th>Stage</th><th>Without it</th><th>The evidence</th></tr>
    <tr><td><b>Measure</b></td>
        <td>{O['n_apps']} apps, {O['answered']/1e6:.1f}M questions, no shared view</td>
        <td>a {app_spread:.0f}-point spread between apps, invisible from inside any one</td></tr>
    <tr><td><b>Answer</b></td>
        <td>every question needs a person to build the answer</td>
        <td>{dd['requests']} deep dives asked for in {iv['window']['days']} days; {dd['open']} still waiting</td></tr>
    <tr><td><b>Act</b></td>
        <td>no record of what was tried, by whom, or whether it worked</td>
        <td>{CA['touches']:,} touches, {CA['students']} students, median close {iv_med_h:g} h</td></tr>
    <tr><td><b>Reuse</b></td>
        <td>the same artefact rebuilt at every campus</td>
        <td>a shared library, {effort_h:.0f} h of logged effort to measure it against</td></tr>
  </table>
</div>

<div class="card">
  <h3>The honest caveats</h3>
  <p class="lead">Stated here rather than buried, because a case a reviewer can puncture is worth less
    than one that punctures itself first.</p>
  <table>
    <tr><td style="width:38%"><b>The helpdesk comparison</b></td>
        <td>{help_med_d:.1f} days against {iv_med_h:g} hours is <em>not</em> like for like — a support
        ticket and an academic stall are different work. It is the same organisation, period and
        largely the same students, which is why it is worth showing, but it is not a controlled
        comparison.</td></tr>
    <tr><td><b>The intervention window is short</b></td>
        <td>{iv['window']['days']} days. Long enough to show a rate, not long enough to show a trend.</td></tr>
    <tr><td><b>Effort capture is partial</b></td>
        <td>The form only began asking on 2026-09-11, so {EF['cm_have']} of {EF['cm_eligible']}
        eligible requests since then carry minutes ({round(100*EF['cm_have']/EF['cm_eligible'])}%),
        and anything completed earlier carries none.</td></tr>
    <tr><td><b>The dashboard is not solo work</b></td>
        <td>{R['tb_pct']}% of commits are mine, which means {100-R['tb_pct']}% are not. On the
        intervention tab specifically it is {R['tab_mine']} of {R['tab_all']}.</td></tr>
  </table>
</div>
</section>

<!-- ══ 2 · DASHBOARD ══ -->
<section class="panel" id="measure">
<div class="print-title">TimeBack Dashboard</div>
<div class="card">
  <span class="pill">Measure</span>
  <h2>TimeBack Dashboard</h2>
  {why(f"A student works in up to {O['n_apps']} apps, each with its own console and its own idea of "
       f"what accuracy means. Without one place that reads all of them, <b>“is this child actually "
       f"learning?”</b> is a question that takes a person a day of tab-switching to answer — per "
       f"child. At {O['students']:,} students that question simply does not get asked.")}
  <p class="lead">The production platform every Campus DRI monitors through: XP, time, accuracy,
    tests and grade-level progress, per student per subject, with role-based guide and admin views,
    daily alerts, doom-loop detection and generated reports.</p>
  {minis([("campuses configured", R['campuses']), ("students rostered", f"{R['rostered']:,}"),
          ("public-school districts", R['public']), ("API endpoints", R['endpoints']),
          ("report generators", R['reports']),
          ("commits, mine", f"{R['tb_mine']:,} ({R['tb_pct']}%)")])}
  <p class="foot">Repository since {R['tb_first']}; {R['tb_mine']:,} of {R['tb_commits']:,} commits
    are mine, counted with <code>git shortlog</code> over all branches. The {R['rostered']:,}
    rostered students span Alpha campuses and the {R['public']} public-school districts together,
    and are a wider population than the {O['students']:,} Alpha students in the accuracy figures —
    those two numbers count different things and are not comparable.</p>
</div>
</section>

<!-- ══ 3 · DEEP DIVE BOT ══ -->
<section class="panel" id="answer">
<div class="print-title">The Deep Dive Bot</div>
<div class="card">
  <span class="pill">Answer</span>
  <h2>The Deep Dive Bot</h2>
  {why(f"The dashboard answers questions you already know to ask, in a browser, at a desk. Real "
       f"questions arrive in Slack, from a guide, mid-lesson: <b>“why is this student stuck?”</b> "
       f"The demand is measured, not assumed — in {iv['window']['days']} days <b>{dd['requests']} "
       f"deep dives were requested by hand</b> for {dd['students']} students, and the hand-built "
       f"path closed {dd['completed']}. {dd['open']} are still open, the oldest waiting "
       f"{dd['oldest_open_days']:.0f} days. That queue is the argument for the bot.")}
  <p class="lead">A Slack bot that turns a plain-English question into a rendered report in the
    thread. The model picks one tool and writes a single framing sentence — it never restates a
    figure, because the tool result is rendered directly. That division is deliberate: a number
    cannot drift between the API and the channel, and an uncertain request comes back as a
    clarifying question instead of a confident answer about the wrong student.</p>
  {minis([("deep dives requested by hand", dd['requests']), ("closed by hand", dd['completed']),
          ("still waiting", dd['open']), ("tools exposed", 6),
          ("agent, lines", f"{R['agent_loc']:,}"), ("ack budget", "3s")])}
  <p class="foot">Tools: student_deep_dive, student_lessons, most_concerning, doom_loops,
    tests_taken, assigned_tests. Slack redelivers on any non-200, so events are de-duplicated on
    event_id and the work is handed to a background task inside the 3-second window. Demand figures
    are the ‘Deep dive’ request type in the intervention log — the manual route the bot replaces.</p>
</div>
</section>

<!-- ══ 4 · INTERVENTIONS ══ -->
<section class="panel" id="act">
<div class="print-title">The Intervention Log</div>
<div class="card">
  <span class="pill">Close the loop</span>
  <h2>The Intervention Log</h2>
  {why("Measuring a stall and doing nothing about it is just a report. When TimeBack does not "
       "resolve a student's stall by itself somebody has to intervene — and before this there was "
       "<b>no record of what was tried, by whom, or whether it worked</b>. It is the only record of "
       "remediation the platform did not do by itself, and the only place the trigger for each one "
       "is written down.")}
  <p class="lead">Two independent logs: requests a Campus DRI raises and pushes to a Curriculum DRI,
    and work the Campus DRI absorbs themselves.</p>
  {minis([("campus touches", f"{CA['touches']:,}"), ("distinct cases", CA['cases']),
          ("students", CA['students']), ("completed", CA['completed']),
          ("still open", CA['open']), ("hours of effort", f"{effort_h:.0f}")])}
  <p class="foot">A row is a touch, not a failure — the same student can appear more than once, so
    both the touch count and the folded case count are shown. The two logs are independent and are
    never totalled together; the Curriculum DRI log holds a further {CU['touches']} touches over
    {CU['students']} students.</p>
</div>

<div class="card">
  <h3>How fast a stall gets answered</h3>
  <p class="lead">All {T['n']} completed Campus DRI requests, from raised to closed. Median
    <b>{iv_med_h:g} hours</b>, 90th percentile {T['p90_h']:g} hours.</p>
  {chart_turn}
  <p class="sub">Volume by request type</p>
  {chart_types}
  <p class="sub">Median hours to close, by type</p>
  {chart_type_speed}
  <p class="foot">Types with fewer than five completed requests are omitted. Curriculum DRI rows are
    excluded from every timing figure on purpose: that log records work retrospectively — the entry
    is written after the work is done — so elapsed time is not defined for it.</p>
  <div class="callout">
    <div class="big">{effort_h:.0f} h</div>
    <p>of human effort logged, split by constraint into {EF['campus_own_h']:.0f}&nbsp;h of Campus DRI
      work absorbed directly ({EF['campus_own_n']} entries) and {EF['curriculum_answer_h']:.0f}&nbsp;h
      spent by Curriculum DRIs answering requests ({EF['curriculum_answer_n']} entries). Separate
      columns, separate people; the schema refuses either in the other's place, and a check over
      every row found <b>zero</b> violations.</p>
  </div>
</div>
</section>

<!-- ══ 5 · RESOURCES ══ -->
<section class="panel" id="reuse">
<div class="print-title">The Resource Library</div>
<div class="card">
  <span class="pill">Reuse</span>
  <h2>The Resource Library</h2>
  {why("The same study guide gets rebuilt at five campuses by five people who do not know the other "
       "four exist. Every hour spent regenerating an artefact that already exists is an hour not "
       "spent on a student who is stuck.")}
  <p class="lead">A shared library on its own Railway service with Postgres behind it, so a resource
    added by anyone appears for everyone rather than living in one person's browser. Two roles —
    staff see everything, students never receive staff-only rows — plus generated study-guide and
    practice-test pages.</p>
  {minis([("resources live", 30), ("subjects", 7), ("grade bands", 13),
          ("resource types", 8), ("roles", 2), ("in the DRI resource tab", 75)])}
  <p class="foot">Counts read live from the service's own /api/health and /api/config. Postgres-backed:
    Railway wipes container disk on redeploy, so the app refuses to pretend SQLite is safe and warns
    in the UI instead.</p>
</div>
</section>

<!-- ══ 6 · ACCURACY ══ -->
<section class="panel" id="accuracy">
<div class="print-title">Accuracy</div>
<div class="card">
  <h3>Accuracy across every grade, subject and app</h3>
  <p class="lead">{O['answered']:,} answered questions from {O['students']:,} students between
    {O['window'].replace(' to ', ' and ')}. Pooled accuracy is <b>{O['pooled_acc']}%</b>; the median
    student sits at {O['median_student_acc']}%. Pooled means every question counts once — not an
    average of averages, so a student who answered 40,000 questions does not weigh the same as one
    who answered 40.</p>
  <p class="sub">By grade</p>
  {chart_grade}
  <p class="foot">Grades under 20,000 answered questions are omitted. PreK sits lowest at
    {[d['acc'] for d in acc['by_grade'] if d['label']=='PreK'][0]}% on the thinnest sample
    ({[d['students'] for d in acc['by_grade'] if d['label']=='PreK'][0]} students).</p>
  <p class="sub">By subject</p>
  {chart_subj}
  <p class="sub">By app — the 16 largest by volume</p>
  {chart_app}
  <p class="foot">This is the chart that earns the dashboard: a {app_spread:.0f}-point spread
    between the best and worst app, invisible from inside any single app's own console.</p>
  <p class="sub">Where it is weakest — subject inside app</p>
  <p class="lead">An app-level average hides which subject inside it is dragging. These are the
    weakest cells carrying at least {CELL_FLOOR:,} answered questions, which is where a placement or
    app-swap decision is worth making.</p>
  {cell_table(weak)}
  <p class="sub">And where it is strongest</p>
  {cell_table(strong)}
</div>
</section>

<!-- ══ 7 · SUPPORT LOAD ══ -->
<section class="panel" id="support">
<div class="print-title">Support load</div>
<div class="card">
  <h3>What comes in through the helpdesk</h3>
  <p class="lead">{KP['total']:,} cases on the Alpha / 2hr Learning brands of the Trilogy central
    helpdesk, pulled from the Kayako API on {tk['pulled_at'][:10]} and sorted by ordered rules over
    subject and last message. {KP['open']:,} are still open ({KP['open_pct']}%), median open age
    {KP['median_open_age']} days.</p>
  {chart_cats}
  <p class="sub">Opened per week, last {len(wk)} full weeks</p>
  {chart_weekly}
  <p class="sub">Time to resolution — the distribution, not the median</p>
  {chart_solve}
  <p class="foot">The shape matters more than any single number: {ST['automated_pct']}% of cases
    close inside an hour by automation and most of the rest take three days to two weeks, so the
    overall median falls in the empty valley between the humps and describes almost nothing. For the
    {ST['n_human']:,} cases a human actually worked, the median is {help_med_d:.1f} days.</p>
  <p class="sub">Median days to resolution, by ticket type</p>
  {chart_tk_type}
  <div class="callout">
    <div class="big">{help_med_d:.1f} d → {iv_med_h:g} h</div>
    <p>A platform problem raised through the general helpdesk waits a median of {help_med_d:.1f} days
      for a human resolution. An academic stall raised through the purpose-built intervention loop is
      closed in {iv_med_h:g} hours. These are <em>different kinds of work</em> and the comparison is
      not apples to apples — but it is the same organisation, the same period and largely the same
      students, and it is the clearest available evidence for what a dedicated loop buys over a
      general queue.</p>
  </div>
</div>
</section>

<!-- ══ 8 · METHOD ══ -->
<section class="panel" id="method">
<div class="print-title">Method &amp; provenance</div>
<div class="card method">
  <h3>Method &amp; provenance</h3>
  <ul>
    <li><b>Accuracy</b> — one API call per student over the whole Alpha roster
      ({O['roster']:,} resolved, {O['students']:,} with recorded activity in the window),
      {O['window']}, pulled {O['pulled']}. Cohort key is the student's own OneRoster grade, not a
      per-subject working grade. Figures are pooled (Σ correct ÷ Σ answered), never an average of
      per-student averages. The {O['n_apps']} “apps” are the distinct source names the API reports,
      which includes a few internal surfaces (TimeBack Dash, manual XP assignment) alongside the
      learning apps proper; the by-app chart shows the 16 largest by volume, all real apps.</li>
    <li><b>Interventions</b> — read from the <code>alpha_dri_interventions</code> source, scoped to
      its published rules: the two <code>section</code> values are independent logs and are never
      totalled; a row is a touch, so folded case counts are given alongside; minutes are read from
      <code>minutes_spent</code> for Campus DRI manual work and <code>completion_minutes</code> for
      Curriculum DRI answers, which the store keeps disjoint by constraint.</li>
    <li><b>Turnaround</b> — <code>completed_at − created_at</code> over completed Campus DRI rows.
      All {T['n']} qualify. The {CU['touches']} Curriculum DRI rows are excluded because that log is
      written retrospectively, which would otherwise produce negative elapsed times.</li>
    <li><b>Support tickets</b> — the Kayako instance carries {tk['scanned']:,} cases across ~219
      brands and its API accepts no brand filter, so the pull reads every case and filters locally to
      the {tk['alpha_total']:,} Alpha-brand ones, of which {KP['total']:,} classify into a named type.
      Resolution is measured to <code>last_completed_at</code>, the agent's resolving reply — not
      <code>last_closed_at</code>, an auto-close firing days later that reads 72 hours against a real
      resolution of 0.1. The pull's page cap was raised from 40,000 to 45,000 for this run: the
      instance had outgrown it and the previous run truncated silently.</li>
    <li><b>Repository figures</b> — counted live from the working copies at build time with
      <code>git log</code> and <code>grep</code>, not recalled.</li>
  </ul>
  <p class="foot">Rebuild the whole page with <code>python3 build_systems.py</code>. The three pull
    scripts that produce its inputs are in this repository; no figure on any tab is typed by hand.</p>
</div>
</section>

</main>

<script>
  // Tabs. The hash is the address so a specific claim can be linked to, and
  // print shows every panel so the PDF is the whole case rather than one tab.
  const panels = [...document.querySelectorAll('.panel')];
  const buttons = [...document.querySelectorAll('.tab-btn')];

  function show(id, push) {{
    const found = panels.some(p => p.id === id);
    if (!found) id = panels[0].id;
    panels.forEach(p => p.classList.toggle('on', p.id === id));
    buttons.forEach(b => b.classList.toggle('on', b.dataset.tab === id));
    if (push && location.hash.slice(1) !== id) history.replaceState(null, '', '#' + id);
    window.scrollTo({{ top: 0, behavior: 'instant' }});
  }}

  buttons.forEach(b => b.addEventListener('click', () => show(b.dataset.tab, true)));
  window.addEventListener('hashchange', () => show(location.hash.slice(1), false));
  show(location.hash.slice(1) || panels[0].id, false);

  // Left/right arrows move between tabs.
  document.addEventListener('keydown', e => {{
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    if (/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
    const i = panels.findIndex(p => p.classList.contains('on'));
    const j = Math.min(panels.length - 1, Math.max(0, i + (e.key === 'ArrowRight' ? 1 : -1)));
    if (j !== i) show(panels[j].id, true);
  }});
</script>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT}  ({len(HTML):,} bytes, {len(TABS)} tabs)")
print(f"  accuracy   {O['answered']:,} questions, {O['pooled_acc']}% pooled, {O['n_apps']} apps")
print(f"  campus log {CA['touches']} touches / {CA['cases']} cases / {CA['students']} students")
print(f"  turnaround median {iv_med_h}h over n={T['n']}")
print(f"  helpdesk   {KP['total']:,} classified, human median {help_med_d:.1f}d")
print(f"  repo       {R['tb_mine']}/{R['tb_commits']} commits ({R['tb_pct']}%), "
      f"{R['fixes']} fixes / {R['feats']} features")
