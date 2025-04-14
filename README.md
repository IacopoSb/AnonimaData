# Indicazioni per deploy con Docker

## Backend

`docker build -t gcr.io/<PROJECT_ID>/backend:latest .`

`docker push gcr.io/<PROJECT_ID>/backend:latest`

## Frontend

`docker build -t gcr.io/<PROJECT_ID>/frontend:latest .`

`docker push gcr.io/<PROJECT_ID>/frontend:latest`
