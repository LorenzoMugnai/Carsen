FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN python -m pip install --no-cache-dir .

USER nobody
ENTRYPOINT ["carsen"]
CMD ["status"]
