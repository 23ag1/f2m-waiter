FROM python:3.11-slim

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .

# Данные движка
RUN mkdir -p /app/engine_data

EXPOSE 1488

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1488"]
