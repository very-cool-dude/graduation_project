FROM python:3.10-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

CMD ["sh", "-c", "echo '' > logs/generator.log && uvicorn generator:app --host 0.0.0.0 --port 8005"]
