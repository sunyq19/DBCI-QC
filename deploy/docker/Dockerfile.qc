FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    MPLCONFIGDIR=/data/.matplotlib XDG_CACHE_HOME=/data/.cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates libgomp1 fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements/workbench.txt /tmp/workbench.txt
# Obtain external packages from their original sources during installation.
RUN pip install --no-cache-dir -r /tmp/workbench.txt && pip check
COPY . /app
RUN pip install --no-cache-dir --no-deps . && \
    useradd --uid 10001 --create-home dbciqc && \
    mkdir -p /data && chown -R 10001:10001 /data && \
    pip freeze > /app/deploy/docker/installed-requirements.txt
USER 10001:10001
EXPOSE 18769
CMD ["python", "/app/deploy/docker/qc_entrypoint.py"]
