# syntax=docker/dockerfile:1

FROM docker.io/library/python@sha256:0f16c5d35fe6464ee471792ab3bb9116f911b65b3fbf10120c98d2bdc6332f48 AS dependencies

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

FROM docker.io/library/python@sha256:0f16c5d35fe6464ee471792ab3bb9116f911b65b3fbf10120c98d2bdc6332f48

ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="opportunity-intelligence-platform" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.title="M6.7 Phase 1 bounded research worker"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/m0-core:/app/research-core:/app/research-local:/app/research-worker

COPY --from=dependencies /runtime /usr/local
COPY packages/m0-core/src /app/m0-core
COPY packages/research-core/src /app/research-core
COPY packages/research-local/src /app/research-local
COPY workers/research/src /app/research-worker

# The upstream Python runtime includes pip and its vendored build/network packages. The worker does
# not install packages at runtime, so remove that tooling and its stale vendored metadata entirely.
RUN python -m pip check \
    && rm -rf \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.13 \
        /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-*.dist-info

USER 65532:65532
ENTRYPOINT ["python", "-m", "opintel_research_worker.main"]
