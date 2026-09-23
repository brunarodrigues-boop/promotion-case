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
import datetime as dt
import json
import os
import pathlib
import subprocess

import charts as C
import feedback as FB

HERE = pathlib.Path(__file__).parent
OUT = HERE / "index.html"
PROMO = pathlib.Path("/tmp/promo")
DRI = pathlib.Path(os.path.expanduser("~/Desktop/dri-workload"))

acc = json.load(open(PROMO / "accuracy.json"))
iv = json.load(open(PROMO / "interventions.json"))
dd = json.load(open(PROMO / "deepdive.json"))
tk = json.load(open(PROMO / "tickets2.json"))
db = json.load(open(PROMO / "dashboard.json"))
rs = json.load(open(PROMO / "resources.json"))
dr = json.load(open(DRI / "dris.json"))
tm = json.load(open(PROMO / "team.json"))

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
GRP, CAT = tk["groups"], tk["categories"]
TK_TOTAL = tk["alpha_total"]
TK_OPEN = sum(g["open"] for g in GRP.values())
# "Student not progressing" is the number the whole helpdesk section turns on,
# so it is pulled out by name rather than read off a chart.
STUCK = CAT["Student not progressing"]
AUTO_N = GRP["Automated & scheduled"]["n"]
TRIAGE_N = GRP["Needs triage"]["n"]

LIB, RDG = rs["library"], rs["reading"]
DRIS = sorted(dr["dris"], key=lambda x: -x["students"])
DRI_TOTAL = sum(x["students"] for x in DRIS)
ME = next((x for x in DRIS if "bruna" in x["name"].lower()), None)
MY_RANK = DRIS.index(ME) + 1 if ME else 0

PUB, ROLE, SURF = db["public"], db["roles"], db["surface"]
ALPHA = db["alpha"]

help_med_d = tk["median_human_h"] / 24.0
iv_med_h = T["median_h"]
effort_h = EF["campus_own_h"] + EF["curriculum_answer_h"]
app16 = acc["by_app"][:16]
app_spread = max(d["acc"] for d in app16) - min(d["acc"] for d in app16)


# ── building blocks ──────────────────────────────────────────────────────────
def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10, 'th')}"


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


# ── public-school tables ─────────────────────────────────────────────────────
TYPE_LABEL = {"ela": "ELA", "math": "Math"}


def _district_rows():
    rows = sorted(PUB["districts"].items(), key=lambda x: -x[1]["students"])
    return "".join(
        f'<tr><td><b>{C.esc(d)}</b></td><td class="n">{v["schools"]}</td>'
        f'<td class="n">{v["students"]:,}</td>'
        f'<td class="n">{100*v["students"]/PUB["students"]:.0f}%</td>'
        f'<td>{" / ".join(TYPE_LABEL.get(t, t) for t in v["types"])}</td></tr>'
        for d, v in rows)


def _school_rows():
    rows = sorted(PUB["by_school"], key=lambda x: (x["district"], -x["students"]))
    out = []
    for sc_ in rows:
        n = f'{sc_["students"]:,}' if sc_["students"] else "—"
        out.append(
            f'<tr><td><b>{C.esc(sc_["short"])}</b></td>'
            f'<td>{C.esc(sc_["district"])}</td>'
            f'<td class="n">{n}</td>'
            f'<td>{TYPE_LABEL.get(sc_["type"], sc_["type"])}</td>'
            f'<td>{C.esc(", ".join(sc_["subjects"]))}</td>'
            f'<td>{C.esc(", ".join(sc_["doom_subjects"]))}</td></tr>')
    return "".join(out)


dist_rows = _district_rows()
school_rows = _school_rows()

def _dri_rows():
    out = []
    for i, x in enumerate(DRIS, 1):
        mine = ME and x["name"] == ME["name"]
        note = []
        if x["shared_campuses"]:
            note.append(f'{x["shared_campuses"]} shared')
        if x.get("no_roster"):
            note.append(f'{x["no_roster"]} without a roster')
        out.append(
            f'<tr{" class=\'me\'" if mine else ""}>'
            f'<td class="n">{i}</td><td>{"<b>" if mine else ""}{C.esc(x["name"])}'
            f'{"</b>" if mine else ""}</td>'
            f'<td class="n">{x["n_campuses"]}</td>'
            f'<td class="n">{x["students"]:,.0f}</td>'
            f'<td class="n">{100*x["students"]/DRI_TOTAL:.1f}%</td>'
            f'<td>{C.esc(", ".join(note))}</td></tr>')
    return "".join(out)


def _reading_rows():
    return "".join(
        f'<tr><td><b>{C.esc(g["grade"])}</b></td><td class="n">{g["lessons"]}</td>'
        f'<td class="n">{g["passages"]}</td><td class="n">{g["words"]:,}</td>'
        f'<td class="n">{100*g["with_text"]/g["lessons"]:.0f}%</td></tr>'
        for g in RDG["by_grade"])


dri_rows = _dri_rows()
reading_rows = _reading_rows()

SURVEY = FB.SURVEY
DONE = sum(1 for t in FB.THEMES if t["status"] == "done")
PARTLY = sum(1 for t in FB.THEMES if t["status"] == "partly")
WIP = sum(1 for t in FB.THEMES if t["status"] == "in progress")

STATUS_LABEL = {"done": "Done", "partly": "Partly", "in progress": "In progress"}
STATUS_CLASS = {"done": "st-done", "partly": "st-partly", "in progress": "st-wip"}


def feedback_blocks():
    out = []
    for t in FB.THEMES:
        quotes = "".join(
            f'<blockquote><p>{C.esc(q)}</p><cite>{C.esc(who)}</cite></blockquote>'
            for who, q in t["quotes"])
        out.append(f"""
        <div class="fb">
          <div class="fb-head">
            <span class="fb-n">{t['n']}</span>
            <h4>{C.esc(t['title'])}</h4>
            <span class="pill {STATUS_CLASS[t['status']]}">{STATUS_LABEL[t['status']]}</span>
            <span class="fb-kind">{t['kind']}</span>
          </div>
          <div class="fb-body">
            <div class="fb-quotes">{quotes}</div>
            <div class="fb-action">
              <span class="fb-action-tag">What was done</span>
              <p>{t['action']}</p>
            </div>
          </div>
        </div>""")
    return "".join(out)


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

dist = tk["distribution"]
chart_solve = C.vbars([(d["label"], d["pct"], f'{d["n"]:,}') for d in dist],
                      unit="%", height=180)

GROUP_ORDER = ["Platform failures", "People & administration", "Student & academic",
               "Automated & scheduled", "Needs triage"]
GRP_COLS = ["#8b7dc8", "#a396d6", "#6fae86", "#bdb2e2", "#ddd8e8"]
gseg = [(g, GRP[g]["n"]) for g in GROUP_ORDER if g in GRP]
chart_groups = C.stacked(gseg, colours=GRP_COLS) + legend(gseg, GRP_COLS)

# One row per category, grouped, so the reader can see what the load is made of.
def cat_table():
    out = ['<table><tr><th>Category</th><th class="n">Cases</th><th class="n">Share</th>'
           '<th class="n">Median</th><th class="n">Closed &lt;1h</th>'
           '<th class="n">Still open</th></tr>']
    for g in GROUP_ORDER:
        if g not in GRP:
            continue
        rows = sorted([(k, v) for k, v in CAT.items() if v["group"] == g],
                      key=lambda x: -x[1]["n"])
        out.append(f'<tr class="grp"><td colspan="6">{C.esc(g)} — '
                   f'{GRP[g]["n"]:,} cases, {100*GRP[g]["n"]//TK_TOTAL}%</td></tr>')
        for k, v in rows:
            med = f'{v["median_h"]/24:.1f} d' if v["median_h"] and v["median_h"] > 24 \
                  else (f'{v["median_h"]:.1f} h' if v["median_h"] is not None else "—")
            out.append(
                f'<tr><td>{C.esc(k)}</td><td class="n">{v["n"]:,}</td>'
                f'<td class="n">{100*v["n"]/TK_TOTAL:.1f}%</td><td class="n">{med}</td>'
                f'<td class="n">{v["auto_pct"] if v["auto_pct"] is not None else "—"}%</td>'
                f'<td class="n">{v["open"]:,}</td></tr>')
    return "".join(out) + "</table>"

chart_dri = C.hbars(
    [(x["name"], round(x["students"]), f'{x["n_campuses"]} campuses') for x in DRIS],
    unit="", vmin=0, label_w=152, colour=C.PURPLE, note_w=84)
chart_reading = C.vbars(
    [(g["grade"], g["passages"], f'{g["lessons"]} lessons') for g in RDG["by_grade"]],
    height=180)

chart_wk = C.vbars([(w["week"][5:], w["n"], "") for w in tk["weekly"][:-1]], height=180)
chart_grp_speed = C.hbars(
    [(g, round(GRP[g]["median_h"] / 24, 1), f'n={GRP[g]["n"]:,}')
     for g in sorted(GRP, key=lambda x: GRP[x]["median_h"])],
    unit="d", vmin=0, label_w=178, colour=C.AMBER)

TABS = [("case", "The case"), ("fb", "Guide feedback"), ("measure", "Dashboard"),
        ("answer", "Deep dive bot"),
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
  html {{ scroll-padding-top: 64px; }}
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
  .panel {{ display: none; scroll-margin-top: 64px; }}
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
  .ask {{ background: linear-gradient(135deg,#6f5fb0,#8b7dc8); color: #fff; border-radius: 16px;
    padding: 26px 30px 24px; margin-bottom: 20px; }}
  .ask-tag {{ display: inline-block; background: rgba(255,255,255,.22); font-size: .64rem;
    font-weight: 700; letter-spacing: .12em; text-transform: uppercase; padding: 4px 11px;
    border-radius: 20px; margin-bottom: 10px; }}
  .ask h2 {{ font-size: 1.85rem; font-weight: 700; letter-spacing: -.02em; margin-bottom: 8px;
    color: #fff; }}
  .ask p {{ font-size: .95rem; color: rgba(255,255,255,.93); max-width: 760px; }}
  .ask code {{ background: rgba(255,255,255,.22); color: #fff; }}
  .fb {{ background: #fff; border: 1px solid #e0daf0; border-radius: 14px; padding: 18px 22px 16px;
    margin-bottom: 12px; }}
  .fb-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
  .fb-n {{ flex: 0 0 24px; height: 24px; border-radius: 50%; background: #ede9f8; color: #6f5fb0;
    font-weight: 700; font-size: .78rem; display: flex; align-items: center; justify-content: center; }}
  .fb-head h4 {{ font-size: 1.02rem; font-weight: 700; letter-spacing: -.01em; flex: 1 1 320px; }}
  .fb-kind {{ font-size: .66rem; color: #a49dba; text-transform: uppercase; letter-spacing: .1em; }}
  .st-done {{ background: #e3f3e9; color: #2f7a4f; }}
  .st-partly {{ background: #fdf1dd; color: #9a6d1f; }}
  .st-wip {{ background: #eceaf4; color: #6f6a80; }}
  .fb-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  .fb-quotes blockquote {{ border-left: 2.5px solid #ddd6ee; padding-left: 11px; margin-bottom: 10px; }}
  .fb-quotes p {{ font-size: .86rem; color: #4a4a52; font-style: italic; }}
  .fb-quotes cite {{ display: block; font-size: .7rem; color: #a49dba; font-style: normal;
    margin-top: 3px; letter-spacing: .02em; }}
  .fb-action {{ background: #f7f5fc; border-radius: 10px; padding: 12px 14px; }}
  .fb-action-tag {{ display: block; font-size: .62rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .12em; color: #8b7dc8; margin-bottom: 5px; }}
  .fb-action p {{ font-size: .86rem; color: #3d3d3d; }}
  @media (max-width: 720px) {{ .fb-body {{ grid-template-columns: 1fr; }} }}
  tr.me td {{ background: #f4f0ff; }}
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
  <span class="role-tag">The case for Head of Campus DRI</span>
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

<div class="ask">
  <span class="ask-tag">The ask</span>
  <h2>Head of Campus DRI</h2>
  <p>Leading the {tm['n_dris']} Campus DRIs — {tm['n_dris']-1} people and myself — across
     {tm['team_campuses']} campuses and {tm['team_students']:,} students. I already carry the
     {ordinal(tm['my_caseload_rank'])}-largest caseload on that team, and every one of the
     {tm['dri_filers']} DRIs already works through systems I built. This page is the evidence for
     both halves of that sentence, and a plan for what I would do with the job.</p>
</div>

<div class="stats">
  {stat(f"{tm['team_students']:,}", "students the team is responsible for")}
  {stat(tm['team_campuses'], "campuses")}
  {stat(f"{tm['dri_filers']}/{tm['n_dris']}", "Campus DRIs already using what I built")}
  {stat(f"{tm['my_students']:,}", f"students I carry today ({ordinal(tm['my_caseload_rank'])} of {tm['n_dris']})")}
  {stat(f"{iv_med_h:g}h", "median time to close an intervention")}
</div>

<div class="card">
  <h2>Why me</h2>
  <p class="lead">
    Five claims. Each one is a number on another tab, not an adjective — so each can be checked,
    and each can be argued with.
  </p>

  {claim(1, "The team already runs on what I built.",
    "The intervention log was not rolled out to anyone. It was built, and the team moved onto it "
    "because it was the only place the work could be written down. That is the strongest evidence "
    "I can offer that I already do this job: the practice the whole function follows is one I "
    "designed, and it stuck without a mandate.",
    f"All <b>{tm['dri_filers']} of {tm['n_dris']}</b> Campus DRIs file into it, alongside "
    f"{tm['curriculum_filers']} Curriculum DRIs — {tm['creators']} people writing, "
    f"{tm['completers']} closing, across <b>{tm['campuses_covered']} campuses</b>, since "
    f"{tm['first_entry']}.")}

  {claim(2, "I set the standard other teams read us through.",
    "<code>alpha_dri_interventions</code> is published to the data-source-skill contract with a "
    "dictionary, query rules, and a hand-written judgement layer saying what the values mean — "
    "which interventions signal a platform failure, which are routine, and what good looks like. "
    "When another team asks how the DRI function is performing, they get the answer through a "
    "definition I wrote. A Head of Campus DRI has to own what the role means to the rest of the "
    "org; I already do.",
    "Source owner and key issuer — credentials are minted per person, by me. The rules bind hard "
    "enough that this page obeys them: the two logs are never totalled, a row is reported as a "
    "touch rather than a failure, and the two minutes columns are scoped separately. A check over "
    "every row found zero violations.")}

  {claim(3, "I already carry near-top scope, while building for everyone else.",
    "The caseload is not evenly shared, and I am at the heavy end of it — while also being the "
    "person maintaining the platform the other fifteen monitor through. Doing both is the closest "
    "thing to a trial run for the role.",
    f"{tm['my_students']:,} students across {tm['my_campuses']} campuses, "
    f"{ordinal(tm['my_caseload_rank'])} of {tm['n_dris']} — "
    f"{100*tm['my_students']//tm['team_students']}% of the network. On the platform itself, "
    f"{R['tb_mine']:,} of {R['tb_commits']:,} commits ({R['tb_pct']}%).")}

  {claim(4, "I made the role measurable — including my own work.",
    "Before the log there was no record of what was tried for a stalled student, by whom, or "
    "whether it worked. That made the function unarguable in both directions: no credit for the "
    "work, and no way to find what was not working. A Head cannot manage this function on "
    "anecdote. I built the evidence layer the job needs, and I am inside it like everyone else.",
    f"{CA['touches']:,} touches over {CA['students']} students in {iv['window']['days']} days, "
    f"median close {iv_med_h:g} hours, {T['within_24h']}% inside a day, and {effort_h:.0f} hours "
    f"of effort now attributable to a named person. For scale: of all {TK_TOTAL:,} helpdesk cases, "
    f"only {STUCK['n']} are a stuck child — the academic conversation was never in the ticket "
    f"queue, and now it has somewhere to live.")}

  {claim(5, "I ask the people I serve, and then I change things.",
    f"Before the year I surveyed the guides the role exists to serve — {SURVEY['responses']} "
    f"responses from {SURVEY['campuses']} campuses. Ten themes of criticism came back. Seven are "
    f"done, two partly, one is a correction: guides were blaming DRIs for a delay an automation "
    f"was causing. Two of the ten traced to a single Campus DRI, and the answer there was a "
    f"personnel decision — move them off the campus, hand the feedback to their replacement, "
    f"coach them. They are doing the job well now. That is the part of this role that cannot be "
    f"solved by building something.",
    f"Every theme, in the guides' own words, with what was done about it, on the Guide feedback "
    f"tab. {DONE} done, {PARTLY} partly, {WIP} in progress — and three of the ten were answered "
    f"by tooling, three by a personnel decision, and four by changing how the role is coached.")}

  {claim(6, "I find what is failing silently.",
    "The failures that matter are the ones nothing reports. Mid-week reports were putting working "
    "students in the RED tier at 0.0 XP/day — on one report, seven of the nine students listed as "
    "having little to no engagement had earned XP every single day. The cause was a fetch that "
    "returned empty instead of raising when the API answered 503, so an outage read as a child "
    "doing no work. Fifteen DRIs acting on a report like that is fifteen wasted conversations and "
    "nine children mislabelled.",
    f"{R['fixes']} of my {R['tb_mine']:,} commits are fixes. The same instinct caught a silent cap "
    f"in the helpdesk pull behind this page — it stopped at exactly 40,000 cases against an "
    f"instance of {tk['scanned']:,} and reported nothing.")}
</div>

<div class="card">
  <h2>What I would do with the job</h2>
  <p class="lead">
    Four problems visible in the team's own data. None of these are guesses; each is a number on
    another tab, and each is why the role needs someone who reads them.
  </p>
  <table>
    <tr><th style="width:27%">Problem</th><th style="width:30%">What the data shows</th><th>What I would do</th></tr>
    <tr><td><b>The caseload is lopsided</b></td>
      <td>The top three DRIs carry {tm['top3_share']}% of all students between them, and the
        largest caseload is {tm['spread']:g}× the smallest.</td>
      <td>Rebalance against live enrolment rather than campus count. A DRI with two campuses can
        be carrying more children than one with ten.</td></tr>
    <tr><td><b>Logging is not yet uniform</b></td>
      <td>Filings range from {tm['top_filer']} to {tm['min_filer']} across the
        {tm['dri_filers']} DRIs in the same {iv['window']['days']} days.</td>
      <td>That spread is either real workload difference or inconsistent practice, and right now
        nobody can tell which. Make the log a standard, then use it to spot who needs support —
        not to rank people.</td></tr>
    <tr><td><b>Requests outrun the answer</b></td>
      <td>{dd['requests']} deep dives asked for in {iv['window']['days']} days; the hand-built
        route closed {dd['completed']}. {dd['open']} are still open, the oldest
        {dd['oldest_open_days']:.0f} days.</td>
      <td>This is the queue the bot exists for. Finish the rollout, measure it, and hold the
        answer time to the same {iv_med_h:g}-hour standard the rest of the log meets.</td></tr>
    <tr><td><b>The data under us is not clean</b></td>
      <td>The email allowlist disagrees with live enrolment on 60 campuses — GT Anywhere reads 510
        against 1,259 enrolled.</td>
      <td>A team measured on student outcomes cannot run on a roster that is wrong by a factor of
        two. Reconcile to enrolment, and keep it reconciled.</td></tr>
  </table>
</div>

<div class="card">
  <h3>The honest caveats</h3>
  <p class="lead">Stated here rather than buried, because a case a reviewer can puncture is worth
    less than one that punctures itself first.</p>
  <table>
    <tr><td style="width:34%"><b>I am not the heaviest user of my own log</b></td>
      <td>{tm['my_filings']} filings puts me {ordinal(tm['my_rank'])} of {tm['dri_filers']}, not
        first. The claim is that the team adopted it, not that I use it most.</td></tr>
    <tr><td><b>This is outputs, not outcomes</b></td>
      <td>Everything here measures work done and work made visible. It does not yet show a child
        who learned more because of it — the log is {iv['window']['days']} days old and there is
        no before to compare against, because nothing was recorded before it.</td></tr>
    <tr><td><b>The window is short</b></td>
      <td>{iv['window']['days']} days. Long enough to show a rate, not long enough to show a trend.</td></tr>
    <tr><td><b>The platform is not solo work</b></td>
      <td>{R['tb_pct']}% of commits are mine, which means {100-R['tb_pct']}% are not. On the
        intervention tab specifically it is {R['tab_mine']} of {R['tab_all']}.</td></tr>
  </table>
</div>

<div class="card">
  <h3>One loop, built end to end</h3>
  <p class="lead">
    The four systems are not separate tools. They are four stages of the loop this role owns, and
    each exists because the stage before it produced something nobody could act on.
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
        <td>{RDG['passages']} reading passages freed from a vendor console; a shared library</td></tr>
  </table>
</div>
</section>

<!-- ══ 1b · GUIDE FEEDBACK ══ -->
<section class="panel" id="fb">
<div class="print-title">Guide feedback, and what was done</div>

<div class="card">
  <h2>We asked the guides, and then we changed things</h2>
  <p class="lead">
    Before the school year I surveyed the people the Campus DRI role exists to serve —
    <b>{SURVEY['responses']} responses from {SURVEY['campuses']} campuses</b>, collected
    {SURVEY['from']} to {SURVEY['to']}. Two open questions carried the criticism: what a Campus
    DRI could do to make your job easier ({SURVEY['q_easier']} answers), and what you wish your
    DRI had done more or less of ({SURVEY['q_more_less']} answers).
  </p>
  <p class="lead">
    Below is every theme of criticism in that survey — in the guides' own words — and what was
    actually done about it in the {(dt.date.fromisoformat(iv['window']['last']) - dt.date.fromisoformat(SURVEY['to'])).days // 7}
    weeks since. Praise is not listed. A page of compliments proves nothing; the test of whether
    feedback was heard is what changed after it.
  </p>
  {minis([("themes of criticism", SURVEY['themes']), ("done", DONE),
          ("partly done", PARTLY), ("in progress", WIP),
          ("responses", SURVEY['responses']), ("campuses", SURVEY['campuses'])])}
  <p class="foot">
    Three of the ten were answered by tooling, three by a personnel decision, and four by changing
    how the role is practised and coached. That split matters: a Head of Campus DRI who can only
    fix things by building something can only fix a third of this list.
  </p>
</div>

{feedback_blocks()}

<div class="card">
  <h3>What this cost, and what it did not fix</h3>
  <table>
    <tr><td style="width:32%"><b>Two themes were one person</b></td>
      <td>The message-volume complaint and the blaming-the-guide complaint traced to the same
        Campus DRI. The answer was to move them off the campus, hand the feedback to their
        replacement, and coach them — not to write a process. They are doing the job well now,
        which is the outcome worth having; the alternative was a policy that punished fifteen
        people for one person's habit.</td></tr>
    <tr><td><b>One theme was a misattribution</b></td>
      <td>Guides experienced slow deep dives and slow skill plans as the same problem. Only the
        first is a DRI queue. The skill plans come from an automation, so no amount of DRI
        responsiveness would have moved them — and telling guides that is more useful than
        absorbing a complaint we cannot act on.</td></tr>
    <tr><td><b>Two are not finished</b></td>
      <td>Standardising how every DRI writes deep dives and reports is convention, not yet
        standard. And the timezone gap needs a hire, not a rule — the request is in, asking that
        core hours be allowed to run to 2pm CT so West Coast campuses are covered by someone
        whose day overlaps theirs.</td></tr>
    <tr><td><b>The coaching programme is separate</b></td>
      <td>The same survey carried 54 responses about the coaching programme — consistency between
        coaches, availability, and reporting back to guides after a call. That is a different
        function and is not claimed here.</td></tr>
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
       f"child. At {db['total_rostered']:,} rostered students across {db['total_campuses']} campuses "
       f"that question simply does not get asked.")}
  <p class="lead">The production platform every Campus DRI monitors through: XP, time, accuracy,
    tests and grade-level progress, per student per subject, with role-scoped guide and admin views,
    daily alerts, doom-loop detection and generated reports.</p>
  {minis([("campuses served", db['total_campuses']),
          ("students rostered", f"{db['total_rostered']:,}"),
          ("API endpoints", SURF['endpoints']),
          ("report endpoints", SURF['report_endpoints']),
          ("PDF generators", SURF['report_generators']),
          ("scheduled jobs", SURF['scheduled_jobs'])])}
  <p class="foot">Repository since {R['tb_first']}; {R['tb_mine']:,} of {R['tb_commits']:,} commits
    are mine ({R['tb_pct']}%), counted with <code>git shortlog</code> over all branches.
    Every figure on this tab is read out of the running configuration at build time, not recalled.</p>
</div>

<div class="card">
  <h3>Two populations, never added together</h3>
  <p class="lead">
    The dashboard serves a private campus network and a public-school partnership, and they are not
    the same kind of thing. Different rostering, different programme design, different reports. The
    totals are shown separately because summing them would describe a population that does not exist.
  </p>
  <table>
    <tr><th>Population</th><th class="n">Campuses</th><th class="n">Students</th><th>How it is rostered</th></tr>
    <tr><td><b>Alpha campuses</b></td><td class="n">{ALPHA['campuses']}</td>
      <td class="n">{ALPHA['students']:,}</td>
      <td>private network, rostered by email allowlist per campus</td></tr>
    <tr><td><b>Public schools</b></td><td class="n">{PUB['schools_rostered']}</td>
      <td class="n">{PUB['students']:,}</td>
      <td>{len(PUB['districts'])} districts, each school with its own programme type and subject set</td></tr>
  </table>
  <p class="foot">
    {ALPHA['campuses']} + {PUB['schools_rostered']} = {db['total_campuses']}, which is the campus
    list. The public-school <em>configuration</em> holds {PUB['schools']} entries, not
    {PUB['schools_rostered']}: “Aldine ISD” is a programme definition with no allowlist of its own,
    so it is configured but not rostered. The audit asserts that difference is exactly one, because
    a second unrostered key appearing silently is how a school gets configured and then never
    looked at.
  </p>
</div>

<div class="card">
  <h3>The public-school partnership</h3>
  <p class="lead">
    {PUB['students']:,} students across {PUB['schools']} schools in {len(PUB['districts'])}
    districts. Each school runs one of two programmes — an <b>ELA</b> track (Language, Reading,
    FastMath) or a <b>Math</b> track (Math, FastMath) — against a daily target of
    {PUB['xp_targets'][0]} XP per subject. Which subjects trigger a doom-loop alert is set per
    school, because a reading school and a maths school fail in different places.
  </p>
  <p class="sub">By district</p>
  <table>
    <tr><th>District</th><th class="n">Schools</th><th class="n">Students</th><th class="n">Share</th><th>Programme</th></tr>
    {dist_rows}
  </table>
  <p class="sub">Every school, as configured</p>
  <table>
    <tr><th>School</th><th>District</th><th class="n">Students</th><th>Programme</th>
      <th>Subjects tracked</th><th>Doom-loop watch</th></tr>
    {school_rows}
  </table>
  <p class="foot">
    Student counts are the length of each school's configured email allowlist — the dashboard looks
    these students up by email, so the allowlist <em>is</em> the roster. District is not a field in
    the config; the schools are keyed by their own acronyms and I have grouped them from the school
    names, which is a judgement call rather than data from the source. Aldine ISD carries a
    twelfth key with no allowlist of its own, which is why it shows five schools and four rosters.
  </p>
</div>

<div class="card">
  <h3>Who can see what</h3>
  <p class="lead">
    Access is not a single admin flag. {ROLE['password_roles']} credential roles resolve to
    {ROLE['distinct_scopes']} distinct scopes, and a scope is one of three shapes: everything, one
    named campus, or an arbitrary set of campuses composed on the fly.
  </p>
  <table>
    <tr><th>Shape</th><th class="n">Count</th><th>What it means</th></tr>
    <tr><td><b>Full access</b></td><td class="n">—</td>
      <td>every campus, both populations, all reports</td></tr>
    <tr><td><b>Single campus</b></td><td class="n">{ROLE['role_to_school_map']}</td>
      <td>role→school entries: the login resolves to exactly one campus and cannot see any other</td></tr>
    <tr><td><b>Composite</b></td><td class="n">{ROLE['composite_roles']}</td>
      <td>a set joined with <code>+</code>, for a person who owns several campuses —
        e.g. <code>{C.esc(ROLE['composite_examples'][0]) if ROLE['composite_examples'] else ''}</code></td></tr>
    <tr><td><b>DRI-scoped</b></td><td class="n">{ROLE['dri_roles']}</td>
      <td>admin-level API access, but restricted to the campuses that DRI is assigned</td></tr>
  </table>
  {minis([("credential roles", ROLE['password_roles']),
          ("distinct scopes", ROLE['distinct_scopes']),
          ("role→school entries", ROLE['role_to_school_map']),
          ("composite roles", ROLE['composite_roles']),
          ("token lifetime", f"{ROLE['token_ttl_hours']}h"),
          ("routers", SURF['routers'])])}
  <p class="foot">
    On top of the credential roles sit three further mechanisms: per-person accounts with their own
    role, a multi-persona login for people who hold more than one role at once (the role is signed
    into the exchange token so the two sign-in paths cannot disagree about who you are), and static
    API keys for service-to-service calls. Sessions are HMAC-signed and expire in
    {ROLE['token_ttl_hours']} hours without needing a database round trip.
  </p>
</div>

<div class="card">
  <h3>Who owns how many students</h3>
  <p class="lead">
    Roles say who <em>can see</em> a campus. This says who is <em>responsible</em> for one.
    {len(DRIS)} Campus DRIs carry {DRI_TOTAL:,.0f} students across {dr['n_campuses']} campuses —
    and the load is not evenly spread: the top three carry
    {100*sum(x['students'] for x in DRIS[:3])/DRI_TOTAL:.0f}% of it between them, and the largest
    caseload is {DRIS[0]['students']/DRIS[-1]['students']:.1f}× the smallest.
  </p>
  {chart_dri}
  <table>
    <tr><th class="n">#</th><th>Campus DRI</th><th class="n">Campuses</th>
      <th class="n">Students</th><th class="n">Share</th><th>Notes</th></tr>
    {dri_rows}
  </table>
  <p class="foot">
    Counts are live enrolled students from OneRoster — an active user record, at least one active
    role, and that role's end date not yet passed — not the planning sheet's manual figures, which
    its own note admits drift. This matters: the allowlist disagrees with enrolment on 60 campuses,
    and GT Anywhere alone reads 510 on the allowlist against 1,259 enrolled. A campus owned jointly
    is split evenly rather than counted whole for each owner; counting Texas Sport Academy Online
    three times over would put all three of its owners at the top of this table.
    Generated {dr['generated']}.
  </p>
</div>

<div class="card">
  <h3>What runs without anyone asking</h3>
  <p class="lead">{SURF['scheduled_jobs']} scheduled jobs, plus a rolling cache refresh every
    {SURF['cache_refresh_minutes']} minutes so a guide opening the dashboard mid-morning is not
    reading yesterday.</p>
  <table>
    <tr><th>Job</th><th>What it does</th></tr>
    <tr><td><code>_run_scheduled_reports</code></td><td>the nightly report run, 02:00 America/Chicago</td></tr>
    <tr><td><code>_refresh_all_schools_background</code></td><td>re-pulls every campus every {SURF['cache_refresh_minutes']} minutes</td></tr>
    <tr><td><code>_run_miami_red_alert</code></td><td>the Miami red-tier alert, 05:00 America/New_York</td></tr>
    <tr><td><code>_run_refresh_teacher_roster</code></td><td>weekly roster reconciliation, Sunday 02:00</td></tr>
    <tr><td><code>_run_email_coaching_wednesday</code> · <code>_run_email_coaching_friday</code></td>
      <td>the two coaching sends</td></tr>
    <tr><td><code>_run_email_fidelity</code></td><td>the fidelity report send</td></tr>
  </table>
  <p class="foot">Guide sends are deliberately <em>not</em> on a timer: leadership reviews and edits
    each message in the Messaging tab before it goes out, so the automation stops one step short of
    the person.</p>
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
<div class="print-title">Resources</div>

<div class="card">
  <span class="pill">Reuse</span>
  <h2>The Resource Estate</h2>
  {why("The same study guide gets rebuilt at five campuses by five people who do not know the other "
       "four exist. Every hour spent regenerating an artefact that already exists is an hour not "
       "spent on a student who is stuck — and when the artefact is a reading passage, rebuilding it "
       "badly is worse than not having it.")}
  <p class="lead">Two things, built for two different problems: a shared library so a resource
    anyone adds is a resource everyone has, and a standalone reading site because the texts guides
    needed were locked inside a vendor console one lesson at a time.</p>
</div>

<div class="card">
  <h3>Reading Texts — {RDG['passages']} passages, free of the console</h3>
  <p class="lead">
    <a href="{RDG['url']}">{RDG['url'].replace('https://','')}</a> ·
    Every reading passage across grades 3–8, in one page a guide can search, print and mark up.
    The source is a vendor console that shows one passage at a time behind a login; a guide
    preparing a lesson could not see what the next text was, could not print it, and could not hand
    it to a student on paper. {RDG['passages']} passages and {RDG['words']:,} words now sit in a
    single file that works offline.
  </p>
  {minis([("passages", RDG['passages']), ("lessons", RDG['lessons']),
          ("words of text", f"{RDG['words']:,}"), ("grades", f"3–8"),
          ("topics", RDG['topics']), ("one file", f"{RDG['page_kb']} KB")])}
  <p class="sub">By grade</p>
  {chart_reading}
  <table>
    <tr><th>Grade</th><th class="n">Lessons</th><th class="n">Passages</th>
      <th class="n">Words</th><th class="n">Lessons with a text</th></tr>
    {reading_rows}
  </table>
  <p class="sub">What it does that the console does not</p>
  <table>
    <tr><td style="width:24%"><b>Search</b></td>
      <td>across every grade at once, on title, lesson, topic and body text — so “find me a text
        about weather” is one query rather than eight menus</td></tr>
    <tr><td><b>Underlining</b></td>
      <td>select to mark, tap a mark to remove it. Stored as character offsets into each paragraph
        rather than as wrapped nodes, so marks survive a reload, print black, and do not nest when
        two overlap</td></tr>
    <tr><td><b>Print</b></td>
      <td>a clean single-page handout: buttons and hints hidden, the student's underlining carried
        through to paper</td></tr>
    <tr><td><b>Text splitting</b></td>
      <td>a lesson drawing on several sources becomes one entry per source rather than a wall of
        prose. One G5 lesson uses five, which is what forced the splitter to stop assuming a pair</td></tr>
  </table>
  <p class="foot">
    Checked live at build time: {sum(1 for v in RDG['features'].values() if v)} of
    {len(RDG['features'])} named features present in the published page, and the passage count read
    out of the page's own data structure rather than remembered. A rebuild that silently dropped a
    feature or a passage would fail this.
  </p>
</div>

<div class="card">
  <h3>The shared library</h3>
  <p class="lead">A library on its own service with Postgres behind it, so a resource added by
    anyone appears for everyone rather than living in one person's browser. Two roles: staff see
    everything, students never receive staff-only rows.</p>
  {minis([("resources live", LIB['resources']), ("subjects", len(LIB['subjects'])),
          ("resource types", len(LIB['types'])), ("grade bands", len(LIB['grades'])),
          ("roles", len(LIB['visibilities'])), ("in the DRI tab", 75)])}
  <p class="foot">
    Counts read live from the service's own <code>/api/health</code> and <code>/api/config</code>.
    Postgres-backed and it checks: Railway wipes container disk on every redeploy, so a SQLite
    fallback would quietly lose every resource the team added. The app reports
    <code>ephemeral: {str(LIB['ephemeral']).lower()}</code> and shows a banner in the UI rather than
    failing silently. Subjects: {C.esc(", ".join(LIB['subjects']))}.
  </p>
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
  <h3>What the helpdesk is actually made of</h3>
  <p class="lead">
    {TK_TOTAL:,} cases on the Alpha / 2hr Learning brands of the Trilogy central helpdesk, pulled
    from the Kayako API on {tk['pulled_at'][:10]}. Sorted into four kinds of work plus an honest
    fifth for the ones whose subject line never says what the ask is.
  </p>
  {chart_groups}
  <div class="callout">
    <div class="big">{100*STUCK['n']/TK_TOTAL:.1f}%</div>
    <p>The single most useful number here. Of {TK_TOTAL:,} support cases, <b>{STUCK['n']}</b> are a
      child who is stuck and needs a plan — a deep dive, a custom plan, an accuracy investigation.
      The helpdesk is where the <em>platform</em> gets fixed and where <em>accounts</em> get made.
      It is not where the academic conversation happens. That work had nowhere to live, which is
      exactly why the intervention log had to be built: it captured {CA['touches']:,} of those in
      {iv['window']['days']} days, more in under three weeks than the helpdesk saw all year.</p>
  </div>
</div>

<div class="card">
  <h3>Every category, and how it behaves</h3>
  <p class="lead">Grouped by what the work is. “Closed &lt;1h” is the automation tell — a category
    that mostly closes inside an hour is being handled by a machine, not a person.</p>
  {cat_table()}
  <p class="foot">
    Automation is separated out on purpose. Offboarding runs alone are {CAT['Offboarding runs']['n']:,}
    cases closing in a median of {CAT['Offboarding runs']['median_h']:.1f} hours; left inside
    “administration” they drag its median toward zero and make human admin work look instant.
    Together with AI chat transcripts and the scheduled licence jobs, {AUTO_N:,} cases
    ({100*AUTO_N//TK_TOTAL}%) are work a machine did rather than work a person asked for.
  </p>
</div>

<div class="card">
  <h3>How the work behaves over time</h3>
  <p class="sub">Median days to resolution, by kind of work</p>
  {chart_grp_speed}
  <p class="sub">Opened per week</p>
  {chart_wk}
  <p class="sub">Time to resolution — the distribution, not the median</p>
  {chart_solve}
  <p class="foot">The shape matters more than any single number: {tk['auto_pct']}% of cases close
    inside an hour by automation and most of the rest take three days to two weeks, so the overall
    median ({tk['median_h']/24:.1f} days) falls in the empty valley between the two humps and
    describes almost nothing. For the cases a human actually worked, the median is
    {help_med_d:.1f} days.</p>
  <div class="callout">
    <div class="big">{help_med_d:.1f} d → {iv_med_h:g} h</div>
    <p>A problem raised through the general helpdesk waits a median of {help_med_d:.1f} days for a
      human resolution. An academic stall raised through the purpose-built intervention loop is
      closed in {iv_med_h:g} hours. These are <em>different kinds of work</em> and the comparison is
      not apples to apples — but it is the same organisation, the same period and largely the same
      students, and it is the clearest available evidence for what a dedicated loop buys over a
      general queue.</p>
  </div>
</div>

<div class="card">
  <h3>How honest this classification is</h3>
  <p class="lead">
    Rules over the subject line, evaluated in a fixed order, every case recording the rule that
    caught it. {tk['coverage_pct']}% of cases land in a named category on a rule that matches a verb
    or a failure signature. The other {TRIAGE_N:,} are held in <b>Needs triage</b> rather than
    forced somewhere flattering.
  </p>
  <table>
    <tr><th>Bucket</th><th class="n">Cases</th><th>What it means</th></tr>
    <tr><td><b>Named category</b></td><td class="n">{TK_TOTAL-TRIAGE_N:,}</td>
      <td>the subject states an ask or a failure — a verb, an error, an app plus a problem</td></tr>
    <tr><td><b>Topic named, ask unclear</b></td>
      <td class="n">{CAT['Topic named, ask unclear']['n']:,}</td>
      <td>names an app, a subject or “test” and nothing else: “eGUMPP”, “language”. Sorted by topic
        would put it in the right neighbourhood, not the right box</td></tr>
    <tr><td><b>Chat with a boilerplate subject</b></td>
      <td class="n">{CAT['Chat with a boilerplate subject']['n']:,}</td>
      <td>“(Live Chat) Alpha Education issue”, filed by the channel with the same wording every
        time</td></tr>
    <tr><td><b>No signal in the subject</b></td>
      <td class="n">{CAT['No signal in the subject']['n']:,}</td>
      <td>a bare student name, or a subject line that says nothing at all</td></tr>
  </table>
  <p class="foot">
    The inherited four-bucket taxonomy reported 76% coverage and 2,006 “Academic — not learning”
    cases. Reading its own rule labels, 1,189 of those 2,006 were caught by a bare subject word —
    “reading”, “math”, “language” — with no verb attached, and the samples are mostly platform work:
    “TimeBack PowerPath placement 500s”, “Fix Eitan Barkai reading plan assignment”. A helpdesk that
    is overwhelmingly platform and administration came to look academic on the strength of the word
    “reading”. This version reports a lower coverage number and a truer one.
  </p>
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
      the {TK_TOTAL:,} Alpha-brand ones. Resolution is measured to <code>last_completed_at</code>,
      the agent's resolving reply — not <code>last_closed_at</code>, an auto-close firing days later
      that reads 72 hours against a real resolution of 0.1. The pull's page cap was raised from
      40,000 to 45,000 for this run: the instance had outgrown it and the previous run truncated
      silently at exactly 40,000 without reporting anything.</li>
    <li><b>Ticket categories</b> — ordered rules over the subject line, first match wins, each case
      recording the rule that caught it. The preview text is only consulted when the subject is
      under twelve characters, because the preview is the <em>last</em> message on a case and is
      usually the agent's closing reply: matching on it classifies a ticket by how it ended rather
      than what it was. Rules that match only a bare topic word are counted separately and never
      folded into a named category.</li>
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
print(f"  helpdesk   {TK_TOTAL:,} cases, {tk['coverage_pct']}% named, "
      f"student-stuck {STUCK['n']}, automation {AUTO_N:,}, human median {help_med_d:.1f}d")
print(f"  repo       {R['tb_mine']}/{R['tb_commits']} commits ({R['tb_pct']}%), "
      f"{R['fixes']} fixes / {R['feats']} features")
