FROM python:3.9-slim

WORKDIR /graphql_delete

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8004

CMD ["uvicorn", "graphql_delete:app", "--host", "0.0.0.0", "--port", "8004"]
