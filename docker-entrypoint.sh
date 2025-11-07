#!/bin/bash
set -euo pipefail

###############################################################################
# docker-entrypoint.sh
#
# Behavior:
#  - If no args are given: run `python source/<APPROACH>/main.py` for each
#    approach in APPROACHES = (CP, SMT, MIP) WITHOUT parameters.
#  - If args are given:
#      * Accepts either positional: APPROACH [N] [VERSION]
#        Example: docker run image MIP 8 v1
#      * Or accepts long flags passed after "--": --approach MIP --n 8 --version v1
#        Example: docker run image -- --approach MIP --n 8 --version v1
#  - For a single specified APPROACH, calls its main.py and forwards --version
#    and --instance (named --n) and other defaults as needed.
#
# Notes:
#  - You should mount your host source and res directories with:
#      -v $(pwd)/source:/CDMO/source -v $(pwd)/res:/CDMO/res
#  - The entrypoint calls python on "source/<APPROACH>/main.py".
#  - If main.py expects different argument names, adapt the forwarding below.
###############################################################################

# Allowed approaches (case-insensitive check)
APPROACHES=(MIP CP SMT)
# CP SMT 

usage() {
  cat <<EOF
Usage:
  # 1) No args -> run all default approaches:
     docker run --rm -v \$(pwd)/source:/CDMO/source -v \$(pwd)/res:/CDMO/res IMAGE

  # 2) Positional: run a single approach with optional n and version:
     docker run --rm -v \$(pwd)/source:/CDMO/source -v \$(pwd)/res:/CDMO/res IMAGE MIP 8 v1

  # 3) Flags: run a single approach using long flags (note the extra -- to forward flags):
     docker run --rm -v \$(pwd)/source:/CDMO/source -v \$(pwd)/res:/CDMO/res IMAGE -- --approach MIP --n 8 --version v1

Options:
  --approach <APPROACH>    One of: CP, SMT, MIP
  --n <int>                Instance size (even integer)
  --version <str>          Version token (e.g. v1, v2, ...)
  -h|--help                Show this help
EOF
}

# helper: uppercase
toupper() { echo "$1" | tr '[:lower:]' '[:upper:]'; }

# If no arguments, run all approaches
if [ "$#" -eq 0 ]; then
  echo "[entrypoint] No arguments passed -> running all approaches (no params)."
  for A in "${APPROACHES[@]}"; do
    MAIN="/CDMO/source/${A}/main.py"
    if [ -f "$MAIN" ]; then
      echo "[entrypoint] Running ${MAIN} (with default args)..."
      python "$MAIN"
    else
      echo "[entrypoint] Warning: ${MAIN} not found. Skipping ${A}."
    fi
  done
  echo "[entrypoint] All done."
  exit 0
fi

# If arguments are present, we support both long-flag style (starting with --)
# and positional style. If first arg starts with --, parse flags.
APPROACH=""
N_VAL=""
VERSION=""
# parse long options if first arg starts with --
if [[ "$1" == --* ]]; then
  # shift through long options
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --approach)
        APPROACH="$2"; shift 2;;
      --n|--instance)
        N_VAL="$2"; shift 2;;
      --version)
        VERSION="$2"; shift 2;;
      -h|--help)
        usage; exit 0;;
      *)
        echo "[entrypoint] Unknown option: $1"
        usage; exit 1;;
    esac
  done
else
  # positional: approach [n] [version]
  APPROACH="$1"
  if [ "${2:-}" != "" ]; then
    N_VAL="$2"
  fi
  if [ "${3:-}" != "" ]; then
    VERSION="$3"
  fi
fi

# Normalize approach to uppercase
APPROACH_UPPER=$(toupper "${APPROACH:-}")

# Validate approach
valid=false
for a in "${APPROACHES[@]}"; do
  if [ "$APPROACH_UPPER" = "$a" ]; then
    valid=true; break
  fi
done

if [ "$valid" != "true" ]; then
  echo "[entrypoint] ERROR: invalid approach '${APPROACH}'. Allowed: ${APPROACHES[*]}"
  usage
  exit 2
fi

# Build main.py path for chosen approach
MAIN="/CDMO/source/${APPROACH_UPPER}/main.py"
if [ ! -f "$MAIN" ]; then
  echo "[entrypoint] ERROR: main file not found at ${MAIN}"; exit 3
fi

# Build python command with forwarded args
CMD_ARGS=()
# Forward version if present (use --version flag for the called main)
if [ -n "$VERSION" ]; then
  CMD_ARGS+=(--version "$VERSION")
fi
# Forward n as --instance (or --n) as the main expects
if [ -n "$N_VAL" ]; then
  CMD_ARGS+=(--instance "$N_VAL")
fi

echo "[entrypoint] Running ${MAIN} with args: ${CMD_ARGS[*]}"
# Exec python with the chosen main and forwarded args
exec python "$MAIN" "${CMD_ARGS[@]}"
