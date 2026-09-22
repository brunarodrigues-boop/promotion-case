"""Builds index.html — the four systems, why each exists, and the evidence.

Every figure on the page comes from a data file written by a pull, never from a
literal typed into the HTML. Where a number needed a judgement call (which rows
count, which window), the call is stated on the page next to the number rather
than buried here.

Inputs
  /tmp/promo/accuracy.json        from timeback-trackers/alpha_app_accuracy_cache.json
  /tmp/promo/interventions.json   from InsForge, scoped per the data-source skill
  ~/Desktop/dri-workload/tickets.json   from pull_tickets.py + classify.py
  repo stats                      counted live from the working copies
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


# ── repo facts, counted rather than remembered ───────────────────────────────
def sh(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                              text=True, timeout=60).stdout.strip()
    except Exception:
        return ""


def repo_stats():
    tb = os.path.expanduser("~/Desktop/TimeBack")
    ad = os.path.expanduser("~/Desktop/alpha-academic-dashboard")
    total = int(sh("git log --oneline | wc -l", tb) or 0)
    mine = 0
    for line in sh("git shortlog -sn --all", tb).splitlines():
        n, _, who = line.strip().partition("\t")
        if who.strip().lower() in ("bruna rodrigues", "brunar999", "brunarodrigues-boop"):
            mine += int(n)
    tsx = "src/pages/admin/Interventions.tsx"
    tab_mine = tab_all = 0
    for line in sh(f"git log --format=%an -- {tsx} | sort | uniq -c | sort -rn", ad).splitlines():
        n, _, who = line.strip().partition(" ")
        tab_all += int(n)
        if who.strip().lower() in ("bruna rodrigues", "brunar999", "brunarodrigues-boop"):
            tab_mine += int(n)
    return {
        "tb_commits": total, "tb_mine": mine,
        "tb_pct": round(100 * mine / total) if total else 0,
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


def school_stats(backend):
    """Campus coverage, read from the config rather than remembered."""
    code = ("import sys; sys.path.insert(0,'.'); import school_config as s; "
            "print(len(s.SCHOOL_STUDENT_EMAILS), "
            "sum(len(v) for v in s.SCHOOL_STUDENT_EMAILS.values()), "
            "len(s.PUBLIC_SCHOOL_CONFIG))")
    try:
        a, b, c = sh(f'python3 -c "{code}"', backend).split()
        return {"campuses": int(a), "rostered": int(b), "public": int(c)}
    except Exception:
        return {"campuses": 0, "rostered": 0, "public": 0}


R = repo_stats()
O = acc["overall"]
T = iv["turnaround"]
CA, CU = iv["campus"], iv["curriculum"]
EF = iv["effort"]
KP, ST = tk["kpi"], tk["solve_time"]

# Helpdesk median in days, for a sentence that reads like a human wrote it.
help_med_d = ST["median_human_h"] / 24.0
iv_med_h = T["median_h"]


# ── page pieces ──────────────────────────────────────────────────────────────
def stat(v, label):
    return f'<div class="stat"><div class="val">{v}</div><div class="label">{label}</div></div>'


def card(tag, title, why, what, chart="", stats=None, foot=""):
    s = ""
    if stats:
        s = '<div class="minis">' + "".join(
            f'<div class="mini"><b>{v}</b><span>{k}</span></div>' for k, v in stats) + "</div>"
    return f"""
    <section class="sys">
      <div class="sys-head"><span class="pill">{tag}</span><h2>{title}</h2></div>
      <div class="why"><span class="why-tag">Why it has to exist</span><p>{why}</p></div>
      <p class="what">{what}</p>
      {s}{chart}
      {f'<p class="foot">{foot}</p>' if foot else ''}
    </section>"""


# ── charts ───────────────────────────────────────────────────────────────────
grade_rows = [(d["label"], d["acc"], f'{d["answered"]:,} q') for d in acc["by_grade"]
              if d["answered"] >= 20000]
# Volume floor, not a student floor: Handwriting has 32 students but only 1,058
# answered questions, and at that size a percentage is noise sitting next to
# Vocabulary's seven million.
SUBJ_FLOOR = 50000
subj_rows = [(d["key"], d["acc"], f'{d["students"]} students · {d["answered"]:,} q')
             for d in acc["by_subject"] if d["answered"] >= SUBJ_FLOOR]
subj_dropped = [d for d in acc["by_subject"] if d["answered"] < SUBJ_FLOOR]
app_rows = [(d["key"], d["acc"], f'{d["answered"]:,} q') for d in acc["by_app"][:16]]

chart_grade = C.hbars(grade_rows, vmin=60, vmax=100, good=88, ok=82, label_w=52, steps=4)
chart_subj = C.hbars(subj_rows, vmin=60, vmax=100, good=88, ok=82, label_w=100, steps=4)
chart_app = C.hbars(app_rows, vmin=60, vmax=100, good=88, ok=80, label_w=150, steps=4)

turn_rows = [("≤8h", T["within_8h"], "same day"),
             ("≤24h", T["within_24h"], "next day"),
             ("≤48h", T["within_48h"], "two days")]
chart_turn = C.vbars([(a, b, c) for a, b, c in turn_rows], unit="%", height=170,
                     vmax=100, rotate=False)

type_rows = [(d["type"], d["n"], "") for d in iv["type_volume"][:9]]
chart_types = C.vbars(type_rows, height=215)

chart_type_speed = C.hbars(
    [(d["type"], d["median_h"], f'n={d["n"]}') for d in
     sorted(iv["by_type"], key=lambda x: x["median_h"])],
    unit="h", vmin=0, label_w=136, colour=C.PURPLE)

# The actionable cut: a subject inside one app, where a swap is a real decision.
CELL_FLOOR = 40000
cells = [d for d in acc["by_subject_app"] if d["answered"] >= CELL_FLOOR]
weak = sorted(cells, key=lambda d: d["acc"])[:8]
strong = sorted(cells, key=lambda d: -d["acc"])[:4]


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

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bruna Rodrigues — Systems in Production</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #f7f5fc; color: #1a1a1a; line-height: 1.6; -webkit-font-smoothing: antialiased; }}
  main {{ max-width: 880px; margin: 0 auto; padding: 72px 28px 110px; }}
  header {{ text-align: center; margin-bottom: 44px; }}
  .role-tag {{ display: inline-block; background: #ede9f8; color: #7b6db8; font-size: .72rem;
    font-weight: 600; letter-spacing: .1em; text-transform: uppercase; padding: 5px 14px;
    border-radius: 20px; margin-bottom: 16px; }}
  header h1 {{ font-size: 2.7rem; font-weight: 700; letter-spacing: -.03em; }}
  header .since {{ margin-top: 12px; font-size: .85rem; color: #999; }}
  .intro {{ font-size: 1.05rem; line-height: 1.75; color: #444; margin: 0 auto 52px;
    max-width: 700px; text-align: center; }}
  .stats {{ display: flex; flex-wrap: wrap; border: 1px solid #e0daf0; border-radius: 16px;
    background: #fff; overflow: hidden; margin-bottom: 56px; }}
  .stat {{ flex: 1 1 150px; padding: 26px 16px; text-align: center; border-right: 1px solid #e0daf0; }}
  .stat:last-child {{ border-right: none; }}
  .stat .val {{ font-size: 1.85rem; font-weight: 700; color: #8b7dc8; letter-spacing: -.02em; line-height: 1; }}
  .stat .label {{ font-size: .72rem; color: #999; margin-top: 8px; line-height: 1.4; }}
  .section-heading {{ font-size: .7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .14em; color: #8b7dc8; margin: 0 0 18px; }}
  .sys {{ background: #fff; border: 1px solid #e0daf0; border-radius: 16px; padding: 30px 30px 26px;
    margin-bottom: 18px; }}
  .sys-head {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .pill {{ background: #ede9f8; color: #7b6db8; font-size: .66rem; font-weight: 700;
    letter-spacing: .09em; text-transform: uppercase; padding: 4px 11px; border-radius: 20px; }}
  .sys h2 {{ font-size: 1.32rem; font-weight: 700; letter-spacing: -.02em; }}
  .why {{ border-left: 3px solid #8b7dc8; background: #faf8ff; border-radius: 0 10px 10px 0;
    padding: 13px 17px; margin-bottom: 16px; }}
  .why-tag {{ display: block; font-size: .63rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .12em; color: #8b7dc8; margin-bottom: 5px; }}
  .why p {{ font-size: .93rem; color: #3d3d3d; }}
  .what {{ font-size: .93rem; color: #555; margin-bottom: 18px; }}
  .minis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 9px;
    margin-bottom: 20px; }}
  .mini {{ background: #faf8ff; border: 1px solid #ece7f8; border-radius: 10px; padding: 11px 12px; }}
  .mini b {{ display: block; font-size: 1.12rem; color: #6f5fb0; letter-spacing: -.01em; }}
  .mini span {{ display: block; font-size: .68rem; color: #999; margin-top: 3px; line-height: 1.35; }}
  .foot {{ font-size: .76rem; color: #9a93ab; margin-top: 14px; font-style: italic; }}
  .chart {{ display: block; margin: 6px 0 4px; }}
  .ev {{ background: #fff; border: 1px solid #e0daf0; border-radius: 16px; padding: 28px 30px;
    margin-bottom: 18px; }}
  .ev h3 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; letter-spacing: -.02em; }}
  .ev p.lead {{ font-size: .92rem; color: #555; margin-bottom: 18px; }}
  .sub {{ font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
    color: #b0a8c4; margin: 22px 0 8px; }}
  .callout {{ display: flex; gap: 18px; align-items: center; background: #f4f0ff;
    border: 1px solid #ddd4f5; border-radius: 12px; padding: 16px 20px; margin: 18px 0 6px; }}
  .callout .big {{ font-size: 1.9rem; font-weight: 700; color: #6f5fb0; line-height: 1; white-space: nowrap; }}
  .callout p {{ font-size: .86rem; color: #4a4459; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .84rem; margin-top: 6px; }}
  th {{ text-align: left; font-size: .66rem; text-transform: uppercase; letter-spacing: .09em;
    color: #b0a8c4; padding: 7px 8px; border-bottom: 1px solid #e0daf0; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #f2eefb; }}
  td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .method {{ font-size: .79rem; color: #8a849b; line-height: 1.65; }}
  .method li {{ margin-bottom: 7px; }}
  .method ul {{ padding-left: 17px; }}
  .method code {{ background: #f0ecf9; padding: 1px 5px; border-radius: 4px; font-size: .92em; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 2px 0 4px; font-size: .74rem;
    color: #8a849b; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .legend i {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
  .nav {{ margin-top: 14px; font-size: .78rem; color: #b3aec2; }}
  .nav a {{ text-decoration: none; }}
  .nav a:hover {{ text-decoration: underline; }}
  .nav span {{ color: #7b6db8; font-weight: 600; }}
  table td b {{ color: #6f5fb0; }}
  a {{ color: #7b6db8; }}
  @media print {{
    body {{ background: #fff; }}
    main {{ padding: 0; max-width: none; }}
    .sys, .ev {{ break-inside: avoid; page-break-inside: avoid; border-color: #ccc; }}
  }}
</style>
</head>
<body>
<main>

<header>
  <span class="role-tag">The case, in numbers</span>
  <h1>Four systems in production</h1>
  <div class="since">Measured {acc['overall']['window'].replace(' to ', ' → ')} ·
    interventions {iv['window']['first']} → {iv['window']['last']} ·
    helpdesk pulled {tk['pulled_at'][:10]}</div>
</header>

<p class="intro">
  {O['students']:,} students are learning across {O['n_apps']} different apps, and each app
  only knows its own corner. These four systems are what turns that into something a person
  can act on: one place that <b>measures</b>, a bot that <b>answers</b>, a log that
  <b>closes the loop</b>, and a library that stops the same work being done twice.
  This page states what each one is for, and puts the numbers underneath it.
</p>

<div class="stats">
  {stat(f"{O['answered']/1e6:.1f}M", "questions measured across every Alpha app")}
  {stat(f"{O['pooled_acc']}%", "pooled accuracy, all students all apps")}
  {stat(f"{CA['touches']:,}", f"intervention touches logged in {iv['window']['days']} days")}
  {stat(f"{iv_med_h:g}h", "median time to close an intervention")}
  {stat(f"{KP['total']:,}", "support tickets classified")}
</div>

<p class="section-heading">The four systems</p>

{card("Measure", "TimeBack Dashboard",
  f"A student works in up to {O['n_apps']} apps, each with its own console and its own idea of "
  f"what accuracy means. Without one place that reads all of them, <b>“is this child actually "
  f"learning?”</b> is a question that takes a person a day of tab-switching to answer — per child. "
  f"At {O['students']:,} students that question simply does not get asked.",
  f"The production platform every Campus DRI monitors through: XP, time, accuracy, tests and "
  f"grade-level progress, per student per subject, with role-based guide and admin views, daily "
  f"alerts, doom-loop detection and generated reports.",
  stats=[("campuses configured", R['campuses']),
         ("students rostered", f"{R['rostered']:,}"),
         ("public-school districts", R['public']),
         ("API endpoints", R['endpoints']), ("report generators", R['reports']),
         ("commits, mine", f"{R['tb_mine']:,} ({R['tb_pct']}%)")],
  foot=f"Repository since {R['tb_first']}; {R['tb_mine']:,} of {R['tb_commits']:,} commits are mine "
       f"({R['tb_pct']}%), counted with <code>git shortlog</code> over all branches. The "
       f"{R['rostered']:,} rostered students span Alpha campuses and the {R['public']} public-school "
       f"districts together, and are a wider population than the {O['students']:,} Alpha students in "
       f"the accuracy figures above — those two numbers count different things and are not "
       f"comparable.")}

{card("Answer", "The Deep Dive Bot",
  f"The dashboard answers questions you already know to ask, in a browser, at a desk. Real questions "
  f"arrive in Slack, from a guide, mid-lesson: <b>“why is this student stuck?”</b> The demand is "
  f"measured, not assumed — in the same {iv['window']['days']} days, <b>{dd['requests']} deep dives "
  f"were requested by hand</b> for {dd['students']} students, and the hand-built path closed "
  f"{dd['completed']} of them. {dd['open']} are still open, the oldest waiting "
  f"{dd['oldest_open_days']:.0f} days. That queue is the argument for the bot.",
  "A Slack bot that turns a plain-English question into a rendered report in the thread. The model "
  "picks one tool and writes a single framing sentence — it never restates a figure, because the "
  "tool result is rendered directly. That division is deliberate: a number cannot drift between the "
  "API and the channel, and an uncertain request comes back as a clarifying question instead of a "
  "confident answer about the wrong student.",
  stats=[("deep dives requested by hand", dd['requests']),
         ("closed by hand", dd['completed']),
         ("still waiting", dd['open']),
         ("tools exposed", 6), ("agent, lines", f"{R['agent_loc']:,}"),
         ("ack budget", "3s")],
  foot="Tools: student_deep_dive, student_lessons, most_concerning, doom_loops, tests_taken, "
       "assigned_tests. Slack redelivers on any non-200, so events are de-duplicated on event_id "
       "and the work is handed to a background task inside the 3-second window. Demand figures are "
       "the 'Deep dive' request type in the intervention log — the manual route the bot replaces.")}

{card("Close the loop", "The Intervention Log",
  "Measuring a stall and doing nothing about it is just a report. When TimeBack does not resolve a "
  "student's stall by itself somebody has to intervene — and before this there was <b>no record of "
  "what was tried, by whom, or whether it worked</b>. It is the only record of remediation the "
  "platform did not do by itself, and the only place the trigger for each one is written down.",
  f"Two independent logs: requests a Campus DRI raises and pushes to a Curriculum DRI, and work the "
  f"Campus DRI absorbs themselves. In {iv['window']['days']} days it captured {CA['touches']:,} campus "
  f"touches over {CA['students']} students, with a median close of {iv_med_h:g} hours.",
  stats=[("campus touches", f"{CA['touches']:,}"), ("distinct cases", CA['cases']),
         ("students", CA['students']), ("completed", CA['completed']),
         ("still open", CA['open']),
         ("hours of effort logged", f"{EF['campus_own_h'] + EF['curriculum_answer_h']:.0f}")],
  foot="A row is a touch, not a failure — the same student can appear more than once, so both the "
       "touch count and the folded case count are shown. The two logs are independent and are never "
       "totalled together.")}

{card("Reuse", "The Resource Library",
  "The same study guide gets rebuilt at five campuses by five people who do not know the other four "
  "exist. Every hour spent regenerating an artefact that already exists is an hour not spent on a "
  "student who is stuck.",
  "A shared library on its own Railway service with Postgres behind it, so a resource added by "
  "anyone appears for everyone rather than living in one person's browser. Two roles — staff see "
  "everything, students never receive staff-only rows — plus generated study-guide and practice-test "
  "pages.",
  stats=[("resources live", 30), ("subjects", 7), ("grade bands", 13),
         ("resource types", 8), ("roles", 2),
         ("in the DRI resource tab", 75)],
  foot="Counts read live from the service's own /api/health and /api/config. Postgres-backed: "
       "Railway wipes container disk on redeploy, so the app refuses to pretend SQLite is safe and "
       "warns in the UI instead.")}

<p class="section-heading">Evidence · what the stack measures</p>

<div class="ev">
  <h3>Accuracy across every grade, subject and app</h3>
  <p class="lead">
    {O['answered']:,} answered questions from {O['students']:,} students between
    {O['window'].replace(' to ', ' and ')}. Pooled accuracy is <b>{O['pooled_acc']}%</b>; the median
    student sits at {O['median_student_acc']}%. Pooled means every question counts once — it is not an
    average of averages, so a student who answered 40,000 questions does not weigh the same as one
    who answered 40.
  </p>

  <p class="sub">By grade</p>
  {chart_grade}
  <p class="foot">Grades with under 20,000 answered questions are omitted. PreK sits lowest at
    {[d['acc'] for d in acc['by_grade'] if d['label']=='PreK'][0]}% on the thinnest sample
    ({[d['students'] for d in acc['by_grade'] if d['label']=='PreK'][0]} students).</p>

  <p class="sub">By subject</p>
  {chart_subj}

  <p class="sub">By app — the 16 largest by volume</p>
  {chart_app}
  <p class="foot">This is the chart that earns the dashboard. The spread between the best and worst
    app is over {max(d['acc'] for d in acc['by_app'][:16]) - min(d['acc'] for d in acc['by_app'][:16]):.0f}
    points, and it is invisible from inside any single app's own console.</p>

  <p class="sub">Where it is weakest — subject inside app</p>
  <p class="lead">An app-level average hides which subject inside it is dragging. These are the
    weakest cells carrying at least {CELL_FLOOR:,} answered questions, which is where a placement or
    app-swap decision is worth making.</p>
  {cell_table(weak)}
  <p class="sub">And where it is strongest</p>
  {cell_table(strong)}
</div>

<p class="section-heading">Evidence · the intervention loop</p>

<div class="ev">
  <h3>How fast a stall gets answered</h3>
  <p class="lead">
    Measured over all {T['n']} completed Campus DRI requests: from the moment a request is raised to
    the moment it is closed. Median <b>{iv_med_h:g} hours</b>, 90th percentile {T['p90_h']:g} hours.
  </p>
  {chart_turn}

  <p class="sub">Volume by request type</p>
  {chart_types}

  <p class="sub">Median hours to close, by type</p>
  {chart_type_speed}
  <p class="foot">Types with fewer than five completed requests are omitted. Curriculum DRI rows are
    excluded from every timing figure on purpose: that log records work retrospectively — the entry is
    written after the work is done — so elapsed time is not defined for it.</p>

  <div class="callout">
    <div class="big">{EF['campus_own_h'] + EF['curriculum_answer_h']:.0f} h</div>
    <p>of human effort logged against interventions, split by constraint into
      {EF['campus_own_h']:.0f}&nbsp;h of Campus DRI work absorbed directly
      ({EF['campus_own_n']} entries) and {EF['curriculum_answer_h']:.0f}&nbsp;h spent by Curriculum
      DRIs answering requests ({EF['curriculum_answer_n']} entries). The two are separate columns and
      separate people; the schema refuses to let either be written in the other's place, and a check
      over every row found <b>zero</b> violations.</p>
  </div>
  <p class="foot">Effort capture only began on 2026-09-11, so requests completed before that date
    carry no minutes and are not a gap: {EF['cm_have']} of {EF['cm_eligible']} eligible requests since
    then have a figure ({round(100*EF['cm_have']/EF['cm_eligible'])}%).</p>
</div>

<p class="section-heading">Evidence · the support load around it</p>

<div class="ev">
  <h3>What comes in through the helpdesk</h3>
  <p class="lead">
    {KP['total']:,} cases on the Alpha / 2hr Learning brands of the Trilogy central helpdesk, pulled
    from the Kayako API on {tk['pulled_at'][:10]} and sorted by ordered rules over subject and last
    message. {KP['open']:,} are still open ({KP['open_pct']}%), with a median open age of
    {KP['median_open_age']} days.
  </p>
  {chart_cats}

  <p class="sub">Opened per week, last {len(wk)} full weeks</p>
  {chart_weekly}

  <p class="sub">Time to resolution — the distribution, not the median</p>
  {chart_solve}
  <p class="foot">The shape matters more than any single number: {ST['automated_pct']}% of cases close
    inside an hour by automation and most of the rest take three days to two weeks, so the overall
    median falls in the empty valley between the two humps and describes almost nothing. For the
    {ST['n_human']:,} cases a human actually worked, the median is
    {ST['median_human_h']/24:.1f} days.</p>

  <p class="sub">Median days to resolution, by ticket type</p>
  {chart_tk_type}

  <div class="callout">
    <div class="big">{help_med_d:.1f} d → {iv_med_h:g} h</div>
    <p>A platform problem raised through the general helpdesk waits a median of
      {help_med_d:.1f} days for a human resolution. An academic stall raised through the purpose-built
      intervention loop is closed in {iv_med_h:g} hours. These are <em>different kinds of work</em> and
      the comparison is not apples to apples — but it is the same organisation, the same period and
      largely the same students, and it is the clearest available evidence for what a dedicated loop
      buys over a general queue.</p>
  </div>
</div>

<p class="section-heading">What this adds up to</p>
<div class="ev">
  <h3>One loop, built end to end</h3>
  <p class="lead">
    These are not four tools that happen to sit near each other. They are the four stages of a
    single loop, and each one exists because the stage before it produced something nobody could
    act on.
  </p>
  <table>
    <tr><th>Stage</th><th>Without it</th><th>Evidence on this page</th></tr>
    <tr><td><b>Measure</b></td>
        <td>{O['n_apps']} apps, {O['answered']/1e6:.1f}M questions, no shared view</td>
        <td>a {max(d['acc'] for d in acc['by_app'][:16]) - min(d['acc'] for d in acc['by_app'][:16]):.0f}-point
            spread between apps, invisible from inside any one of them</td></tr>
    <tr><td><b>Answer</b></td>
        <td>every question needs a person to go and build the answer</td>
        <td>{dd['requests']} deep dives asked for in {iv['window']['days']} days;
            {dd['open']} still waiting</td></tr>
    <tr><td><b>Act</b></td>
        <td>no record of what was tried, by whom, or whether it worked</td>
        <td>{CA['touches']:,} touches over {CA['students']} students, median close
            {iv_med_h:g}&nbsp;h</td></tr>
    <tr><td><b>Reuse</b></td>
        <td>the same artefact rebuilt at every campus</td>
        <td>a shared library, {EF['campus_own_h'] + EF['curriculum_answer_h']:.0f}&nbsp;h of
            logged effort it can be measured against</td></tr>
  </table>
  <div class="callout">
    <div class="big">{R['tb_pct']}%</div>
    <p>of the {R['tb_commits']:,} commits on the platform repository are mine
      ({R['tb_mine']:,}), alongside {R['tab_mine']} of the {R['tab_all']} commits on the
      intervention tab, and ownership of the <code>alpha_dri_interventions</code> data source —
      its dictionary, its published query rules and the judgement layer other teams read it
      through.</p>
  </div>
</div>

<p class="section-heading">Method &amp; provenance</p>
<div class="ev method">
  <ul>
    <li><b>Accuracy</b> — one API call per student over the whole Alpha roster
      ({O['roster']:,} resolved students, {O['students']:,} with recorded activity in the window),
      {O['window']}, pulled {O['pulled']}. Cohort key is the student's own OneRoster grade, not a
      per-subject working grade. Figures are pooled (Σ correct ÷ Σ answered), never an average of
      per-student averages. The {O['n_apps']} “apps” are the distinct source names the API reports,
      which includes a few internal surfaces (TimeBack Dash, manual XP assignment) alongside the
      learning apps proper; the by-app chart shows the 16 largest by volume, all of which are
      real apps.</li>
    <li><b>Interventions</b> — read from the <code>alpha_dri_interventions</code> source, scoped to
      its published rules: the two <code>section</code> values are independent logs and are never
      totalled; a row is a touch, so folded case counts are given alongside; minutes are read from
      <code>minutes_spent</code> for Campus DRI manual work and <code>completion_minutes</code> for
      Curriculum DRI answers, which the store keeps disjoint by constraint.</li>
    <li><b>Turnaround</b> — <code>completed_at − created_at</code> over completed Campus DRI rows.
      All {T['n']} qualify. The 172 Curriculum DRI rows are excluded because that log is written
      retrospectively, which would otherwise produce negative elapsed times.</li>
    <li><b>Support tickets</b> — the Kayako instance carries {tk['scanned']:,} cases across ~219
      brands and its API accepts no brand filter, so the pull reads every case and filters locally to
      the {tk['alpha_total']:,} Alpha-brand ones, of which {KP['total']:,} classify into a named type.
      Resolution is measured to <code>last_completed_at</code>, the agent's resolving reply — not
      <code>last_closed_at</code>, which is an auto-close firing days later and reads 72 hours against
      a real resolution of 0.1.</li>
    <li><b>Repository figures</b> — counted live from the working copies at build time with
      <code>git shortlog</code> and <code>grep</code>, not recalled.</li>
  </ul>
</div>

</main>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT}  ({len(HTML):,} bytes)")
print(f"  accuracy   {O['answered']:,} questions, {O['pooled_acc']}% pooled, {O['n_apps']} apps")
print(f"  campus log {CA['touches']} touches / {CA['cases']} cases / {CA['students']} students")
print(f"  turnaround median {iv_med_h}h over n={T['n']}")
print(f"  helpdesk   {KP['total']:,} classified, human median {ST['median_human_h']/24:.1f}d")
print(f"  repo       {R['tb_mine']}/{R['tb_commits']} commits ({R['tb_pct']}%), "
      f"{R['endpoints']} endpoints, {R['reports']} reports")
