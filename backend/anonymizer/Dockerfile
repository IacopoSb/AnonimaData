# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for building some Python packages (e.g., pandas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
COPY . .

# The GOOGLE_CLOUD_PROJECT_ID environment variable will be set by Terraform
# in the deployment environment (e.g., Kubernetes, Cloud Run, GCE).
# Ensure your Terraform configuration sets this environment variable for the container.

# Expose the port if your service were to accept incoming HTTP requests directly.
# (Not strictly necessary for a Pub/Sub consumer, but good practice if it ever expands)
# EXPOSE 8080 

# Run anonymization_service.py when the container launches
CMD ["python", "anonymization_service.py"]