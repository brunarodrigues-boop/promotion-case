"""Sort the helpdesk into what the work actually is, not just where it landed.

The question this answers is the one a reader asks first: how much of the
support load is *the platform failing* and how much is *a child who needs a
decision*? Those are different problems with different owners, and the
inherited four-bucket split could not tell them apart — it put 3,430 of 14,403
cases in "Other", which is not a taxonomy, it is a shrug.

Three groups, each with its own categories:

  Platform & automation   the tool broke, or a scheduled job ran
  Student & academic      a child needs a decision, a test, or a plan
  People & administration accounts, enrolment, kit, money

ORDER IS THE DESIGN, and the order is deliberate:

  1. Automated records first. "AI chat conversation with ..." is a transcript
     the bot filed, not a request anyone made. Left later in the order it gets
     caught by whatever word happens to appear in the conversation.
  2. Recurring automation next. "Weekly VocabLoco deactivation" names an app
     and would otherwise read as an app bug; it is a scheduled licence job.
  3. Money and kit, because "declined Ramp reimbursement" matches the bug rule
     on "declined" and a travel expense is not a platform failure.
  4. Test verbs, because "Invalidate Alpha ELA STAAR G5" is a test request
     whatever else it mentions.
  5. Platform failure, so "Reading progression assignment failure" is a fault
     that happens to name a subject rather than a struggling student.
  6. Academic, then administration last: "offboard" is unambiguous and rare
     enough not to need priority.

Every case carries the rule that caught it, so any row can be argued with.

Reads ~/Desktop/dri-workload/tickets_raw.json, writes /tmp/promo/tickets2.json.
"""
import collections
import datetime as dt
import json
import os
import re
import statistics

RAW = os.path.expanduser("~/Desktop/dri-workload/tickets_raw.json")
OUT = "/tmp/promo/tickets2.json"

TODAY = dt.date.today()
# status arrives as an id; the names live in the pull's own lookup table
OPEN_STATUSES = {"New", "Open", "Pending", "Hold"}

APPS = (r"lalilo|freckle|moby ?max|anton|alpha ?read|alpha ?write|alpha ?phonics|"
        r"alpha ?literacy|alpha ?math|alpha ?learn|alpha ?science|zearn|vocab ?loco|"
        r"vocaboloco|membean|edia|egumpp|fast ?math|math ?raiders|math ?academy|"
        r"happy ?numbers|mentava|edmentum|incept|amira|clear ?fluency|duolingo|"
        r"speechify|studyreel|ixl|khan|alpha ?test|timeback|tb dash|scribble|literably")

# Nouns that appear in both singular and plural. Writing \bassignment\b was a
# real bug: it never matched "missing MobyMax assignments", and several hundred
# cases fell through to Unclassified on the letter s alone.
CONTENT = r"(?:lesson|course|class|assignment|content|curriculum|unit|skill|module|activit(?:y|ies))s?"
SUBJECT = r"(?:math|reading|language|science|writing|vocab\w*|handwriting|social studies|phonics|spelling|fastmath|fast math)"
ASSESS  = r"(?:tests?|exams?|assessments?|staar|\bmap\b|quiz(?:zes)?|diagnostics?)"

# (group, category, rule name, pattern) — evaluated top to bottom, first wins.
RULES = [
    # ── 0 · work a machine did, not work a person asked for ─────────────────
    # These three are separated out because leaving them mixed in makes every
    # median lie. Offboarding runs alone are 1,291 cases closing in a median of
    # 0.14h; folded into "administration" they drag its median toward zero and
    # make human admin work look instant.
    ("Automated & scheduled", "AI chat transcript", "ai chat record",
     r"^ai chat conversation with|thanks for chatting earlier with our ai support|"
     r"anonymous ai chat user"),
    ("Automated & scheduled", "Offboarding runs", "bulk offboard job",
     r"^\s*(off|on).?board(ing)? student\b|^\s*(off|on).?board\b[^.]{0,40}"
     r"\bfrom all (systems|apps)"),
    ("Automated & scheduled", "Licence & seat automation", "scheduled licence run",
     r"weekly .{0,24}(deactivat|activat|licen[cs]|seat|pro |courseware)|"
     r"(deactivat|reactivat)\w* .{0,18}(licen[cs]|seat|account)s?\b|"
     r"licen[cs]e (renewal|expir|assign|removal)|seat (count|assign|remov)|"
     r"bulk (backfill|assign|import|upload|ticket)|backfill request"),

    # ── 2 · money and kit ────────────────────────────────────────────────────
    ("People & administration", "Finance & procurement", "finance",
     r"ops bot|ramp card|\bramp\b|reimburse|expense|invoice|purchase order|"
     r"\bpurchase\b|order not delivered|travel|amazon business|budget|payment|payroll"),
    ("People & administration", "Devices & equipment", "kit",
     r"\b(laptops?|chromebooks?|ipads?|headphones?|chargers?|monitors?|"
     r"device (request|swap|replace|broken|lost))\b|shipping|\brma\b|"
     r"goguardian|\broblox\b|web filter|site block|screen ?time"),

    # ── 3 · tests ────────────────────────────────────────────────────────────
    ("Student & academic", "Test administration", "test verb",
     rf"\b(assign|unlock|re-?assign|invalidat|re-?take|retake|reset|re-?open|unsubmit|"
     rf"re-?score|regrade|re-?grade|schedul|proctor)\w*\b[^.]{{0,40}}{ASSESS}|"
     rf"{ASSESS}[^.]{{0,40}}\b(assign|unlock|invalidat|re-?take|retake|reset|re-?open|"
     rf"unsubmit|re-?score|regrade|lock|unavailable|window)\w*\b|"
     r"test.?out|\bproctor\w*|\bmap (test|window|session|score)"),

    # ── 4 · the platform failed ──────────────────────────────────────────────
    ("Platform failures", "XP, credit & sync", "xp or sync",
     r"xp not (being )?(award|assign|updat|show|appear|giv|count|credit)|\bno xp\b|"
     r"not awarding|missing xp|xp (issue|discrepanc|missing|not|error|request|score|"
     r"correction|adjust)|didn'?t (get|receive) .{0,15}xp|\bxp\b[^.]{0,30}"
     r"(missing|wrong|incorrect|decreas|drop|negativ|not|discrepan|mismatch)|"
     r"(missing|wrong|incorrect|decreas|drop|negativ|discrepan|mismatch)[^.]{0,20}\bxp\b|"
     r"not sync|sync(ing)? (issue|problem|fail)|out of sync|metrics not|not updating|"
     r"not reflect|not turning green|isn'?t turning green|"
     r"progress (not|isn'?t) (show|updat|sav|record)|progress (deleted|lost|reset|missing)|"
     r"minutes not|time not (logg|record|count)|time (spent )?(reported|discrepan|"
     r"excessive|incorrect)|score (mismatch|discrepan|wrong|incorrect)"),
    ("Platform failures", "Content not delivered", "missing content",
     rf"(missing|\bno\b|not receiving|didn'?t (get|receive)|cannot (see|find)|"
     rf"can'?t (see|find)|without)[^.]{{0,32}}{CONTENT}|"
     rf"{CONTENT}[^.]{{0,28}}(missing|not (assigned|showing|appearing|available|loading)|"
     rf"blank|empty)|"
     rf"\bno {SUBJECT}\b|{SUBJECT}[^.]{{0,18}}(missing|blank|empty|not (showing|there))|"
     rf"blank (screen|page|lesson|course)|\bout of content\b|needs? more {CONTENT}"),
    ("Platform failures", "App / platform bug", "failure signature",
     r"\b(bugs?|broken|errors?|crash\w*|fail(ed|ing|ure|s)?|stuck on|not (work|load|"
     r"respond|open|launch|submit|sav|display)\w*|won'?t (load|open|work|submit|save)|"
     r"unable to (load|open|access|submit|log)|glitch\w*|freez\w*|timed? out|"
     r"50[0234] error)\b|not responding|incorrect(ly)?|mismatch|duplicate|orphan|"
     r"wrong (score|xp|grade|level|answer|lesson|skill|plan|course)|"
     r"\bexploit\w*|\bcheat\w*|visibility issue|confusing wording"),
    ("Platform failures", "App / platform bug", "app named with a problem",
     rf"({APPS})[^.]{{0,42}}\b(issues?|problems?|not|wrong|missing|error|broken|fail\w*|"
     rf"stuck|deleted|reset|duplicate|blank|unavailable|code|blocked?)\b|"
     rf"\b(issues?|problems?|errors?|trouble|unblock|blocked?)\b[^.]{{0,28}}({APPS})"),

    # ── 5 · the student ──────────────────────────────────────────────────────
    ("Student & academic", "Student not progressing", "deep dive / stalled",
     r"deep dive|not (learning|progressing|improving|advancing|mastering)|"
     r"no (progress|growth|improvement|movement|activity)|\b(stalled|plateau|regress)\w*|"
     r"falling behind|behind (grade|level|pace|target)|struggl\w*|"
     r"low (accuracy|xp|performance|score|mastery)|accuracy (is |was )?(low|dropped|down)|"
     r"doom loop|false green|red flag|not meeting|below (grade|target|expect)|"
     r"concern(s|ed)? about|intervention|scaffold\w*|catch.?up plan|custom plan|"
     r"not pass\w*|didn'?t pass|keeps? (failing|getting)|does ?n[o']t understand|"
     r"next steps|\bwhy\b[^.]{0,40}(fail|struggl|low|wrong|miss)|"
     r"\d+ (times|attempts)|multiple attempts"),
    ("Student & academic", "Placement & course assignment", "placement",
     rf"\bplacement\b|placed (too|in|at)|wrong (grade|level)|hole.?fill\w*|backfill\w*|"
     rf"\bhf (skill|class)|set the .{{0,24}}grade|grade to \d|showing as grade|"
     rf"(move|promot|demot|skip|advanc)\w*[^.]{{0,26}}(grade|level|student|up|down)|"
     rf"\b(add|remove|assign|swap|change|enable|disable)\w*\b[^.]{{0,26}}"
     rf"\b(app|{CONTENT}|{SUBJECT}|{APPS})\b|"
     rf"course (request|change|add|drop)|needs? more|more work"),
    ("Student & academic", "Accommodations", "accommodation",
     r"text.?to.?speech|\btts\b|speechify|read.?aloud|accommodat\w*|\biep\b|\b504\b|"
     r"extended time|extra time|dyslexi\w*|translat\w*|bilingual|\besl\b|\bell\b"),

    # ── 6 · people ───────────────────────────────────────────────────────────
    ("People & administration", "Enrolment & campus setup", "enrolment",
     r"\b(enroll?ments?|enroll?|unenroll?|withdraw\w*|dropped|new students?|transfer\w*|"
     r"rosters?|roster(ing)?|onboard\w*|offboard\w*|off.?board\w*|on.?board\w*)\b|"
     r"(setup|set up|new) (campus|school|org)|campus setup|"
     r"(set|change|update|assign) .{0,12}(primary )?organi[sz]ation|repair campus|"
     r"(rename|complete the setup|migrat\w*) .{0,30}(campus|school|student|to)|"
     r"change role|start date|last day|\bleaver\b|graduat\w*|"
     r"\badd\b[^.]{0,30}\bto\b[^.]{0,30}(timeback|campus|school|class|cohort|legends)"),
    ("People & administration", "Account & access", "access",
     r"\b(access|accounts?|passwords?|log ?in|sign.?in|sso|permissions?|credentials?|"
     r"\bpin\b|invite|2fa|mfa)\b|admin (access|rights|role)|cannot log|can'?t log|"
     r"locked out|email (change|update|address)|change email|update .{0,30}email|"
     r"add\w* (a )?user to|provision\w*|contact info|"
     r"preferred name|name change|\bdomain\b|unblock"),

    # ── 6b · a chat whose subject line is boilerplate ────────────────────────
    # "(Live Chat) Alpha Education issue" appears hundreds of times with that
    # exact wording. The channel filed it; the subject says nothing about the
    # ask. Naming the pattern is more useful than letting the word "issue" sort
    # it into platform failures.
    ("Needs triage", "Chat with a boilerplate subject", "generic chat subject",
     r"^\(?(live chat|ai chat|chat)\)?\s*[-:]?\s*(alpha )?(education|support)?\s*"
     r"(issue|request|question)?\s*$|"
     r"^(alpha )?education issue$|^\(?(live|ai) chat\)?"),

    # ── 7 · named a topic but never said the ask ────────────────────────────
    # "Bernard Fischer | Reading - Oral Reading Fluency tests", "eGUMPP",
    # "language". These name the area and nothing else. The inherited taxonomy
    # forced them into Academic on the strength of the word "reading" and so
    # reported 2,006 academic cases when 1,189 of them were this — which is how
    # a helpdesk that is overwhelmingly platform work came to look academic.
    # They are held in their own bucket instead, because the honest answer to
    # "what is this ticket" is that the subject line does not say.
    ("Needs triage", "Topic named, ask unclear", "assessment word only",
     rf"{ASSESS}"),
    ("Needs triage", "Topic named, ask unclear", "app name only",
     rf"({APPS})"),
    ("Needs triage", "Topic named, ask unclear", "subject word only",
     rf"{SUBJECT}|\bstudents?\b"),
]

COMPILED = [(g, c, n, re.compile(p, re.I)) for g, c, n, p in RULES]

FOLLOWUP = re.compile(r"^\s*(re:\s*)?follow-?up\s*(for\s*)?(ticket\s*)?#?\d*\s*:?\s*", re.I)
AICHAT = re.compile(r"^\s*\(ai chat\)\s*", re.I)


def normalise(subject, preview):
    """Subject first, preview only as backup.

    The preview is the *last* message on the case, which is usually the agent's
    closing reply ("Thanks for your patience"). Matching on it classifies a
    ticket by how it ended rather than what it was, so it is only consulted when
    the subject is too thin to say anything.
    """
    s = subject or ""
    for _ in range(3):                      # "Follow-up for #1: Follow-up on ..."
        new = FOLLOWUP.sub("", s)
        new = AICHAT.sub("", new)
        if new == s:
            break
        s = new
    s = s.strip()
    if len(s) < 12:                         # a bare name tells us nothing
        return f"{s} {preview or ''}"[:600]
    return s


# The last-resort rules match on a bare topic word with no verb. They put a
# case in the right neighbourhood, not the right box, and saying so is the
# difference between a taxonomy and a guess. Everything they catch is counted
# separately so a reader can discount it.
WEAK = {"assessment word only", "subject word only", "app name only"}


def classify(text):
    for group, cat, name, rx in COMPILED:
        if rx.search(text):
            return group, cat, name
    return "Needs triage", "No signal in the subject", ""


def hours(a, b):
    if not a or not b:
        return None
    try:
        t0 = dt.datetime.fromisoformat(a.replace("Z", "+00:00"))
        t1 = dt.datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return None
    h = (t1 - t0).total_seconds() / 3600.0
    return h if h >= 0 else None


def pct(vals, q):
    return round(statistics.quantiles(sorted(vals), n=100)[q - 1], 1) if len(vals) > 1 else None


def main():
    raw = json.load(open(RAW))
    cases = raw["cases"]
    status_name = {int(k): v for k, v in raw["lookups"]["statuses"].items()}
    rows, rule_hits = [], collections.Counter()

    for c in cases:
        text = normalise(c.get("subject", ""), c.get("preview", ""))
        group, cat, rule = classify(text)
        rule_hits[f"{cat} :: {rule}"] += 1
        solved = hours(c.get("created_at"), c.get("last_completed_at"))
        rows.append({
            "id": c.get("id"), "group": group, "category": cat, "rule": rule,
            "weak": rule in WEAK,
            "status": status_name.get(c.get("status"), "Unknown"),
            "created_at": c.get("created_at"),
            "solved_h": solved,
        })

    by_group = collections.Counter(r["group"] for r in rows)
    by_cat = collections.Counter(r["category"] for r in rows)
    cat_group = {r["category"]: r["group"] for r in rows}

    def stats(sel):
        v = [r["solved_h"] for r in sel if r["solved_h"] is not None]
        human = [h for h in v if h > 1]
        return {
            "n": len(sel),
            "weak": sum(1 for r in sel if r["weak"]),
            "n_solved": len(v),
            "auto_pct": round(100 * sum(1 for h in v if h <= 1) / len(v)) if v else None,
            "median_h": round(statistics.median(v), 1) if v else None,
            "median_human_h": round(statistics.median(human), 1) if human else None,
            "p90_h": pct(v, 90),
            "open": sum(1 for r in sel if r["status"] in OPEN_STATUSES),
        }

    groups = {g: stats([r for r in rows if r["group"] == g]) for g in by_group}
    cats = {}
    for cat in by_cat:
        s = stats([r for r in rows if r["category"] == cat])
        s["group"] = cat_group[cat]
        cats[cat] = s

    # Solve-time distribution. The shape is bimodal — automation closes a
    # quarter inside the hour and the rest take days — so a single median
    # lands in the empty valley between the humps and describes nothing.
    BUCKETS = [("under 1h", 0, 1), ("1-4h", 1, 4), ("4-24h", 4, 24),
               ("1-3d", 24, 72), ("3-7d", 72, 168), ("1-2w", 168, 336),
               ("2w-1m", 336, 720), ("over 1m", 720, 1e9)]
    solved = [r["solved_h"] for r in rows if r["solved_h"] is not None]
    dist = [{"label": lab, "n": sum(1 for h in solved if lo <= h < hi),
             "pct": round(100 * sum(1 for h in solved if lo <= h < hi) / len(solved), 1)}
            for lab, lo, hi in BUCKETS]

    # Opened per ISO week, so volume can be read as a rate rather than a total.
    wk = collections.Counter()
    for r in rows:
        if r["created_at"]:
            d = dt.date.fromisoformat(r["created_at"][:10])
            wk[(d - dt.timedelta(days=d.weekday())).isoformat()] += 1
    weeks = [{"week": k, "n": v} for k, v in sorted(wk.items())][-8:]

    human = [h for h in solved if h > 1]
    total = len(rows)
    uncl = by_cat.get("No signal in the subject", 0) + by_cat.get("Topic named, ask unclear", 0)
    weak = sum(1 for r in rows if r["weak"])
    out = {
        "pulled_at": raw.get("pulled_at"),
        "scanned": raw.get("scanned"),
        "alpha_total": total,
        "unclassified": uncl,
        "coverage_pct": round(100 * (total - uncl) / total, 1),
        "weak": weak,
        "strong_pct": round(100 * (total - uncl - weak) / total, 1),
        "n_solved": len(solved),
        "auto_pct": round(100 * sum(1 for h in solved if h <= 1) / len(solved)),
        "median_h": round(statistics.median(solved), 1),
        "median_human_h": round(statistics.median(human), 1),
        "distribution": dist,
        "weekly": weeks,
        "groups": groups,
        "categories": cats,
        "rule_hits": dict(rule_hits.most_common()),
    }
    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)

    print(f"{total:,} Alpha cases   coverage {out['coverage_pct']}%   "
          f"(strong {out['strong_pct']}%, weak {weak:,})   unclassified {uncl:,}\n")
    for g, s in sorted(groups.items(), key=lambda x: -x[1]["n"]):
        print(f"{g:<26} {s['n']:>6,}  {100*s['n']//total:>3}%   "
              f"median {s['median_h'] or 0:>6.1f}h   open {s['open']:,}")
    print()
    for cat, s in sorted(cats.items(), key=lambda x: -x[1]["n"]):
        print(f"   {cat:<30} {s['n']:>6,}  median {s['median_h'] or 0:>6.1f}h  "
              f"auto {s['auto_pct'] or 0:>3}%  open {s['open']:>5,}  weak {s['weak']:>4,}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
