# Use a lightweight official Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python script, templates, teams.json, and CSVs into the container
COPY . .

# Expose the port Flask is running on
EXPOSE 5003

# Run the script when the container launchez
CMD ["python", "app.py"]