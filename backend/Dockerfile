FROM python:3.11-slim

# Installing system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Setting working directory
WORKDIR /app

# Copying requirements
COPY requirements.txt .

# Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copying application code
COPY . .

# Creating uploads directory
RUN mkdir -p /app/uploads

# Exposeing port
EXPOSE 8000

# Running the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]