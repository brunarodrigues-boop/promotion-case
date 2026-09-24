# The case, in numbers — four systems in production

A tabbed dashboard. Tab one is the case itself — the summary and the argument
for promotion, five claims each tied to a number on another tab. The rest are
one tab per system (dashboard, deep dive bot, interventions, resources) and one
per body of evidence (accuracy, support load, method), so a reader can go
straight to whichever claim they want to test.

Self-contained: no JavaScript beyond the tab switching, no chart library, no
network. Printing shows every tab, so the PDF is the whole case rather than
whichever tab happened to be open — 18 pages.

No figure on the page is typed by hand. Every one comes from a data file
written by a pull, so the page cannot drift from the source and can be rebuilt
after any of the four systems moves.

## Rebuild

```bash
python3 audit.py                # must pass first — it writes audit.json
python3 build_systems.py        # reads the inputs, writes index.html
```

The order matters now. `build_systems.py` reads `audit.json` and **refuses to
build off a failing audit**, because the page claims every figure on it is
checked. The check count on the case tab is read from that file rather than
typed, so adding a check updates the page.

## Inputs, and how to refresh each

| Input | Refresh with | Cost |
|---|---|---|
| `/tmp/promo/accuracy.json` | see below | ~2,000 API calls |
| `/tmp/promo/interventions.json` | see below | one SQL round trip |
| `/tmp/promo/deepdive.json` | see below | one SQL round trip |
| `/tmp/promo/team.json` | `python3 pull_team.py` | one SQL round trip |
| `/tmp/promo/g12_reading_k8.json` | `python3 pull_g12_reading.py` | needs the `/tmp` OneRoster caches first |
| `/tmp/promo/audit.json` | `python3 audit.py` | ~3 min; the build refuses a failing audit |
| `~/Desktop/dri-workload/tickets_raw.json` | `cd ~/Desktop/dri-workload && python3 pull_tickets.py` | ~12 min, pages all ~40k cases |
| `/tmp/promo/tickets2.json` | `python3 classify_tickets.py` | seconds |
| `/tmp/promo/dashboard.json` | `python3 pull_dashboard.py` | seconds |
| `/tmp/promo/resources.json` | `python3 pull_resources.py` | seconds, fetches both sites live |
| `~/Desktop/dri-workload/dris.json` | `python3 pull_oneroster_cache.py` then `cd ~/Desktop/dri-workload && python3 pull_dris.py` | ~3 min |
| repo figures | nothing — counted live at build time | — |

### accuracy.json

Derived from `~/Desktop/timeback-trackers/alpha_app_accuracy_cache.json`, which
is produced by `pull_alpha_app_accuracy.py` (one accuracy call per student over
the whole Alpha roster). The aggregation into pooled accuracy by grade, subject,
app and subject×app is the block at the top of this repo's history — re-run it
against a newer cache to refresh.

Pooled, not averaged: Σ correct ÷ Σ answered. An average of per-student averages
would let a student who answered forty questions weigh the same as one who
answered forty thousand.

### interventions.json and deepdive.json

Read from the `alpha_dri_interventions` source via the InsForge CLI. Three of
its published rules bind anything computed here and are not optional:

- **A row is a touch, not a failure.** Fold on `email + subject + grade` within
  one log; report both the touch count and the folded count, labelled.
- **The two `section` values are independent logs.** Never total across
  `campus_dri` and `subject_dri`, and never expect them to pair.
- **Minutes live in two disjoint columns.** `minutes_spent` is the Campus DRI's
  own time on `entry_kind = 'manual_work'`; `completion_minutes` is the
  Curriculum DRI's time answering a request. The store refuses either in the
  other's place. Scope every minutes figure, or the denominator becomes the
  whole log and the answer understates the effort.

Turnaround is `completed_at − created_at` over completed `campus_dri` rows only.
The `subject_dri` log is written retrospectively — the entry is made after the
work is done — so elapsed time is not defined for it and including it would
produce negative durations.

### team.json

The figures the ask itself rests on — the caseload claims, the headline stat
row, and the two caveats about rank. Until `pull_team.py` existed these were the
only numbers on the page written by hand, which meant they were also the only
ones `audit.py` could not re-derive. Both properties were invisible until `/tmp`
was cleared and the build died on a missing file nothing in the repo could write.

**The join is on email, never on name.** `dris.json` and `team_members` disagree
on the spelling of three of the sixteen people — "Chris Voigt" against
"Christopher Voigt", "Hari Soragaon" against "Hariprasad Soragaon", "Joshua
Albar" against "Joshua Lance Martin Albar". Matching on name silently drops
those three and the adoption claim comes out at 11 of 16 instead of 14, which
reads as three DRIs ignoring the log rather than as a string mismatch.

**Who counts as a DRI is `dris.json`, not `position` in `team_members`.** That
column reads `Campus DRI` for only 13 of the 16: my own row says "AI-driven
Learning Analyst", and two people who file into the campus log — a Curriculum
DRI and an Academic Lead — carry no campus caseload at all.

Adoption is **14 of 16**, not all 16. The page said "All 14 of 16" until the
producer made the number real; two DRIs responsible for 1,915 students between
them, including the second-largest caseload on the team, have filed nothing. The
audit now asserts that "all" and a non-empty silent list cannot both be true.

### tickets.json

`pull_tickets.py` pages every case on the Kayako instance and filters locally to
the Alpha brands, because `/cases.json` accepts no brand filter. Two things to
know:

- **The `cap` argument is a real limit.** It was `40000` while the instance held
  40,579 cases, which silently truncated the pull at the dormant end. It is now
  `45000`. Check `scanned` against the instance's `total_count` after any pull;
  if they are equal to the cap, raise it.
- **Resolution is measured to `last_completed_at`**, the agent's resolving
  reply — not `last_closed_at`, which is an auto-close firing days later and
  reads 72 hours against a real resolution of 0.1.

The solve-time distribution is bimodal and the overall median falls in the empty
valley between the humps, so the page shows the distribution and quotes the
human-worked median separately rather than leading with one number.

## Charts

`charts.py` — inline SVG, no JavaScript and no chart library, so the page
survives being emailed and opened offline. Axis tops are chosen by picking a
round *step* first and letting the top follow, which is why the labels read 0 /
100 / 200 / 300 rather than 0 / 62 / 125 / 188.

Accuracy charts start at 60%, not 0. Everything on them sits between 62 and 95,
and a 0-based axis renders that as a row of identical bars — hiding exactly the
differences the chart exists to show. The axis is labelled, so the choice is
visible rather than hidden.


## Auditing

```bash
python3 audit.py     # 114 checks, exits non-zero on any failure
```

`check_growing` and `check_drifting` exist because the intervention log is
live and append-only, and the audit re-queries it seconds to minutes after the
snapshot the page was built from. For a **counter**, a re-query can only come
back higher and lower means rows vanished, so only a decrease fails. For a
**median or a sum of minutes** there is no such direction — new rows move it
either way — so the bound is on the size of the move, not its sign, set tight
enough that the wrong column or the wrong section still fails by hours.

Every figure on the page is re-derived by a *second route* and compared: the
accuracy totals are recounted straight from the per-student cache, the
intervention figures are re-queried in a different shape, the ticket categories
are re-classified from the raw pull, and the by-app/by-subject/by-grade slices
must each sum back to the same grand total. Re-running the same code and getting
the same answer proves nothing; a figure only one code path can produce is a
figure nobody has checked.

The audit also asserts the store's own constraints still hold (zero violations)
and that the helpdesk pull did not stop on a round number, which is how the
40,000 cap went unnoticed.

## Ticket taxonomy

`classify_tickets.py` replaces the inherited four-bucket split. Ordered rules
over the subject line, first match wins, every case recording the rule that
caught it. Four groups:

| Group | What it is |
|---|---|
| Platform failures | app bugs, XP/credit/sync, content not delivered |
| Student & academic | stuck students, tests, placement, accommodations |
| People & administration | accounts, enrolment, devices, finance |
| Automated & scheduled | AI chat transcripts, offboarding runs, licence jobs |
| Needs triage | the subject line never says what the ask is |

Three things this fixed:

- **`\bassignment\b` never matched "assignments".** Several hundred cases fell
  through to Unclassified on the letter s alone.
- **Automation was mixed into administration.** Offboarding runs are 1,294 cases
  closing in a median of 0.1 hours; folded into admin they dragged its median
  toward zero and made human admin work look instant.
- **The inherited "Academic — not learning" count was inflated.** It reported
  2,006, but 1,189 of those were caught by a bare subject word — "reading",
  "math" — with no verb attached, and the samples are mostly platform work. The
  honest count of *a child who is stuck and needs a plan* is 45 of 14,403.
  Rules that match only a topic word are now counted separately and never
  folded into a named category, which is why coverage reads 73% rather than 86%.


## Dashboard configuration

`pull_dashboard.py` reads the running `school_config.py` and `main.py` rather
than recalling anything, because the shape changes weekly.

Two populations are kept apart and must never be summed: **95 Alpha campuses /
6,556 students**, rostered by email allowlist, and **12 public schools / 2,050
students** across 5 districts, each with its own programme type, subject set and
doom-loop watch list.

The arithmetic has a trap the audit now guards. 95 + 12 = 107, but the campus
list holds 106: `aldine isd` is a programme definition with no allowlist of its
own, so it is *configured but not rostered*. The audit asserts that difference
is exactly one — a second unrostered key appearing silently is how a school gets
configured and then never looked at.

District is not a field in the config. The schools are keyed by their own
acronyms and the grouping here is read off the school names, which is a
judgement call and is labelled as one on the page.


## Keep this repository private

The DRI caseload table names 16 colleagues alongside their student load. There
is no student PII anywhere in the build, but a table of named people and their
workloads is not something to put behind a public URL without asking them. The
Accuracy tab also names third-party vendors against unflattering numbers
(MobyMax at 69.7%, Freckle at 70.7%).

## DRI caseload

`pull_dris.py` in `dri-workload` needs three OneRoster caches that live in
`/tmp`, and nothing in that repo builds them — when the machine clears `/tmp`
the refresh dies on a `FileNotFoundError` that says nothing about what should
have produced the file. `pull_oneroster_cache.py` here builds all three.

It pages 34,347 students at 1,000 per request; 3,000 returns a 502. It retries,
and it **refuses to write a short file** — the first version silently wrote zero
students when the API 502'd, which is the same failure mode as the mid-week
report bug on the case tab, reproduced by me, in a script written to document it.

Counts are live enrolled students — an active user record, at least one active
role, that role's end date not yet passed — not the planning sheet's manual
figures. The difference is large: the allowlist disagrees with enrolment on 60
campuses, and GT Anywhere reads 510 on the allowlist against 1,259 enrolled.
Jointly-owned campuses are split evenly; counting Texas Sport Academy Online
whole for each of its three owners would put all three at the top of the table.

## Reading Texts

`pull_resources.py` fetches the published page and parses its data structure,
so the passage count is read from what is actually live rather than remembered.
The audit fetches it a second time and recounts independently, and asserts that
all five named features (search, underlining, print, text splitting, offline)
are still present — a rebuild that silently dropped one would fail.

Note `fetch()` uses curl, not urllib: urllib cannot complete the TLS handshake
from here because the outbound proxy presents its own certificate. The Kayako
client in `dri-workload` works around the same thing the same way.
