FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY static/ static/
COPY sample-docs/ sample-docs/
COPY .env.example .env.example

RUN mkdir -p data/chroma data/uploads

ENV HF_ENDPOINT=https://hf-mirror.com
ENV EMBEDDING_PROVIDER=local

EXPOSE 8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
