# Use an official Python runtime as a parent image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY Backend/ .

# Copy chunks.json into the container (expected at docs/chunks.json relative to repo root)
# When building from the repo root, the docs/ folder should be available.
COPY docs/chunks.json /app/docs/chunks.json

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
