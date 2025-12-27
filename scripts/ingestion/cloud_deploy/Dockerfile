FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy logic and data
COPY main.py .
COPY data.json .

# Set specific environment variable for script to find data
ENV DATA_FILE_PATH="data.json"

# Run ingestion
CMD ["python", "main.py"]
