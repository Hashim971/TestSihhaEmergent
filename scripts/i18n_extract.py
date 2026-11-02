"""Extracts user-facing English UI strings from the React source for the Arabic dictionary."""
import json
import pathlib
import re

SRC = pathlib.Path("/app/frontend/src")
OUT = pathlib.Path("/app/frontend/src/i18n/strings_en.json")

JSX_TEXT = re.compile(r">\s*([^<>{}`]*[A-Za-z][^<>{}`]*?)\s*<")
ATTR = re.compile(r'\b(?:placeholder|title|aria-label|alt)="([^"{}]*[A-Za-z][^"{}]*)"')
KEYED = re.compile(r'\b(?:label|desc|description|title|headline|sub|message|text|reason|empty)\s*:\s*"([^"]*[A-Za-z][^"]*)"')
CALLS = re.compile(r'(?:toast\.(?:success|error|info|warning)|setError|setStatus|setLiveStatus|errorText\([^,]*,)\s*\(?\s*"([^"]*[A-Za-z][^"]*)"')
TERNARY = re.compile(r'\?\s*"([^"]*[A-Za-z ][^"]*)"\s*:\s*"([^"]*[A-Za-z ][^"]*)"')
ARRAY_PAIR = re.compile(r'\[\s*"[a-z_#/]+"\s*,\s*"([^"]*[A-Za-z][^"]*)"\s*\]')


def keep(s: str) -> bool:
    s = s.strip()
    if len(s) < 2 or len(s) > 400 or not re.search(r"[A-Za-z]{2}", s):
        return False
    if re.fullmatch(r"[a-z0-9_\-./:#]+", s):
        return False
    if re.search(r"\b(?:px|py|rounded|bg-|text-|flex|grid|border|hover:)\b", s) or "=>" in s or "&&" in s:
        return False
    return True


strings = set()
for path in list(SRC.rglob("*.jsx")) + list(SRC.rglob("*.js")):
    if "i18n" in path.parts:
        continue
    code = path.read_text(encoding="utf-8")
    for rx in (JSX_TEXT, ATTR, KEYED, CALLS, ARRAY_PAIR):
        for m in rx.finditer(code):
            s = " ".join(m.group(1).split())
            if keep(s):
                strings.add(s)
    for m in TERNARY.finditer(code):
        for g in m.groups():
            s = " ".join(g.split())
            if keep(s) and " " in s or (keep(s) and s[:1].isupper()):
                strings.add(s)

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(sorted(strings), ensure_ascii=False, indent=0), encoding="utf-8")
print(len(strings))
