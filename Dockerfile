# Start from the base Python image
FROM python:3.11-slim

# Install OpenJDK
RUN apt-get update && \
    apt-get install -y openjdk-11-jre && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME (optional but helpful)
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Verify Java installation
RUN java -version

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables for Gunicorn
ENV GUNICORN_CMD_ARGS="--workers 3 --bind 0.0.0.0:8000"

# Command to run the application
CMD ["gunicorn", "app:app"]
