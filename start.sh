#!/usr/bin/bash

# Initialize default variable values
SOFT=false
TEST=false
MODE="prod"

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: $0 [options]"
      echo "  -h, --help        Show help"
      echo "  -s, --soft        Enable soft launch; Push only Corporate employees"
      echo "  -t, --test        Enable test launch; Push only Natalie Baldwin"
      exit 0
      ;;
    -s|--soft)
      SOFT=true
      MODE="soft"
      shift # Move past the flag
      ;;
    -t|--test)
      TEST=true
      MODE="test"
      shift # Move past the flag
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

LAST_RUN_FILE="$PROJECT_DIR/json/last_run.json"

START_TIME=$(date +%s)
STARTED_AT=$(date -Iseconds)

RUN_SOURCE="${RUN_SOURCE:-cron}"

# Create log file
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y-%m-%d-%H-%M-%S")
LOG_FILE="$LOG_DIR/log-$TIMESTAMP.log"

# Send both stdout and stderr to the log while still displaying on the console
exec > >(tee -a "$LOG_FILE") 2>&1

######################################################
echo "===== INTRANET DATA ENGINE START ====="
######################################################

if [ "$SOFT" = true ]; then
  echo "Configured for SOFT LAUNCH"
elif [ "$TEST" = true ]; then
  echo "Configured for TEST LAUNCH" 
else
  echo "Configured for PROD LAUNCH"
fi

######################################################
echo "===== FETCHING NOTION DATA ====="
######################################################
/usr/local/go/bin/go run .
GO_EXIT=$?

echo "Go exit code: $GO_EXIT"

if [ "$GO_EXIT" -ne 0 ]; then
    STATUS="failed"

    END_TIME=$(date +%s)
    FINISHED_AT=$(date -Iseconds)
    DURATION=$((END_TIME - START_TIME))

    cat > "$LAST_RUN_FILE" <<EOF
{
  "job_name": "Intranet Data",
  "status": "$STATUS",
  "started_at": "$STARTED_AT",
  "finished_at": "$FINISHED_AT",
  "duration_seconds": $DURATION,
  "run_source": "$RUN_SOURCE",
  "mode": "$MODE"
}
EOF

    echo "ERROR: go run . failed"
    exit "$GO_EXIT"
fi

######################################################
echo "===== PYTHON CONFIG UNDERWAY ====="
######################################################

SCRIPT_DIR="$PROJECT_DIR/scripts"

if [ "$SOFT" = true ]; then
  python3 "$SCRIPT_DIR/oversee_process.py" --soft
elif [ "$TEST" = true ]; then
  python3 "$SCRIPT_DIR/oversee_process.py" --test
else
  python3 "$SCRIPT_DIR/oversee_process.py"
fi

######################################################
echo "===== POSTING TO INTRANET ====="
######################################################

source "$PROJECT_DIR/venv/bin/activate"

PY_EXIT=$?

deactivate

END_TIME=$(date +%s)
FINISHED_AT=$(date -Iseconds)
DURATION=$((END_TIME - START_TIME))

if [ "$PY_EXIT" -eq 0 ]; then
    STATUS="success"
else
    STATUS="failed"
fi

cat > "$LAST_RUN_FILE" <<EOF
{
  "job_name": "Intranet Data",
  "status": "$STATUS",
  "started_at": "$STARTED_AT",
  "finished_at": "$FINISHED_AT",
  "duration_seconds": $DURATION,
  "run_source": "$RUN_SOURCE",
  "mode": "$MODE"
}
EOF

echo "Python exit code: $PY_EXIT"

if [ "$PY_EXIT" -ne 0 ]; then
    echo "ERROR: Python process failed"
    exit "$PY_EXIT"
fi

echo "===== INTRANET DATA ENGINE COMPLETE ====="