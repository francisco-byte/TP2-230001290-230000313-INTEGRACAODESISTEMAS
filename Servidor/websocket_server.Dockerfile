FROM python:3.9-slim

WORKDIR /app

COPY websocket_server.py /app/websocket_server.py

RUN pip install websockets

CMD ["python", "websocket_server.py"]
