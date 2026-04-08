#!/usr/bin/env bash
# Double-click this to start Recipe Fetcher
# Safari will open automatically

# Kill any existing instance
lsof -ti:8080 | xargs kill 2>/dev/null

exec /Users/brandonmcdevitt/recipe-fetcher/start.sh
