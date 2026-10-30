FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir Flask==2.2.5 gunicorn

COPY app.py .

EXPOSE 8025

CMD ["gunicorn", "--bind", "0.0.0.0:8025", "--workers", "1", "app:app"]
