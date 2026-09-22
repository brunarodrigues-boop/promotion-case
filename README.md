# The case, in numbers — four systems in production

A single self-contained page: the deep dive bot, the TimeBack dashboard, the
resource library and the intervention log — what each is for, why it has to
exist, and the numbers underneath it.

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
| `~/Desktop/dri-workload/tickets.json` | `cd ~/Desktop/dri-workload && python3 pull_tickets.py && python3 classify.py` | ~12 min, pages all ~40k cases |
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
