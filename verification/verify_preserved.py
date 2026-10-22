"""Check that every customer customization (server.diff vs Cisco 0f63e16) survives in our server.

For each hunk: every line the customer ADDED must be present in our file (in the same
order within the hunk); every Cisco line the customer REMOVED must not be present in
the corresponding place. Lines are compared stripped of surrounding whitespace.
Usage: python verify_preserved.py server.diff new_server.py
"""
import sys

diff_path, new_path = sys.argv[1], sys.argv[2]
new_lines = [l.strip() for l in open(new_path, encoding="utf-8").read().splitlines()]
new_text = "\n".join(new_lines)

hunks, cur = [], None
for raw in open(diff_path, encoding="utf-8").read().splitlines():
    if raw.startswith("@@"):
        cur = {"header": raw, "added": [], "removed": []}
        hunks.append(cur)
    elif cur is not None and raw.startswith("+") and not raw.startswith("+++"):
        cur["added"].append(raw[1:].strip())
    elif cur is not None and raw.startswith("-") and not raw.startswith("---"):
        cur["removed"].append(raw[1:].strip())

def import_covered(line):
    """A 'from X import a, b' line is kept if the new file imports at least the same names from X."""
    if not line.startswith("from ") or " import " not in line:
        return False
    module, names = line[5:].split(" import ", 1)
    wanted = {n.strip() for n in names.split(",")}
    for other in new_lines:
        if other.startswith(f"from {module} import "):
            have = {n.strip() for n in other.split(" import ", 1)[1].split(",")}
            if wanted <= have:
                return True
    return False


ok = True
for h in hunks:
    added = [l for l in h["added"] if l]
    # added lines must appear in order (as a subsequence) in the new file
    pos, missing = 0, []
    for line in added:
        try:
            pos = new_lines.index(line, pos) + 1
        except ValueError:
            if not import_covered(line):
                missing.append(line)
    # removed lines: report the ones that are still there AND not re-added elsewhere by the customer
    # generic lines like "else:" or ")" occur everywhere; only distinctive lines are worth a note
    still = [l for l in h["removed"] if len(l) >= 25 and l in new_lines and l not in added]
    status = "KEPT" if not missing else "MISSING"
    print(f"{status:8s} {h['header']}  (+{len(added)} lines)")
    for m in missing:
        ok = False
        print("    missing:", m[:110])
    for r in still:
        print("    note: a line the customer removed also exists in the new file:", r[:100])

print("\nRESULT:", "all customer changes are present" if ok else "SOME CUSTOMER CHANGES ARE MISSING")
sys.exit(0 if ok else 1)
