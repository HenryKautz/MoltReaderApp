FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 10000

# Run the application
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
