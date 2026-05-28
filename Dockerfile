FROM python:3.14-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY server ./server

RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt fastapi uvicorn[standard] python-multipart pandas torch
RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
