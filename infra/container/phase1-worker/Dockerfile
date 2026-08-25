# syntax=docker/dockerfile:1

FROM docker.io/library/python@sha256:7f7ee17311e0273954ffe76a7b84a2d8c8ecf16f9992e780e4d46c86175df431 AS dependencies

ARG UV_VERSION=0.11.32
WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services ./services
COPY workers ./workers

RUN python -m pip install --disable-pip-version-check --no-cache-dir "uv==${UV_VERSION}" \
    && uv export \
        --locked \
        --package opintel-research-worker \
        --package opintel-intelligence-worker \
        --no-dev \
        --no-emit-workspace \
        --no-annotate \
        --no-header \
        --output-file /tmp/runtime-requirements.txt \
    && python -m pip install \
        --disable-pip-version-check \
        --no-cache-dir \
        --require-hashes \
        --prefix /runtime \
        --requirement /tmp/runtime-requirements.txt

FROM docker.io/library/python@sha256:7f7ee17311e0273954ffe76a7b84a2d8c8ecf16f9992e780e4d46c86175df431

ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="opportunity-intelligence-platform" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.title="M6.7 Phase 1 bounded research worker"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/m0-core:/app/m0-local:/app/research-core:/app/research-local:/app/opportunity-core:/app/opportunity-local:/app/audit-core:/app/audit-local:/app/demo-core:/app/demo-local:/app/outreach-core:/app/outreach-local:/app/shadow-core:/app/research-worker:/app/intelligence-worker

COPY --from=dependencies /runtime /usr/local
COPY packages/m0-core/src /app/m0-core
COPY packages/m0-local/src /app/m0-local
COPY packages/research-core/src /app/research-core
COPY packages/research-local/src /app/research-local
COPY packages/opportunity-core/src /app/opportunity-core
COPY packages/opportunity-local/src /app/opportunity-local
COPY packages/audit-core/src /app/audit-core
COPY packages/audit-local/src /app/audit-local
COPY packages/demo-core/src /app/demo-core
COPY packages/demo-local/src /app/demo-local
COPY packages/outreach-core/src /app/outreach-core
COPY packages/outreach-local/src /app/outreach-local
COPY packages/shadow-core/src /app/shadow-core
COPY workers/research/src /app/research-worker
COPY workers/intelligence/src /app/intelligence-worker

# The upstream Python runtime includes pip and its vendored build/network packages. The worker does
# not install packages at runtime, so remove that tooling and its stale vendored metadata entirely.
RUN apk add --no-cache --upgrade \
        libcrypto3=3.5.7-r0 \
        libssl3=3.5.7-r0 \
        xz-libs=5.8.3-r0 \
    && python -m pip check \
    && rm -rf \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.13 \
        /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-*.dist-info

USER 65532:65532
ENTRYPOINT ["python", "-m", "opintel_research_worker.main"]
