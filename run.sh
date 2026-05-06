#!/bin/zsh
# Wrapper for tracker.py — used by cron / launchd.
# Edit ROCHA_PHONE below to set your iMessage destination (international format).

export ROCHA_PHONE="${ROCHA_PHONE:-}"  # set via launchd plist or here directly
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$(dirname "$0")"
/opt/homebrew/bin/python3 tracker.py
