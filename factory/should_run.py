"""Skip the heavy setup when today's quota for this language is already used up (it resets at midnight Pacific)."""
import json, os, sys, time
lang = sys.argv[1]; p = f"content/status-{lang}.json"
day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 8 * 3600))
done = os.path.exists(p) and json.load(open(p)).get("exhausted_day") == day
print(f"run={'0' if done else '1'}")
open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a").write(f"run={'0' if done else '1'}\n")
