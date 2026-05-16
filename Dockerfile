FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY server.py ./server.py

# JSON data files (images are served from Cloudflare R2)
COPY data/topic-map.json ./data/topic-map.json
COPY data/processed/questions.json ./data/processed/questions.json
COPY data/processed/manual_papers.json ./data/processed/manual_papers.json
COPY data/processed/physics_manual_papers.json ./data/processed/physics_manual_papers.json
COPY data/biology/topic-map.json ./data/biology/topic-map.json
COPY data/biology/processed/questions.json ./data/biology/processed/questions.json
COPY data/biology/processed/manual_papers.json ./data/biology/processed/manual_papers.json
COPY data/chemistry/topic-map.json ./data/chemistry/topic-map.json
COPY data/chemistry/processed/questions.json ./data/chemistry/processed/questions.json
COPY data/chemistry/processed/manual_papers.json ./data/chemistry/processed/manual_papers.json
COPY data/physics/topic-map.json ./data/physics/topic-map.json
COPY data/physics/processed/questions.json ./data/physics/processed/questions.json
COPY data/physics/processed/manual_papers.json ./data/physics/processed/manual_papers.json
COPY data/business/topic-map.json ./data/business/topic-map.json
COPY data/business/processed/questions.json ./data/business/processed/questions.json
COPY data/tutoring/processed/questions.json ./data/tutoring/processed/questions.json
COPY data/tutoring/processed/markschemes.json ./data/tutoring/processed/markschemes.json

# Formula booklets (PDFs served same-origin)
COPY data/resources ./data/resources

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8080", "server:app"]
