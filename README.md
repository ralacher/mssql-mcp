# MSSQL MCP Server

This project is an MCP (Model Context Protocol) server for connecting to Microsoft SQL Server databases. It uses MCPO to introduce an OpenAPI proxy in front of the MCP server, enabling OpenAPI-compatible clients to interact with the MCP server via a standardized HTTP interface. The server provides tools for schema inspection and querying, all accessible via the MCP protocol or through the OpenAPI proxy.

## Diagram
```mermaid
flowchart LR
    User --> |Prompt| Agent
    Agent --> |OpenAPI| Container
    Container --> |T-SQL| Database
```

## Features
- Connects to Microsoft SQL Server using MCP
- Provides tools for querying and schema inspection
- Designed for integration with MCP-compatible clients
- Container-ready (Docker)

## Available Tools
- **read_query**: Execute SELECT queries on the MSSQL database
- **list_tables**: List all existing tables and their columns

## Required Environment Variables

Set the following environment variables to configure the database connection:

- `MSSQL_CONNECTION_STRING` (Server=tcp:{server}.database.windows.net,1433;Database={database};UID={user};PWD={password};Driver=ODBC Driver 17 for SQL Server) 
- `MCP_SERVER_NAME` (mcp-database-assistant)
- `MCP_SERVER_VERSION` (1.0.0)

These can be set in your environment or injected at container runtime. If not set, the server will use values from `src/config.json`.

## Building and Running with Docker

1. **Build the Docker image:**
   ```sh
   docker build -t mssql-mcp .
   ```

2. **Run the container:**
   ```sh
   docker run --rm -it mssql-mcp
   ```

3. **Default command:**
   The container runs:
   ```sh
   mcpo --config config.json
   ```

## Requirements
- Python 3.11+
- Microsoft ODBC Driver 17 for SQL Server (installed in the Docker image)
- MCP-compatible client (for example, VS Code with MCP extension)

## License
See [LICENSE](LICENSE).
