FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt 

COPY . .

EXPOSE 8420

CMD ["python", "-m", "localstripe"]
