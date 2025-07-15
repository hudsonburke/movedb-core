FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml .
RUN pip install -e .

# Copy source code
COPY src/ ./src/
COPY README.md LICENSE ./

# Install the package in development mode
RUN pip install -e .

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "movedb.api.cli", "serve"]
