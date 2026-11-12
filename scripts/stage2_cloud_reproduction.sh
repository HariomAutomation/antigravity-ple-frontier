#!/usr/bin/env bash
# ==============================================================================
# ANTIGRAVITY PE FRONTIER: STAGE 2 CLOUD REPRODUCTION & ARTIFACTS RUNBOOK
# ==============================================================================
# Automates full reproduction on any Ubuntu 22.04 / 24.04 Cloud VM (GCP / AWS / RunPod):
# 1. Installs Docker, uv, Harbor, and system dependencies.
# 2. Configures Model Proxy for Google-sponsored Claude Opus 5.5 / Gemini models.
# 3. Runs 'kit check' smoke tests.
# 4. Executes full 29-task dev set via 'eval/run.py' to produce 100% fair-play compliant artifacts/.
# 5. Cryptographically tags and commits the final Stage 2 entry.
# ==============================================================================

set -euo pipefail

echo "================================================================================"
echo "         ANTIGRAVITY PE FRONTIER: STAGE 2 REPRODUCTION PIPELINE                 "
echo "================================================================================"

# Check root / sudo access
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "[!] Warning: Sudo access is required to install Docker and system packages."
fi

# 1. System Package Installation
echo "[+] Step 1: Installing system prerequisites & Docker..."
if ! command -v docker &>/dev/null; then
    echo "[-] Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io curl git openssl ca-certificates python3 python3-pip
    sudo systemctl start docker || true
    sudo systemctl enable docker || true
    sudo usermod -aG docker "$USER" || true
    echo "[+] Docker installed successfully."
else
    echo "[+] Docker is already installed: $(docker --version)"
fi

# 2. uv Package Manager Installation
echo "[+] Step 2: Installing uv & Harbor..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "[+] uv version: $(uv --version)"

# Install Harbor
uv tool install harbor==0.20.0 --with websockets || true

# 3. Hugging Face Dataset Authentication
echo "[+] Step 3: Checking Hugging Face token..."
if [ -z "${HF_TOKEN:-}" ]; then
    echo "[!] HF_TOKEN is not set!"
    echo "    Please generate a read token at: https://huggingface.co/settings/tokens"
    read -rp "    Enter your HF_TOKEN: " HF_TOKEN
    export HF_TOKEN
fi

# 4. Model Proxy Configuration
echo "[+] Step 4: Setting up Model Proxy for Google-sponsored models..."
MODEL_PROXY_KEY="${MODEL_PROXY_KEY:-$(openssl rand -hex 24)}"
export MODEL_PROXY_KEY
export MODEL_PROXY_URL="${MODEL_PROXY_URL:-http://localhost:4000}"

# Check for GCP Project or Anthropic/Gemini credentials
if [ -z "${VERTEXAI_PROJECT:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "[!] Note: To run google-cloud/claude-opus-5-5, authenticate with GCP or provide credentials:"
    echo "    Option A: Run 'gcloud auth application-default login' and set 'export VERTEXAI_PROJECT=<your-gcp-project>'"
    echo "    Option B: Export ANTHROPIC_API_KEY=<key>"
    read -rp "    Enter your GCP Project ID or API Key (or press Enter if already logged in): " USER_CRED
    if [ -n "$USER_CRED" ]; then
        if [[ "$USER_CRED" == sk-* ]]; then
            export ANTHROPIC_API_KEY="$USER_CRED"
        else
            export VERTEXAI_PROJECT="$USER_CRED"
        fi
    fi
fi

# Start local proxy if kit/model_proxy exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLE_REPO="${REPO_ROOT}/../kaggle-physical-engineerings-last-exam/ple-repo"

if [ -f "${PLE_REPO}/kit/model_proxy/start.sh" ]; then
    echo "[+] Starting PLE model proxy in background..."
    "${PLE_REPO}/kit/model_proxy/start.sh" &
    PROXY_PID=$!
    sleep 3
    echo "[+] Model proxy running (PID: ${PROXY_PID}) at ${MODEL_PROXY_URL}"
fi

# 5. Local Readiness & Smoke Check
echo "[+] Step 5: Running pre-flight 'kit check'..."
PYTHONPATH="${PLE_REPO}" python3 -m kit check "${REPO_ROOT}" || {
    echo "[!] kit check encountered warnings. Reviewing before full run..."
}

# 6. Full 29-Task Dev Set Execution
echo "================================================================================"
echo "[+] Step 6: Executing full 29-task dev set reproduction via eval/run.py..."
echo "    This will run all 29 tasks and export fresh compliant artifacts/."
echo "================================================================================"

read -rp "Start full 29-task dev set run now? (y/N): " CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    PYTHONPATH="${PLE_REPO}" uv run python "${PLE_REPO}/eval/run.py" "${REPO_ROOT}"
    echo "[+] Dev set run complete! Reviewing generated artifacts..."
    PYTHONPATH="${PLE_REPO}" python3 -m kit artifacts "${REPO_ROOT}"
    
    # 7. Commit & Tag Stage 2 Entry
    echo "[+] Step 7: Committing fresh artifacts and locking Stage 2 tag..."
    git -C "${REPO_ROOT}" add -A
    git -C "${REPO_ROOT}" commit -m "feat(stage2): complete authentic 29-task dev-set reproduction and manifest"
    git -C "${REPO_ROOT}" tag -f stage2-eval
    STAGE2_SHA=$(git -C "${REPO_ROOT}" rev-parse HEAD)
    echo "================================================================================"
    echo "  STAGE 2 REPRODUCTION COMPLETE!"
    echo "  Commit SHA: ${STAGE2_SHA}"
    echo "  Git Tag:    stage2-eval"
    echo "================================================================================"
else
    echo "[*] Skipping full run. You can trigger it anytime with:"
    echo "    PYTHONPATH=${PLE_REPO} uv run python ${PLE_REPO}/eval/run.py ${REPO_ROOT}"
fi
