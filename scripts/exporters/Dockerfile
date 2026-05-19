# syntax=docker/dockerfile:1.7
FROM python:3.12-slim
WORKDIR /app
COPY cron_exporter.py .
EXPOSE 9101
CMD ["python3", "cron_exporter.py"]
