# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
# Including the 'templates' directory if you have one for Flask
COPY . .

# Expose the port that Flask will run on
EXPOSE 8080

# The GOOGLE_CLOUD_PROJECT_ID environment variable will be set by Terraform
# in the deployment environment (e.g., Kubernetes, Cloud Run, GCE).
# Ensure your Terraform configuration sets this environment variable for the container.

# Run frontend_service.py when the container launches
# Using Gunicorn or a similar WSGI server is recommended for production
# For development/testing, Flask's built-in server is fine.
# We'll use a simple command that sets FLASK_APP and runs it.
CMD ["python", "frontend_service.py"]