FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY config/ config/
COPY src/ src/
COPY sql/ sql/
COPY main.py .

# Create data and report directories, then drop root privileges
RUN mkdir -p data/raw data/processed data/database reports logs \
    && useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["--mode", "full"]
