#!/usr/bin/env bash
# ==============================================================================
# ANTIGRAVITY PE FRONTIER: STAGE 2 CLOUD REPRODUCTION & ARTIFACTS RUNBOOK
# ==============================================================================
# Reproduces the Stage 2 entry on an Ubuntu 22.04 / 24.04 VM (GCP / AWS / RunPod):
#   1. Installs Docker, uv, Harbor, and system dependencies.
#   2. Starts the kit's Vertex AI model proxy (the proxy is Vertex-only).
#   3. Runs the 29-task public dev set via eval/run.py.
#   4. Reviews the fresh artifacts, commits them, runs 'kit check' (build,
#      smoke test, artifact review), then tags stage2-eval.
#
# Prerequisites:
#   - A Google Cloud project with the Vertex AI API enabled, and Application
#     Default Credentials on the VM:
#         gcloud auth application-default login
#     On a GCP VM with an attached service account, ADC is automatic.
#   - Access to the gated Hugging Face dev-set dataset:
#         export HF_TOKEN=<read token>
#     (or run 'uv run hf auth login' once).
#
# Environment knobs:
#   PLE_REPO=<path>        PLE benchmark checkout (auto-discovered if unset)
#   VERTEXAI_PROJECT=...   GCP project for the local model proxy
#   MODEL_PROXY_URL=...    Use an already-running proxy instead of starting one
#   MODEL_PROXY_KEY=...    Key for that proxy (generated for a local proxy)
#   ENV_FILE=<path>        Optional env file passed to eval/run.py and kit check
#   HF_TOKEN=...           Hugging Face read token
#   TASKS=a,b              Run only these dev tasks (default: all 29)
#   TRIALS=N               Parallel tasks for eval/run.py
#   REBUILD=1              Force a harness image rebuild in kit check
#   DRY_RUN=1              Validate paths/configuration; print commands only
#   AUTO_CONFIRM=1         Do not prompt before the full dev-set run
#   PUSH=1                 Push the branch and stage2-eval tag after kit check
# ==============================================================================

set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
AUTO_CONFIRM="${AUTO_CONFIRM:-0}"
PUSH="${PUSH:-0}"
export DRY_RUN AUTO_CONFIRM PUSH

say()  { printf '%s\n' "$*"; }
die()  { printf '[!] %s\n' "$*" >&2; exit 1; }

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
[ -f "$REPO_ROOT/serve.py" ] || die "REPO_ROOT ($REPO_ROOT) does not look like the entry repository (serve.py missing)."
[ -f "$REPO_ROOT/submission.yaml" ] || die "REPO_ROOT ($REPO_ROOT) has no submission.yaml."

say "================================================================================"
say "         ANTIGRAVITY PE FRONTIER: STAGE 2 REPRODUCTION PIPELINE                 "
say "================================================================================"

# ------------------------------------------------------------------------------
# 0. Locate the PLE benchmark checkout and the Docker/root helpers
# ------------------------------------------------------------------------------
resolve_ple_repo() {
    local candidate
    local -a candidates=(
        "${PLE_REPO:-}"
        "$REPO_ROOT/../ple-repo"
        "$REPO_ROOT/../../ple-repo"
        "$REPO_ROOT/../kaggle/competitions/kaggle-physical-engineerings-last-exam/ple-repo"
        "$HOME/kaggle/competitions/kaggle-physical-engineerings-last-exam/ple-repo"
    )
    for candidate in "${candidates[@]}"; do
        [ -n "$candidate" ] || continue
        if [ -f "$candidate/eval/run.py" ] && [ -f "$candidate/kit/__main__.py" ]; then
            (cd "$candidate" && pwd)
            return 0
        fi
    done
    # Last resort: a shallow search under $HOME for a PLE checkout.
    while IFS= read -r candidate; do
        if [ -f "$candidate/eval/run.py" ] && [ -f "$candidate/kit/__main__.py" ]; then
            (cd "$candidate" && pwd)
            return 0
        fi
    done < <(find "$HOME" -maxdepth 6 -type d -name ple-repo 2>/dev/null | head -n 20)
    return 1
}

PLE_REPO="$(resolve_ple_repo)" || die "Could not find the PLE benchmark checkout. Set PLE_REPO=/path/to/ple-repo."
say "[+] Entry repository: $REPO_ROOT"
say "[+] PLE benchmark:    $PLE_REPO"

if [ "$EUID" -eq 0 ]; then
    SUDO=()
elif command -v sudo >/dev/null 2>&1; then
    SUDO=(sudo)
else
    die "Root access or sudo is required to install Docker and system packages."
fi
export PLE_REPO

as_root() {
    if [ "${#SUDO[@]}" -eq 0 ]; then "$@"; else "${SUDO[@]}" "$@"; fi
}
do_root() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '    [dry-run]'; printf ' %q' "$@"; printf '\n'
    else
        as_root "$@"
    fi
}
do_cmd() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '    [dry-run]'; printf ' %q' "$@"; printf '\n'
    else
        "$@"
    fi
}
run_in_ple() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '    [dry-run] (cd %q &&' "$PLE_REPO"; printf ' %q' "$@"; printf ')\n'
    else
        ( cd "$PLE_REPO" && "$@" )
    fi
}
proxy_is_up() {
    local url="${1%/}" code
    code="$(curl -s -o /dev/null --max-time 3 -w '%{http_code}' "$url/health/liveliness" || true)"
    [ -n "$code" ] && [ "$code" != "000" ]
}

# ------------------------------------------------------------------------------
# 1. System packages and Docker
# ------------------------------------------------------------------------------
say "[+] Step 1: Checking Docker and system prerequisites..."
if [ "$DRY_RUN" != "1" ] && ! command -v docker >/dev/null 2>&1; then
    command -v apt-get >/dev/null 2>&1 || die "This runbook targets Ubuntu/Debian (apt-get not found)."
    do_root apt-get update -y
    do_root apt-get install -y docker.io curl git openssl ca-certificates
fi
if [ "$DRY_RUN" != "1" ]; then
    runtime_missing=()
    command -v curl >/dev/null 2>&1 || runtime_missing+=(curl)
    command -v git >/dev/null 2>&1 || runtime_missing+=(git)
    command -v openssl >/dev/null 2>&1 || runtime_missing+=(openssl)
    if [ "${#runtime_missing[@]}" -gt 0 ]; then
        command -v apt-get >/dev/null 2>&1 || die "Missing ${runtime_missing[*]}; apt-get is required to install them."
        do_root apt-get update -y
        do_root apt-get install -y "${runtime_missing[@]}"
    fi
    command -v docker >/dev/null 2>&1 || die "Docker installation failed."
    as_root systemctl enable --now docker >/dev/null 2>&1 || true
fi

if [ "$DRY_RUN" != "1" ]; then
    if ! docker info >/dev/null 2>&1; then
        # usermod edits /etc/group immediately, but the current shell keeps its
        # old supplementary groups. Re-exec under `sg docker` instead of asking
        # the operator to log out and back in.
        if ! getent group docker 2>/dev/null | grep -qE "(^|[:,])${USER}(,|$)"; then
            say "[+] Adding $USER to the docker group..."
            as_root usermod -aG docker "$USER" || true
        fi
        if [ "${PLE_DOCKER_REEXEC:-0}" != "1" ] && command -v sg >/dev/null 2>&1; then
            export PLE_DOCKER_REEXEC=1
            say "[*] Docker group membership is not active in this shell; re-executing under 'sg docker'..."
            exec sg docker -c "$(printf '%q ' "$SCRIPT_PATH" "$@")"
        fi
        die "Docker daemon is not reachable. Start it ('sudo systemctl start docker') and log out/in, then rerun."
    fi
    say "[+] Docker: $(docker --version)"
else
    say "    [dry-run] docker info"
fi

# ------------------------------------------------------------------------------
# 2. uv and Harbor
# ------------------------------------------------------------------------------
say "[+] Step 2: Checking uv and Harbor..."
if [ "$DRY_RUN" != "1" ] && ! command -v uv >/dev/null 2>&1; then
    do_cmd sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
export PATH="$HOME/.local/bin:$PATH"
if [ "$DRY_RUN" != "1" ]; then
    command -v uv >/dev/null 2>&1 || die "uv installation failed."
    say "[+] uv: $(uv --version)"
    if ! uv tool list 2>/dev/null | grep -qE '^harbor v?0\.20\.0'; then
        say "[+] Installing Harbor 0.20.0 with websockets..."
        do_cmd uv tool install --force harbor==0.20.0 --with websockets
    fi
    command -v harbor >/dev/null 2>&1 || die "Harbor installation failed; check 'uv tool list'."
else
    say "    [dry-run] uv tool install --force harbor==0.20.0 --with websockets"
fi

# ------------------------------------------------------------------------------
# 3. Hugging Face access
# ------------------------------------------------------------------------------
say "[+] Step 3: Checking Hugging Face access..."
if [ -z "${HF_TOKEN:-}" ] \
    && [ ! -f "$HOME/.cache/huggingface/token" ] \
    && [ ! -f "$HOME/.huggingface/token" ]; then
    if [ "$DRY_RUN" = "1" ] || [ "$AUTO_CONFIRM" = "1" ] || [ ! -t 0 ]; then
        say "[!] HF_TOKEN is not set and no cached token was found."
        say "    The dev-set dataset is gated; export HF_TOKEN or run 'uv run hf auth login'."
        [ "$DRY_RUN" = "1" ] || die "Missing Hugging Face credentials."
    else
        say "[!] HF_TOKEN is not set."
        say "    Generate a read token at https://huggingface.co/settings/tokens"
        read -rsp "    Enter HF_TOKEN: " HF_TOKEN
        say ""
        export HF_TOKEN
        [ -n "$HF_TOKEN" ] || die "HF_TOKEN cannot be empty."
    fi
fi

# ------------------------------------------------------------------------------
# 4. Model proxy (Vertex AI only)
# ------------------------------------------------------------------------------
say "[+] Step 4: Configuring the model proxy..."
MODEL_PROXY_URL="${MODEL_PROXY_URL:-http://localhost:4000}"
export MODEL_PROXY_URL
PROXY_PID=""

cleanup() {
    local status=$?
    trap - EXIT
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        say "[*] Stopping local model proxy (PID $PROXY_PID)..."
        kill "$PROXY_PID" 2>/dev/null || true
        wait "$PROXY_PID" 2>/dev/null || true
    fi
    exit "$status"
}
trap cleanup EXIT

if proxy_is_up "$MODEL_PROXY_URL"; then
    [ -n "${MODEL_PROXY_KEY:-}" ] || die "A model proxy is already listening at $MODEL_PROXY_URL; set MODEL_PROXY_KEY."
    say "[+] Using the existing model proxy at $MODEL_PROXY_URL"
else
    local_url=0
    case "$MODEL_PROXY_URL" in
        http://localhost:*|http://127.0.0.1:*|http://0.0.0.0:*) local_url=1 ;;
    esac

    if [ -z "${VERTEXAI_PROJECT:-}" ]; then
        say "[!] The kit model proxy serves google-cloud models from Vertex AI only."
        say "    Set VERTEXAI_PROJECT=<gcp-project> (and ADC), or point MODEL_PROXY_URL/KEY"
        say "    at an already-running proxy."
        [ "$DRY_RUN" = "1" ] || die "Missing Vertex AI configuration."
    elif [ "$local_url" != "1" ]; then
        [ "$DRY_RUN" = "1" ] || die "MODEL_PROXY_URL=$MODEL_PROXY_URL is not reachable and is not local."
    else
        MODEL_PROXY_KEY="${MODEL_PROXY_KEY:-$(openssl rand -hex 24)}"
        export MODEL_PROXY_KEY VERTEXAI_PROJECT

        # Keep the proxy's bind port in sync with the URL we health-check.
        proxy_hostport="${MODEL_PROXY_URL#*://}"
        proxy_hostport="${proxy_hostport%%/*}"
        if [ "$proxy_hostport" != "${proxy_hostport##*:}" ]; then
            MODEL_PROXY_PORT="${MODEL_PROXY_PORT:-${proxy_hostport##*:}}"
            export MODEL_PROXY_PORT
        fi

        if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && command -v gcloud >/dev/null 2>&1; then
            if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
                say "[!] No Application Default Credentials detected."
                say "    Run: gcloud auth application-default login"
                [ "$DRY_RUN" = "1" ] || die "Vertex AI credentials are missing."
            fi
        elif [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
            say "[!] gcloud not found; ensure ADC is available (e.g. a GCP VM service account)"
            say "    or set GOOGLE_APPLICATION_CREDENTIALS to a service-account key."
        fi

        say "[+] Starting the Vertex AI model proxy at $MODEL_PROXY_URL ..."
        mkdir -p "$REPO_ROOT/runs"
        if [ "$DRY_RUN" = "1" ]; then
            say "    [dry-run] (cd $PLE_REPO && ./kit/model_proxy/start.sh) &"
        else
            ( cd "$PLE_REPO" && ./kit/model_proxy/start.sh ) \
                >"$REPO_ROOT/runs/model_proxy.log" 2>&1 &
            PROXY_PID=$!
            for _ in $(seq 1 60); do
                proxy_is_up "$MODEL_PROXY_URL" && break
                if ! kill -0 "$PROXY_PID" 2>/dev/null; then
                    tail -n 40 "$REPO_ROOT/runs/model_proxy.log" >&2 || true
                    die "The model proxy exited during startup. See $REPO_ROOT/runs/model_proxy.log"
                fi
                sleep 2
            done
            proxy_is_up "$MODEL_PROXY_URL" || {
                tail -n 40 "$REPO_ROOT/runs/model_proxy.log" >&2 || true
                die "The model proxy did not become reachable at $MODEL_PROXY_URL."
            }
            say "[+] Model proxy ready (PID $PROXY_PID)."
        fi
    fi
fi

# ------------------------------------------------------------------------------
# 5. Validate the entry (no Docker)
# ------------------------------------------------------------------------------
say "[+] Step 5: Validating submission.yaml ..."
run_in_ple uv run python -m kit validate "$REPO_ROOT"

# ------------------------------------------------------------------------------
# 6. Full dev-set reproduction
# ------------------------------------------------------------------------------
say "================================================================================"
say "[+] Step 6: Running the public dev set via eval/run.py ..."
say "    Fresh outputs are written to $REPO_ROOT/artifacts/."
if [ -n "${TASKS:-}" ]; then
    say "    Tasks:  $TASKS"
else
    say "    Tasks:  all 29 public dev tasks"
fi
say "    Expect several hours on an 8-CPU VM (Harbor builds large world images)."
say "================================================================================"

if [ "$AUTO_CONFIRM" != "1" ]; then
    [ -t 0 ] || die "Non-interactive shell: set AUTO_CONFIRM=1 to start the run."
    read -rp "Start the dev-set run now? (y/N): " CONFIRM
    [[ "$CONFIRM" =~ ^[Yy]$ ]] || die "Aborted by operator."
fi

EVAL_ARGS=("$REPO_ROOT")
[ -n "${TASKS:-}" ] && EVAL_ARGS+=(--tasks "$TASKS")
[ -n "${TRIALS:-}" ] && EVAL_ARGS+=(--trials "$TRIALS")
[ -n "${ENV_FILE:-}" ] && EVAL_ARGS+=(--env-file "$ENV_FILE")
run_in_ple uv run python eval/run.py "${EVAL_ARGS[@]}"

# ------------------------------------------------------------------------------
# 7. Review, commit, check, tag
# ------------------------------------------------------------------------------
[ -d "$REPO_ROOT/artifacts" ] || die "eval/run.py did not produce $REPO_ROOT/artifacts."
say "[+] Step 7: Reviewing the fresh artifacts with the server's rules..."
run_in_ple uv run python -m kit artifacts "$REPO_ROOT"

if [ "$DRY_RUN" != "1" ]; then
    say "[+] Step 8: Committing only artifacts/ ..."
    git -C "$REPO_ROOT" add -A -- artifacts
    if git -C "$REPO_ROOT" diff --cached --quiet -- artifacts; then
        say "[*] No artifact changes to commit; reusing the existing commit."
    else
        if git -C "$REPO_ROOT" diff --cached --name-only -- artifacts | grep -q '__pycache__'; then
            die "Refusing to commit __pycache__; fix .gitignore and unstage it."
        fi
        git -C "$REPO_ROOT" commit -m "feat(stage2): authentic 29-task dev-set reproduction and manifest" -- artifacts
    fi

    if [ -n "$(git -C "$REPO_ROOT" status --porcelain -- . ':(exclude)artifacts' ':(exclude)runs')" ]; then
        say "[!] Warning: uncommitted changes remain outside artifacts/."
        say "    Commit the harness before submitting; kit check reads the working tree."
    fi

    say "[+] Step 9: Running the full readiness check (Docker build + smoke test)..."
    CHECK_ARGS=("$REPO_ROOT")
    [ -n "${ENV_FILE:-}" ] && CHECK_ARGS+=(--env-file "$ENV_FILE")
    [ "${REBUILD:-0}" = "1" ] && CHECK_ARGS+=(--rebuild)
    CHECK_LOG="$REPO_ROOT/runs/kit_check.log"
    mkdir -p "$REPO_ROOT/runs"
    if ! run_in_ple uv run python -m kit check "${CHECK_ARGS[@]}" 2>&1 | tee "$CHECK_LOG"; then
        die "'kit check' failed. Full log: $CHECK_LOG"
    fi
    grep -q 'ready to submit' "$CHECK_LOG" \
        || die "'kit check' did not report 'ready to submit'. Full log: $CHECK_LOG"

    say "[+] Step 10: Tagging stage2-eval ..."
    git -C "$REPO_ROOT" tag -f stage2-eval
    STAGE2_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"

    if [ "$PUSH" = "1" ]; then
        BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
        [ "$BRANCH" != "HEAD" ] || die "Cannot push a detached HEAD."
        say "[+] Pushing $BRANCH and stage2-eval ..."
        git -C "$REPO_ROOT" push origin "$BRANCH"
        git -C "$REPO_ROOT" push -f origin stage2-eval
    fi

    say "================================================================================"
    say "  STAGE 2 REPRODUCTION COMPLETE"
    say "  Commit:   $STAGE2_SHA"
    say "  Tag:      stage2-eval (local; set PUSH=1 to publish)"
    say "  Artifacts reviewed and 'kit check' reported ready to submit."
    say "================================================================================"
else
    say "[+] Dry run complete. No files were modified."
    say "    Re-run with DRY_RUN=0 (and credentials set) to reproduce the dev set."
fi
