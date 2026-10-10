FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LINGUAWALK_DB_PATH=/app/data/linguawalk.db

WORKDIR /app

RUN groupadd --gid 10001 linguawalk \
    && useradd --uid 10001 --gid linguawalk --no-create-home --shell /usr/sbin/nologin linguawalk

COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY --chown=linguawalk:linguawalk app.py config.py consolidation.py db.py learning.py models.py schema.sql ./
RUN mkdir -p /app/data && chown linguawalk:linguawalk /app/data

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
