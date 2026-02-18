# syntax=docker/dockerfile:1.7

FROM python:3.11-slim@sha256:543d6cace00ffc96bc95d332493bb28a4332c6dd614aab5fcbd649ae8a7953d9

LABEL org.opencontainers.image.title="HyRISE" \
      org.opencontainers.image.description="HIV Resistance Interpretation and Visualization System runtime image" \
      org.opencontainers.image.source="https://github.com/phac-nml/HyRISE" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

ARG SIERRALOCAL_REF=428ebf9e7908cdf5a5aa5ab192c11ddd457aa132
ARG POSTALIGN_REF=6bcc53044ff6c73d97d3a56b0643fe6ba8bc862f

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        git \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/hyrise
COPY pyproject.toml setup.py README.md LICENSE AUTHORS.md MANIFEST.in ./
COPY src ./src

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "git+https://github.com/hivdb/post-align.git@${POSTALIGN_REF}" \
    && python -m pip install "git+https://github.com/PoonLab/sierra-local.git@${SIERRALOCAL_REF}" \
    && python -m pip install . \
    && python -m pip install "multiqc==1.33" \
    && python -m pip check

RUN useradd --create-home --home-dir /home/hyrise --shell /usr/sbin/nologin hyrise \
    && mkdir -p /data /home/hyrise/.config/hyrise /home/hyrise/.local/share/hyrise \
    && chown -R hyrise:hyrise /data /home/hyrise

USER hyrise
WORKDIR /data

ENTRYPOINT ["tini", "--", "hyrise"]
CMD ["--help"]
