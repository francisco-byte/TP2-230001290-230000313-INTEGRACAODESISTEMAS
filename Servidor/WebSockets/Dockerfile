FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY WebSockets/ .

EXPOSE 6789

CMD ["python", "websocket_server.py"]