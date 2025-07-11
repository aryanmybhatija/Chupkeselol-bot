# Use a lightweight Python image
FROM python:3.11-slim-bookworm

# Set environment variables
# Kolkata timezone (IST - UTC+5:30)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    TZ=Asia/Kolkata

# Set timezone and install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    aria2 \
    ffmpeg \
    procps \
    wget \
    gnupg \
    ca-certificates \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create download directory and fix permissions
RUN mkdir -p downloads \
    && chmod 777 downloads

# Fix permissions for authorized_users.json
RUN if [ -f "authorized_users.json" ]; then chmod 664 authorized_users.json; fi   

# Copy and prepare entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose Flask port
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Start the bot
CMD ["python", "noor.py"]
