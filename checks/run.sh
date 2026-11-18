#!/bin/sh
# Runs the checks for every task up to and including the current one.
# The current task number lives in the .task file at the project root.
set -e
cd "$(dirname "$0")/.."
TASK=${1:-$(cat .task 2>/dev/null || echo 0)}
if [ "$TASK" -eq 0 ]; then
  echo "No task on this branch. Start with: git switch -c backend/01-models task/01-models"
  exit 1
fi
FILES=""
for n in $(seq 1 "$TASK"); do
  f=$(ls checks/test_$(printf '%02d' "$n")_*.py 2>/dev/null || true)
  FILES="$FILES $f"
done
# Your own tests (Task 5 onwards) run too.
[ -f todos/tests.py ] && FILES="$FILES todos/tests.py"
echo "Running checks for tasks 1 to $TASK"
exec python -m pytest $FILES
