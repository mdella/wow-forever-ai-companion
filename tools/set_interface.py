"""The supported WoW: Forever client interface lives in one place, the FOREVER_INTERFACE file at the
repository root. This copies it into every file that states it.

  python3 tools/set_interface.py            copy FOREVER_INTERFACE into every file
  python3 tools/set_interface.py 16002      set FOREVER_INTERFACE to 16002, then copy it
  python3 tools/set_interface.py --check    change nothing; exit 1 if any file disagrees

Change it only in an add-on release that was tested against that game version (CLAUDE.md, rule 11).
The player's data add-on follows the installed AICompanion.toc by itself (companion/gen_data.py)."""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "FOREVER_INTERFACE")

# (file, pattern): group 1 is the text before the number; the number follows it.
PLACES = [
    ("AddOns/AICompanion/AICompanion.toc", r"^(## Interface:[ \t]*)\d+"),
    ("AddOns/AICompanion_Data/AICompanion_Data.toc", r"^(## Interface:[ \t]*)\d+"),
    ("tests/mock_wow.lua", r"^(function GetBuildInfo\(\) return [^\n]*?, )\d+(?= end)"),
    ("tests/mock_wow.lua", r"(client interface )\d+"),
    ("README.md", r"(client interface )\d+"),
    ("CLAUDE.md", r"(Client interface )\d+"),
    ("companion/COMPANION_GUIDE.md", r"(client interface )\d+"),
]


def read_source():
    value = open(SOURCE, encoding="utf-8").read().strip()
    if not re.fullmatch(r"\d{5,6}", value):
        sys.exit("FOREVER_INTERFACE must hold one interface number, like 16001; it holds %r" % value)
    return value


def mismatches(value):
    """Each (file, found) that does not say value. A pattern that finds nothing is a mismatch."""
    bad = []
    for path, pattern in PLACES:
        text = open(os.path.join(ROOT, path), encoding="utf-8").read()
        found = [m.group(0)[len(m.group(1)):] for m in re.finditer(pattern, text, re.M)]
        if not found:
            bad.append((path, "nothing matched " + pattern))
        bad += [(path, f) for f in found if f != value]
    return bad


def sync(value):
    changed = set()
    for path, pattern in PLACES:
        full = os.path.join(ROOT, path)
        text = open(full, encoding="utf-8").read()
        new, n = re.subn(pattern, lambda m: m.group(1) + value, text, flags=re.M)
        if n == 0:
            sys.exit("%s: nothing matched %s" % (path, pattern))
        if new != text:
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            changed.add(path)
    return sorted(changed)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--check"]:
        bad = mismatches(read_source())
        for path, found in bad:
            print("%s: %s" % (path, found))
        sys.exit(1 if bad else 0)
    if len(args) == 1:
        if not re.fullmatch(r"\d{5,6}", args[0]):
            sys.exit("usage: set_interface.py [<interface number> | --check]")
        with open(SOURCE, "w", encoding="utf-8", newline="\n") as f:
            f.write(args[0] + "\n")
    elif args:
        sys.exit("usage: set_interface.py [<interface number> | --check]")
    value = read_source()
    changed = sync(value)
    print("interface %s;" % value, ("updated " + ", ".join(changed)) if changed else "every file already says it")
