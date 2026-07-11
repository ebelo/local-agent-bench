FROM node:26.1.0-bookworm-slim AS node-runtime

FROM python:3.12-slim

ARG INSTALL_AGENT_RUNTIMES=0
ARG OPENCLAW_VERSION=2026.6.11
ARG PI_VERSION=0.80.3
ARG HERMES_REPO=https://github.com/NousResearch/hermes-agent.git
ARG HERMES_REF=f64e4f4f5768c18a53f44890747653bafcab2796

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OLLAMA_BASE_URL=http://ollama:11434 \
    PATH=/usr/local/bin:/opt/hermes/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git jq libatomic1 \
    && git config --global --add safe.directory /workspace/local-agent-bench \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

WORKDIR /workspace/local-agent-bench

COPY pyproject.toml README.md ./
COPY local_agent_bench ./local_agent_bench
COPY benchmarks ./benchmarks
COPY runners ./runners
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir pytest \
    && pip install --no-cache-dir -e .

RUN if [ "$INSTALL_AGENT_RUNTIMES" = "1" ]; then \
        npm install -g "openclaw@${OPENCLAW_VERSION}" "@earendil-works/pi-coding-agent@${PI_VERSION}" \
        && python3 -m venv /opt/hermes \
        && /opt/hermes/bin/pip install --no-cache-dir --upgrade pip \
        && /opt/hermes/bin/pip install --no-cache-dir "git+${HERMES_REPO}@${HERMES_REF}" \
        && ln -sf /opt/hermes/bin/hermes /usr/local/bin/hermes \
        && ln -sf /opt/hermes/bin/hermes-acp /usr/local/bin/hermes-acp \
        && ln -sf /opt/hermes/bin/hermes-agent /usr/local/bin/hermes-agent; \
    fi

CMD ["python3", "-m", "local_agent_bench", "diagnose", "--runtime", "raw-ollama-react", "--model", "qwen2.5-coder:7b"]
