import json, os, datetime

base = r"C:\Users\LENOVO\.claude\projects\C--Users-LENOVO"
daily = {}

def process_file(fp):
    with open(fp, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                msg = d.get("message", {})
                ts = d.get("timestamp")
                if isinstance(msg, dict) and "usage" in msg:
                    u = msg["usage"]
                    inp = u.get("input_tokens", 0)
                    cache_create = u.get("cache_creation_input_tokens", 0)
                    cache_read = u.get("cache_read_input_tokens", 0)
                    out = u.get("output_tokens", 0)

                    dt = None
                    if ts:
                        if isinstance(ts, (int, float)) and ts > 1e12:
                            dt = datetime.datetime.fromtimestamp(ts/1000)
                        elif isinstance(ts, (int, float)):
                            dt = datetime.datetime.fromtimestamp(ts)
                        elif isinstance(ts, str):
                            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt is None:
                        return

                    day = dt.strftime("%Y-%m-%d")
                    if not day.startswith("2026-02"):
                        return

                    if day not in daily:
                        daily[day] = {"input": 0, "cache_create": 0, "cache_read": 0, "output": 0, "calls": 0}
                    daily[day]["input"] += inp
                    daily[day]["cache_create"] += cache_create
                    daily[day]["cache_read"] += cache_read
                    daily[day]["output"] += out
                    daily[day]["calls"] += 1
            except:
                pass

# Process all session files + subagents
for f in os.listdir(base):
    if f.endswith(".jsonl"):
        process_file(os.path.join(base, f))
        session_id = f.replace(".jsonl", "")
        sub_dir = os.path.join(base, session_id, "subagents")
        if os.path.exists(sub_dir):
            for sf in os.listdir(sub_dir):
                if sf.endswith(".jsonl"):
                    process_file(os.path.join(sub_dir, sf))

# Print header
print("{:<12} {:>10} {:>10} {:>12} {:>10} {:>12} {:>6}".format(
    "Date", "Input", "CacheW", "CacheR", "Output", "TotalIn", "Calls"))
print("-" * 80)

ti = tc = tr = to = ta = 0
for day in sorted(daily):
    d = daily[day]
    total_input = d["input"] + d["cache_create"] + d["cache_read"]
    ti += d["input"]
    tc += d["cache_create"]
    tr += d["cache_read"]
    to += d["output"]
    ta += d["calls"]
    print("{:<12} {:>10,} {:>10,} {:>12,} {:>10,} {:>12,} {:>6}".format(
        day, d["input"], d["cache_create"], d["cache_read"], d["output"], total_input, d["calls"]))

print("-" * 80)
gi = ti + tc + tr
print("{:<12} {:>10,} {:>10,} {:>12,} {:>10,} {:>12,} {:>6}".format(
    "TOTAL", ti, tc, tr, to, gi, ta))
print()
print("Grand total input tokens:  {:>14,}".format(gi))
print("Grand total output tokens: {:>14,}".format(to))
print("Grand total ALL tokens:    {:>14,}".format(gi + to))
print()

# Cost estimate at API rates for Claude Opus 4
# Opus: $15/M input, $75/M output, cache write $18.75/M, cache read $1.875/M
cost_input = ti * 15 / 1_000_000
cost_cw = tc * 18.75 / 1_000_000
cost_cr = tr * 1.875 / 1_000_000
cost_out = to * 75 / 1_000_000
total_cost = cost_input + cost_cw + cost_cr + cost_out

print("=== API Cost Equivalent (Opus 4 rates) ===")
print("Input tokens:       ${:>8.2f}  ({:,} @ $15/M)".format(cost_input, ti))
print("Cache write tokens: ${:>8.2f}  ({:,} @ $18.75/M)".format(cost_cw, tc))
print("Cache read tokens:  ${:>8.2f}  ({:,} @ $1.875/M)".format(cost_cr, tr))
print("Output tokens:      ${:>8.2f}  ({:,} @ $75/M)".format(cost_out, to))
print("---")
print("TOTAL API COST:     ${:>8.2f}".format(total_cost))
print()
print("You paid: $200 (subscription)")
print("NOTE: Only covers Feb 19-28 (earlier transcript files cleaned up)")
print("Estimated full month: ~2x this = ~${:.0f}".format(total_cost * 2))
