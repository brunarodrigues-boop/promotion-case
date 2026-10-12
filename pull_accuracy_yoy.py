"""Student accuracy last school year against this one, for the same children.

WHY THE WINDOWS ARE NOT THE SAME LENGTH. The analytics endpoint holds nothing
before November 2025 -- August to October 2025 comes back empty for every
student probed -- so the matching Aug-Sep window last year does not exist. It
also costs one call per day, so pulling all of last year for every student is
438,000 calls and does not finish. Last year is therefore the closing stretch
of 2025-26, which is both affordable and the fairest comparison: it is where
the children actually ended up. Accuracy is a RATE, so unequal windows still
compare; exposure does not, which is why answered counts are carried alongside
every percentage.

MATCHED COHORT. Only students with real volume in BOTH windows are compared --
roughly half the roster, because the rest joined this year and have no last
year. A pooled figure over everyone would be comparing two different groups of
children and calling the difference progress.

POOLED, NOT AVERAGED. Correct divided by answered across the cohort. Averaging
per-student percentages gives a child with forty questions the same weight as
one with forty thousand.

Writes /tmp/promo/accuracy_yoy.json
"""
import collections
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.expanduser("~/Desktop/TimeBack/backend"))
os.chdir(os.path.expanduser("~/Desktop/TimeBack/backend"))
from dotenv import load_dotenv                                    # noqa: E402
load_dotenv(os.path.expanduser("~/Desktop/TimeBack/.env"))
import data_client as dc                                          # noqa: E402

TRK   = os.path.expanduser("~/Desktop/timeback-trackers")
ROSTER = os.path.join(TRK, "prek_k_roster_cache.json")
THIS_CACHE = os.path.join(TRK, "alpha_app_accuracy_cache.json")
PART = "/tmp/promo/accuracy_lastyear_partial.json"
OUT  = "/tmp/promo/accuracy_yoy.json"

# The analytics endpoint fetches ONE CALL PER DAY, so a window's cost is its
# length. All of last year (Nov-Jun) is 215 calls per student and 438,000 in
# total, which does not finish. Last year is therefore the closing stretch of
# the school year -- the densest part of it, and the fairest thing to compare a
# new year against, since it is where the children actually ended up.
LAST = ("2026-03-01", "2026-06-04")      # end of the 2025-26 school year
THIS = ("2026-08-10", "2026-09-17")      # the window this year's cache was pulled over
# Lower than it would be for equal windows: last year's volume is a fraction of
# this year's, so a 500 floor would throw away most of the matched cohort.
MIN_ANSWERED = 200


def totals(acc):
    """{subject: [correct, answered]} from the analytics day map."""
    per = collections.defaultdict(lambda: [0, 0])
    for _d, subj_map in (acc or {}).items():
        for subj, sd in (subj_map or {}).items():
            for _app, av in ((sd or {}).get("apps") or {}).items():
                per[subj][0] += (av or {}).get("correct", 0) or 0
                per[subj][1] += (av or {}).get("total", 0) or 0
    return {k: v for k, v in per.items()}


def main():
    roster = [r for r in json.load(open(ROSTER))
              if r.get("found") and r.get("sourced_id")]
    all_n = len(roster)
    # Only pull last year for children who have THIS year. A student with no
    # current volume can never be matched, so their last year is 96 calls spent
    # to produce a row that is dropped anyway -- and this pull costs one call
    # per day per student.
    this_recs = {r["email"]: r for r in json.load(open(THIS_CACHE))}

    def this_volume(em):
        rec = this_recs.get(em) or {}
        return sum(v[1] for v in (rec.get("per") or {}).values())

    roster = [r for r in roster if this_volume(r["email"]) >= MIN_ANSWERED]
    print(f"{len(roster)} candidates of {all_n} resolved students "
          f"(the rest have no this-year volume to match against)", flush=True)

    H = {"Authorization": f"Bearer {dc.get_token()}"}
    partial = json.load(open(PART)) if os.path.exists(PART) else {}
    print(f"resuming with {len(partial)} already pulled", flush=True)
    lock, done, t0 = threading.Lock(), [0], time.time()

    def one(r):
        if r["email"] in partial:
            with lock:
                done[0] += 1
            return
        acc = {}
        # Retry: the API answers 503 under load, and without this an overloaded
        # minute silently becomes a child with no last year.
        for attempt in range(6):
            try:
                acc = dc.fetch_analytics_local_days_accuracy(
                    H, r["sourced_id"], LAST[0], LAST[1])
                if acc is not None:
                    break
            except Exception:
                acc = None
            time.sleep(3 + attempt * 4)
        if acc is None:
            raise RuntimeError(f"{r['email']}: analytics unavailable")
        with lock:
            partial[r["email"]] = {"per": {k: v for k, v in totals(acc).items()}}
            done[0] += 1
            if done[0] % 50 == 0:
                json.dump(partial, open(PART, "w"))
                el = time.time() - t0
                print(f"  {done[0]}/{len(roster)}  {el:.0f}s  "
                      f"eta {el/max(done[0],1)*(len(roster)-done[0]):.0f}s", flush=True)

    with ThreadPoolExecutor(max_workers=14) as pool:
        list(pool.map(one, roster))
    json.dump(partial, open(PART, "w"))
    print(f"last-year pull done in {time.time()-t0:.0f}s", flush=True)

    # This year comes from the cache the page already uses, so the "this year"
    # figure on the new chart is the same number as the one on the Accuracy tab.
    this_recs = {r["email"]: r for r in json.load(open(THIS_CACHE))}

    def fold(per):
        c = sum(v[0] for v in per.values())
        t = sum(v[1] for v in per.values())
        return c, t

    rows, by_subj = [], collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in roster:
        em = r["email"]
        ly = (partial.get(em) or {}).get("per") or {}
        ty_rec = this_recs.get(em) or {}
        ty = collections.defaultdict(lambda: [0, 0])
        for k, v in (ty_rec.get("per") or {}).items():
            subj = k.split("||")[0]
            ty[subj][0] += v[0]
            ty[subj][1] += v[1]
        c1, t1 = fold(ly)
        c2, t2 = fold(dict(ty))
        if t1 < MIN_ANSWERED or t2 < MIN_ANSWERED:
            continue
        rows.append({"email": em, "grades": r.get("grades") or [],
                     "last_correct": c1, "last_answered": t1,
                     "this_correct": c2, "this_answered": t2,
                     "last_acc": round(100 * c1 / t1, 1),
                     "this_acc": round(100 * c2 / t2, 1)})
        for subj in set(ly) | set(ty):
            a = ly.get(subj) or [0, 0]
            b = ty.get(subj) or [0, 0]
            if a[1] >= MIN_ANSWERED and b[1] >= MIN_ANSWERED:
                by_subj[subj][0] += a[0]
                by_subj[subj][1] += a[1]
                by_subj[subj][2] += b[0]
                by_subj[subj][3] += b[1]

    lc = sum(r["last_correct"] for r in rows)
    lt = sum(r["last_answered"] for r in rows)
    tc = sum(r["this_correct"] for r in rows)
    tt = sum(r["this_answered"] for r in rows)
    improved = sum(1 for r in rows if r["this_acc"] > r["last_acc"])

    out = {
        "last_window": " to ".join(LAST), "this_window": " to ".join(THIS),
        "min_answered": MIN_ANSWERED,
        "roster": len(roster), "matched": len(rows),
        "last_acc": round(100 * lc / lt, 1) if lt else None,
        "this_acc": round(100 * tc / tt, 1) if tt else None,
        "last_answered": lt, "this_answered": tt,
        "improved": improved, "declined": len(rows) - improved,
        "by_subject": sorted(
            [{"subject": s, "last_acc": round(100 * v[0] / v[1], 1),
              "this_acc": round(100 * v[2] / v[3], 1),
              "last_answered": v[1], "this_answered": v[3]}
             for s, v in by_subj.items() if v[1] and v[3]],
            key=lambda x: -x["this_answered"]),
        "students": rows,
    }
    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")
    print(f"  matched {out['matched']} of {out['roster']} students")
    print(f"  last year {out['last_acc']}% over {lt:,} answered")
    print(f"  this year {out['this_acc']}% over {tt:,} answered")
    print(f"  improved {improved}, declined {out['declined']}")


if __name__ == "__main__":
    main()
