FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY GraphQL/ .

EXPOSE 8004

CMD ["python", "graphql_delete.py"]
