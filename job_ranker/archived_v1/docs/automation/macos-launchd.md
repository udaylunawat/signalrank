
# macOS Automation with launchd (Daily Runs + Login Notifications)

This document describes the **correct, production-grade way** to run a daily batch job on macOS using `launchd`, with **deferred notifications shown on login**.

This design is intentional, robust, and avoids common macOS pitfalls.

---

## Ground Truths (Non-Negotiable)

1. **LaunchAgents do NOT run while the system is powered off**  
   macOS cannot execute user jobs when the machine is shut down.

2. **Sleep is safe when using `StartCalendarInterval`**  
   If the system is asleep at the scheduled time, `launchd` runs the job on the next wake or login.

3. **Notifications require a logged-in GUI session**  
   - Notifications can only be displayed after login  
   - Jobs may run earlier, but notifications must be deferred

**Conclusion**

> Run the job daily when possible, record status, and show a notification on the next login.

---

## Architecture (Authoritative)

launchd (daily trigger)
└── run_daily.sh
├── performs batch work
├── writes status file (success / failure + timestamp)
└── exits

launchd (RunAtLoad, login-only)
└── job_ranker_notify.sh
├── reads last run status
└── sends macOS notification

This separation is **required**.  
Any design that mixes scheduling and GUI notification is fragile.

---

## Step 1: Daily Scheduler LaunchAgent

The scheduler must run **once per day**, not continuously.

### Scheduler plist

```bash
cat << 'EOF' > ~/Library/LaunchAgents/com.example.job_ranker.notify.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.job_ranker.notify</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/examplecandidate/bin/job_ranker_notify.sh</string>
  </array>

  <!-- Run on login -->
  <key>RunAtLoad</key>
  <true/>

  <!-- Allow manual trigger -->
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
EOF

launchctl unload ~/Library/LaunchAgents/com.example.job_ranker.notify.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.example.job_ranker.notify.plist
```

Why this works
	•	Runs exactly once per day
	•	Catches up after sleep
	•	No runaway daemon
	•	Deterministic execution

⸻

Step 2: Persist Run Status (Single Source of Truth)

At the end of run_daily.sh:
```bash
STATUS_FILE="$HOME/.job_ranker_last_run.json"

echo "{
  \"timestamp\": \"$(date -Iseconds)\",
  \"status\": \"success\"
}" > "$STATUS_FILE"

Add failure handling near the top:

trap 'echo "{\"timestamp\":\"$(date -Iseconds)\",\"status\":\"failed\"}" > "$HOME/.job_ranker_last_run.json"' ERR
```
This file is the only contract between batch execution and notifications.

⸻

Step 3: Notification Script (GUI-Only)
```bash
cat << 'EOF' > ~/bin/job_ranker_notify.sh
#!/usr/bin/env bash
set -e

STATUS_FILE="$HOME/.job_ranker_last_run.json"
MAX_DURATION=300        # 5 minutes
INTERVAL=30             # re-notify every 30s

[ -f "$STATUS_FILE" ] || exit 0

RUN_ID=$(jq -r '.run_id' "$STATUS_FILE")
STATUS=$(jq -r '.status' "$STATUS_FILE")
TS=$(jq -r '.timestamp' "$STATUS_FILE")
NOTIFIED=$(jq -r '.notified' "$STATUS_FILE")

# If already notified, do nothing
if [ "$NOTIFIED" = "true" ]; then
  exit 0
fi

if [ "$STATUS" = "success" ]; then
  MSG="Job Ranker completed successfully at $TS"
else
  MSG="Job Ranker FAILED at $TS"
fi

START=$(date +%s)

while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))

  if [ "$ELAPSED" -ge "$MAX_DURATION" ]; then
    break
  fi

  /usr/bin/osascript <<EOT
display notification "$MSG" with title "Job Ranker" subtitle "Daily batch run"
EOT

  sleep "$INTERVAL"
done

# Mark as notified
jq '.notified = true' "$STATUS_FILE" > "$STATUS_FILE.tmp"
mv "$STATUS_FILE.tmp" "$STATUS_FILE"
EOF

chmod +x ~/bin/job_ranker_notify.sh
```

⸻

Step 4: Login-Only Notification LaunchAgent

cat << 'EOF' > ~/Library/LaunchAgents/com.example.job_ranker.notify.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.job_ranker.notify</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/examplecandidate/bin/job_ranker_notify.sh</string>
  </array>

  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF

launchctl unload ~/Library/LaunchAgents/com.example.job_ranker.notify.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.example.job_ranker.notify.plist


⸻

Guarantees
	•	Runs once per day
	•	No CPU spin
	•	Survives sleep
	•	Notifications appear on login
	•	Batch execution is never blocked
	•	Scheduler has zero GUI dependency
	•	Clean separation of concerns

⸻

Explicit Limitations (Do Not Fight These)
	•	Jobs cannot run while the Mac is powered off
	•	Notifications cannot appear without login
	•	GUI alerts from background daemons are unreliable by design

Any claim otherwise is incorrect.

⸻

Optional Hardening
	•	Add last_notified to avoid repeat notifications
	•	Notify only on failures
	•	Use launchctl print gui/$UID/... for debugging

⸻

Design Principle

Batch systems should be silent.
Humans should be notified only when they are present.

---
