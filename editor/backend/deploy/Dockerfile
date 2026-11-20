FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY editor/backend/requirements.txt /tmp/olv-requirements.txt
RUN pip install --no-cache-dir -r /tmp/olv-requirements.txt && useradd --uid 10001 --create-home olv && mkdir -p /var/lib/olv && chown olv:olv /var/lib/olv
COPY --chown=olv:olv . /app
USER olv
ENV OLV_STATE_DIR=/var/lib/olv
EXPOSE 8080
CMD ["gunicorn", "editor.backend.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "180", "--access-logfile", "-", "--error-logfile", "-"]
