# Job Ranker Notifications & Streamlit Lifecycle

## Vision, Design, Implementation, Testing, and Operations (macOS)

This document explains **how notifications and the Streamlit UI were envisioned, implemented, tested, and should be maintained** for the Calm-First Job Ranker on macOS.

The goal is **predictable, calm, non-intrusive automation** that respects macOS constraints and avoids background sprawl.

---

## 1. Vision (What We Wanted)

### User experience goals

- A **daily batch job** runs automatically.
- The user is **not interrupted** while the machine is asleep or shut down.
- When a run completes:
  - The user is **notified once per run**.
  - The user can **click a single “View Results” action**.
  - Clicking opens the **Streamlit UI** immediately.
- When the user is done:
  - **Closing Streamlit should stop Streamlit**.
  - No background servers should linger.
- No duplicate notifications.
- No CPU spin.
- No hidden daemons.

### Design philosophy

> Batch systems should be silent.  
> Humans should be notified only when they are present.  
> UI processes must have an obvious owner.

---

## 2. macOS Constraints (Non-Negotiable Truths)

These constraints shaped every design decision.

1. **LaunchAgents do NOT run while the Mac is powered off**
2. **Sleep is safe**  
   Jobs scheduled with `StartCalendarInterval` will run on wake/login.
3. **Notifications require a logged-in GUI session**
4. **Notifications cannot execute arbitrary callbacks**
5. **Browser tabs closing do NOT signal the server**
6. **Only the process owner can reliably control process lifetime**

Because of this:

- Notifications must be **deferred to login** if the job ran earlier.
- Streamlit **cannot** auto-stop on browser close.
- Streamlit **must** be tied to something that actually closes (Terminal).

---

## 3. Final Architecture (Authoritative)

```
launchd (daily trigger)
└── run_daily.sh
    ├── runs batch pipeline
    ├── writes run status (JSON)
    ├── triggers notifier (best-effort)
    └── exits

launchd (login-triggered)
└── job_ranker_notify.sh
    ├── checks for unseen run
    ├── fires notification
    ├── acknowledges run
    └── exits

Terminal.app (user-owned)
└── streamlit run app.py
    ├── runs UI
    └── stops when Terminal closes
```

### Key invariants

- **Batch does not depend on UI**
- **Notifications do not own long-running processes**
- **Terminal owns Streamlit**
- **State, not events, controls behavior**

---

## 4. State Contract (Single Source of Truth)

All notification logic is driven by a single file:

`~/.job_ranker_last_run.json`

### Example

```json
{
  "run_id": "1738035012",
  "timestamp": "2026-01-28T04:44:19+05:30",
  "status": "success",
  "notified": false
}
```

| Field      | Purpose                                 |
|------------|-----------------------------------------|
| run_id     | Uniquely identifies a batch run         |
| timestamp  | When the run completed                  |
| status     | success / failed                        |
| notified   | Whether the user has acknowledged this run |

This makes the system:
- idempotent
- restart-safe
- debuggable
- deterministic

---

## 5. Implementation Details

### 5.1 Batch job (run_daily.sh)

**Responsibilities:**
- Run the pipeline
- Record run outcome
- Never show UI
- Never depend on GUI availability

**At the end of the script:**

```sh
STATUS_FILE="$HOME/.job_ranker_last_run.json"
RUN_ID="$(date +%s)"

echo "{
  \"run_id\": \"$RUN_ID\",
  \"timestamp\": \"$(date -Iseconds)\",
  \"status\": \"success\",
  \"notified\": false
}" > "$STATUS_FILE"
```

**Failure trap:**

```sh
trap 'echo "{\"run_id\":\"$(date +%s)\",\"timestamp\":\"$(date -Iseconds)\",\"status\":\"failed\",\"notified\":false}" > "$HOME/.job_ranker_last_run.json"' ERR
```

**Optional immediate trigger:**

```sh
launchctl kickstart -k gui/$(id -u)/com.example.job_ranker.notify || true
```

---

### 5.2 Notification script (`job_ranker_notify.sh`)

**Responsibilities:**
- Run only when GUI is available
- Notify once per run
- Acknowledge state
- Launch Streamlit via Terminal

**Core logic:**
- If `notified == true` → exit
- Show notification
- Mark `notified = true`
- Open Terminal + Streamlit

**Terminal-bound Streamlit (critical):**

```applescript
tell application "Terminal"
  activate
  do script "cd /Users/examplecandidate/Projects/job_ranker/scrape_jobs && streamlit run app.py"
end tell
```

**Why this matters:**
- Closing the Terminal window kills Streamlit
- No orphan background servers
- Clear ownership

---

### 5.3 LaunchAgents

**Scheduler (daily)**
- Uses `StartCalendarInterval`
- No `KeepAlive`
- No GUI dependency

**Notifier (login-only)**
- Uses `RunAtLoad`
- Does not loop
- Safe to trigger manually

---

## 6. Click-to-Acknowledge Behavior

**What “click” means on macOS**
- Notifications cannot run callbacks.
- Clicking opens apps or URLs.
- Acknowledgement must be state-based, not event-based.

**How ACK works here**
- The notifier marks the run as notified immediately
- Clicking the notification opens Terminal + Streamlit
- No repeat notifications for the same run

This avoids brittle click-detection hacks.

---

## 7. Testing Guide

### 7.1 Unit-style testing (no launchd)

```sh
cat << EOF > ~/.job_ranker_last_run.json
{
  "run_id": "test",
  "timestamp": "$(date -Iseconds)",
  "status": "success",
  "notified": false
}
EOF

~/bin/job_ranker_notify.sh
```

**Expected:**
- Notification appears
- Terminal opens
- Streamlit starts
- Browser opens

**Verify ACK:**

```sh
jq .notified ~/.job_ranker_last_run.json
```

---

### 7.2 Lifecycle test (core requirement)

1. Click notification
2. Streamlit opens
3. Close Terminal window

**Verify:**

```sh
lsof -i :8501 || echo "streamlit stopped"
```

---

### 7.3 launchd integration

```sh
launchctl kickstart -k gui/$(id -u)/com.example.job_ranker.notify
```

**Expected:**
- Same behavior as manual run

---

### 7.4 Sleep / login test

1. Set `notified=false`
2. Put Mac to sleep
3. Wake + login

**Expected:**
- Notification appears on login
- Click opens Streamlit

---

## 8. Operations & Maintenance

**Stop notifications for current run**

```sh
jq '.notified = true' ~/.job_ranker_last_run.json > ~/.tmp && mv ~/.tmp ~/.job_ranker_last_run.json
```

**Disable notifications entirely**

```sh
launchctl unload ~/Library/LaunchAgents/com.example.job_ranker.notify.plist
```

**Re-enable notifications**

```sh
launchctl load ~/Library/LaunchAgents/com.example.job_ranker.notify.plist
```

**Stop Streamlit immediately**

```sh
pkill -f streamlit
```

---

## 9. What We Explicitly Avoided (On Purpose)

- Background daemons for UI
- Auto-restarting Streamlit
- Polling loops
- Browser-close detection hacks
- GUI dependencies in batch jobs

These all lead to brittle systems on macOS.

---

## 10. Design Summary

| Concern             | Decision             |
|---------------------|---------------------|
| Batch execution     | launchd, headless   |
| Notification timing | login-aware         |
| Notification dedupe | state-based         |
| UI lifetime         | Terminal-owned      |
| Streamlit shutdown  | close Terminal      |
| Debuggability       | single JSON file    |

---

## 11. Mental Model (Keep This)

- Batch jobs write facts.
- Notifications interpret facts.
- Terminals own processes.
- Browsers are just viewers.

If you keep this model, the system stays calm and predictable.

---
