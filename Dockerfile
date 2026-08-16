FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-libmysqlclient-dev pkg-config gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --timeout-keep-alive above uvicorn's 5s default: services/load-test found
# that a persistent HTTP connection idle for 5-6s (routine under bursty
# concurrent traffic) races against the server closing it, so a client
# reusing that socket sees "Remote end closed connection without response"
# on its next request. 30s comfortably outlasts realistic client idle gaps.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 30"]
