#!/usr/bin/env python3
"""
Build Beer League Flappy Buck.

The page is self-reproducing: it carries a base64 copy of its own source in a
<script id="tpl"> tag, so that when a player beats their best score the page can
rebuild itself with the new league state swapped in and republish. This script
produces both shipping forms from one source:

    index.html          a complete standalone document (GitHub Pages, file://)
    dist/artifact.html  body-content only, for publishing as a Claude Artifact

The league board itself lives in live_state.json and is baked into both outputs.
Read the "Never wipe the board" section of README.md before you rebuild.
"""
import base64
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# split so the markers themselves never appear verbatim in the template
PH_STATE = "__STATE" + "_JSON__"
PH_TPL = "__TEMPLATE" + "_B64__"


def read(*parts):
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return len(text.encode("utf-8"))


def main():
    head = read("src", "head.html").strip()
    body = read("src", "body1.html").rstrip() + "\n" + read("src", "body2.html").strip()

    # the canonical document -- this exact string is what publish() rebuilds from
    template = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        + head
        + "\n</head>\n<body>\n"
        + body
        + "\n</body>\n</html>\n"
    )

    for marker in (PH_STATE, PH_TPL):
        found = template.count(marker)
        if found != 1:
            sys.exit("FAIL: %s appears %d times in the template, expected exactly 1" % (marker, found))

    b64 = base64.b64encode(template.encode("utf-8")).decode("ascii")

    state = read("live_state.json").strip()
    try:
        parsed = json.loads(state)
    except ValueError as exc:
        sys.exit("FAIL: live_state.json is not valid JSON (%s)" % exc)

    def hydrate(tpl, state_json):
        return tpl.replace(PH_STATE, state_json).replace(PH_TPL, b64)

    index = hydrate(template, state)
    artifact = hydrate(head + "\n" + body + "\n", state)

    # the page must rebuild itself byte-for-byte, or republishing corrupts it
    decoded = base64.b64decode(b64).decode("utf-8")
    if decoded != template:
        sys.exit("FAIL: base64 round-trip does not match the template")
    if hydrate(decoded, state) != index:
        sys.exit("FAIL: the template is not a fixed point -- republishing would corrupt the page")

    n_index = write("index.html", index)
    n_art = write(os.path.join("dist", "artifact.html"), artifact)

    scores = parsed.get("scores", {})
    print("template        %7d bytes" % len(template.encode("utf-8")))
    print("index.html      %7d bytes" % n_index)
    print("dist/artifact   %7d bytes" % n_art)
    print("fixed point     OK")
    print("phase           %s" % parsed.get("phase"))
    if scores:
        board = sorted(scores.items(), key=lambda kv: -(kv[1].get("best") or 0))
        print("board           " + ", ".join("%s %s" % (n, v.get("best")) for n, v in board))
    else:
        print("board           empty")


if __name__ == "__main__":
    main()
