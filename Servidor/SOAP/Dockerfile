FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY SOAP/ .
EXPOSE 8002
CMD ["python", "app.py"]