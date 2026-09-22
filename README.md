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
python3 build_systems.py        # reads the four inputs, writes index.html
```

## Inputs, and how to refresh each

| Input | Refresh with | Cost |
|---|---|---|
| `/tmp/promo/accuracy.json` | see below | ~2,000 API calls |
| `/tmp/promo/interventions.json` | see below | one SQL round trip |
| `/tmp/promo/deepdive.json` | see below | one SQL round trip |
| `~/Desktop/dri-workload/tickets_raw.json` | `cd ~/Desktop/dri-workload && python3 pull_tickets.py` | ~12 min, pages all ~40k cases |
| `/tmp/promo/tickets2.json` | `python3 classify_tickets.py` | seconds |
| `/tmp/promo/dashboard.json` | `python3 pull_dashboard.py` | seconds |
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
python3 audit.py     # 32 checks, exits non-zero on any failure
```

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
