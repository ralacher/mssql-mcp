FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Copy all files to the container
COPY . /app

# Install system dependencies for pyodbc and SQL Server ODBC driver
RUN apt-get update && \
    apt-get install -y curl gnupg2 && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y gcc g++ msodbcsql17 unixodbc-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install mcpo if not in requirements.txt
RUN pip install mcpo

# Set the default command
CMD ["mcpo", "--config", "config.json"]