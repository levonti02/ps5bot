FROM python:3.11-slim

WORKDIR /opt/ps5bot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]
