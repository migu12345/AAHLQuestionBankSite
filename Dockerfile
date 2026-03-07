FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data/processed ./data/processed
COPY data/resources ./data/resources
COPY data/business ./data/business
COPY data/tutoring ./data/tutoring
COPY data/topic-map.json ./data/topic-map.json
COPY server.py ./server.py

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8080", "server:app"]
