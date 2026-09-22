"""Aggregate per-student app accuracy into the shape systems.html needs.

Reads the cache produced by ~/Desktop/timeback-trackers/pull_alpha_app_accuracy.py
(one accuracy call per student across the whole Alpha roster) and folds it into
pooled accuracy by grade, by subject, by app and by subject x app.

Pooled, deliberately: sum the correct answers and divide by the answered ones.
Averaging per-student percentages would give a student with forty questions the
same weight as one with forty thousand, and at that point the number stops
describing the cohort.

Writes /tmp/promo/accuracy.json.
"""
import collections
import json
import os
import statistics

CACHE = os.path.expanduser("~/Desktop/timeback-trackers/alpha_app_accuracy_cache.json")
OUT = "/tmp/promo/accuracy.json"

# The window the cache was pulled over, and when. Both are printed on the page,
# so they travel with the numbers instead of being folded away.
WINDOW = "2026-08-10 to 2026-09-17"
PULLED = "2026-09-18"

GRADE_LABELS = {"-1": "PreK", "0": "K"}


def label(g):
    return GRADE_LABELS.get(str(g), f"G{g}")


def sort_key(g):
    s = str(g)
    return int(s) if s.lstrip("-").isdigit() else 99


def main():
    recs = json.load(open(CACHE))
    have = [r for r in recs if r.get("per")]

    def agg(keys_of):
        totals = collections.defaultdict(lambda: [0, 0])
        students = collections.defaultdict(set)
        for r in have:
            for k, (correct, answered) in r["per"].items():
                for key in keys_of(r, k):
                    totals[key][0] += correct
                    totals[key][1] += answered
                    students[key].add(r["email"])
        return [{"key": k, "acc": round(100.0 * c / t, 1), "correct": c,
                 "answered": t, "students": len(students[k])}
                for k, (c, t) in totals.items() if t]

    by_subject = sorted(agg(lambda r, k: [k.split("||")[0]]),
                        key=lambda d: -d["answered"])
    by_app = sorted(agg(lambda r, k: [k.split("||")[1]]),
                    key=lambda d: -d["answered"])
    by_subject_app = sorted(agg(lambda r, k: [k.replace("||", "  ·  ")]),
                            key=lambda d: -d["answered"])
    by_grade = sorted(
        [{**d, "label": label(d["key"])}
         for d in agg(lambda r, k: list(r.get("grades") or ["?"]))],
        key=lambda d: sort_key(d["key"]))

    correct = sum(d["correct"] for d in by_subject)
    answered = sum(d["answered"] for d in by_subject)
    per_student = []
    for r in have:
        c = sum(v[0] for v in r["per"].values())
        t = sum(v[1] for v in r["per"].values())
        if t:
            per_student.append(100.0 * c / t)

    out = {
        "overall": {
            "pooled_acc": round(100.0 * correct / answered, 1),
            "correct": correct, "answered": answered,
            "students": len(have), "roster": len(recs),
            "median_student_acc": round(statistics.median(per_student), 1),
            "window": WINDOW, "pulled": PULLED,
            "n_apps": len(by_app), "n_subjects": len(by_subject),
        },
        "by_subject": by_subject, "by_app": by_app,
        "by_grade": by_grade, "by_subject_app": by_subject_app,
    }
    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    o = out["overall"]
    print(f"wrote {OUT}")
    print(f"  {o['answered']:,} answered, {o['pooled_acc']}% pooled, "
          f"{o['students']:,} students, {o['n_apps']} apps")


if __name__ == "__main__":
    main()
