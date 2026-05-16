FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data/processed ./data/processed
COPY data/physics ./data/physics
COPY data/resources ./data/resources
COPY data/business ./data/business
COPY data/tutoring ./data/tutoring
COPY data/biology/processed/questions.json ./data/biology/processed/questions.json
COPY data/biology/processed/manual_papers.json ./data/biology/processed/manual_papers.json
COPY data/chemistry/processed/questions.json ./data/chemistry/processed/questions.json
COPY data/chemistry/processed/manual_papers.json ./data/chemistry/processed/manual_papers.json
COPY data/topic-map.json ./data/topic-map.json
COPY server.py ./server.py

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8080", "server:app"]
