# Organism launchd services

## Setup

Before loading `com.nuzantara.organism.control-panel.plist`, create the operator token:

    mkdir -p ~/.organism
    head -c 32 /dev/urandom | base64 > ~/.organism/token
    chmod 600 ~/.organism/token

Then load the service:

    launchctl load ~/Library/LaunchAgents/com.nuzantara.organism.control-panel.plist
    curl http://127.0.0.1:1819/health

## Usage

    TOKEN=$(cat ~/.organism/token)
    curl -X POST "http://127.0.0.1:1819/pause?minutes=30" -H "X-Organism-Token: $TOKEN"
    curl -X POST "http://127.0.0.1:1819/resume" -H "X-Organism-Token: $TOKEN"
    curl "http://127.0.0.1:1819/health"          # no auth needed
    curl "http://127.0.0.1:1819/stats" -H "X-Organism-Token: $TOKEN"

## Files

- `com.nuzantara.organism.control-panel.plist` — HTTP control panel on :1819 (W0.4)
- `com.nuzantara.organism.supervisor.plist` — Supervisor daemon (W1.A, not yet)
