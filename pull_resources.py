"""Measure the resource estate: the shared library, and the reading-texts site.

Both are read live rather than described from memory — the library from its own
/api/health and /api/config, the reading site by fetching the published page and
parsing the data structure out of it. If either is down, that shows up as a
failure here rather than as a stale number on the page.

Writes /tmp/promo/resources.json.
"""
import json
import os
import re
import subprocess

LIBRARY = "https://web-production-8873c.up.railway.app"
READING = "https://brunarodrigues-boop.github.io/reading-texts/index.html"
OUT = "/tmp/promo/resources.json"


def fetch(url, timeout=40):
    """curl, not urllib.

    urllib cannot complete the TLS handshake from here — the outbound proxy
    presents its own certificate and urllib rejects it with
    CERTIFICATE_VERIFY_FAILED. curl negotiates it fine, and dri-workload's
    Kayako client works around the same thing the same way.
    """
    r = subprocess.run(["curl", "-sS", "--fail", "--max-time", str(timeout),
                        "-H", "User-Agent: promotion-case/1.0", url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"fetch failed ({r.returncode}) for {url}: {r.stderr[:200]}")
    return r.stdout


def library():
    health = json.loads(fetch(f"{LIBRARY}/api/health"))
    config = json.loads(fetch(f"{LIBRARY}/api/config"))
    return {
        "url": LIBRARY,
        "resources": health.get("count"),
        "postgres": health.get("postgres"),
        # Railway wipes container disk on redeploy, so SQLite here would lose
        # every resource the team added. The app refuses to pretend otherwise.
        "ephemeral": config.get("ephemeral"),
        "subjects": config.get("subjects") or [],
        "types": config.get("types") or [],
        "grades": config.get("grades") or [],
        "visibilities": config.get("visibilities") or [],
        "student_login": bool(config.get("has_student_login")),
    }


def reading_texts():
    page = fetch(f"{READING}?cb=audit")
    m = re.search(r"const DATA = (\{.*?\});\n", page, re.S)
    if not m:
        raise SystemExit("reading-texts: could not find the DATA block")
    data = json.loads(m.group(1))

    by_grade, passages, lessons, words = [], 0, 0, 0
    for g in sorted(data, key=int):
        items = data[g]
        p = sum(len(i["texts"]) for i in items)
        w = sum(len(t.split()) for i in items for t in i["texts"])
        by_grade.append({"grade": f"G{g}", "lessons": len(items),
                         "passages": p, "words": w,
                         "with_text": sum(1 for i in items if i["texts"])})
        passages += p
        lessons += len(items)
        words += w

    return {
        "url": "https://brunarodrigues-boop.github.io/reading-texts/",
        "grades": len(data),
        "lessons": lessons,
        "passages": passages,
        "words": words,
        "topics": len({i["topic"] for g in data.values() for i in g}),
        "lessons_with_text": sum(b["with_text"] for b in by_grade),
        "by_grade": by_grade,
        "page_kb": round(len(page) / 1024),
        # Each is a single named function in the page; absence means the
        # feature shipped and was then lost in a rebuild.
        "features": {
            "search": "searchResults" in page,
            "underlining": "toggleUnderline" in page,
            "print": "printLesson" in page,
            "text_splitting": "splitRawTexts" in page,
            "offline": "fetch(" not in page.split("const DATA")[0][-4000:],
        },
    }


def main():
    out = {"library": library(), "reading": reading_texts()}
    os.makedirs("/tmp/promo", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)

    lib, rd = out["library"], out["reading"]
    print(f"library:  {lib['resources']} resources, postgres={lib['postgres']}, "
          f"{len(lib['subjects'])} subjects, {len(lib['types'])} types")
    print(f"reading:  {rd['passages']} passages, {rd['lessons']} lessons, "
          f"{rd['grades']} grades, {rd['words']:,} words, {rd['page_kb']} KB")
    for g in rd["by_grade"]:
        print(f"   {g['grade']}  {g['lessons']:>3} lessons  {g['passages']:>3} passages  "
              f"{g['words']:>7,} words")
    missing = [k for k, v in rd["features"].items() if not v]
    print(f"   features: {'all present' if not missing else 'MISSING ' + ', '.join(missing)}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
