FROM python:3.12-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
EXPOSE 8080
COPY . /app
WORKDIR /app
RUN pip install -r ./requirements.txt
CMD ["python", "app.py"]