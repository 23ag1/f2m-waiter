FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV UPLOAD_DIR=/data/uploads
VOLUME ["/data/uploads"]

EXPOSE 5050

CMD ["python", "app.py"]
