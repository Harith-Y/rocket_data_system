FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make the setup script executable
RUN chmod +x setup.sh

# Run the setup script
RUN ./setup.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 8000

# Start the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
