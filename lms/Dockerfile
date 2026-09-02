FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LLOVES_DB=/data/lloves.sqlite
ENV HOST=0.0.0.0
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY lms/requirements.txt lms/requirements.txt
RUN pip install --no-cache-dir -r lms/requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--workers", "1", "--timeout", "120", "--bind", "0.0.0.0:8080", "--chdir", "lms", "app:create_app()"]
