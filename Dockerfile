# Basis: Microsofts offizielles Playwright-Image
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere alle Dateien aus dem Ordner in den Container (Script, .env, requirements.txt ...)
COPY . .

ENV TZ=Europe/Berlin

# Starte den Bot
CMD ["python3", "bot.py"]
