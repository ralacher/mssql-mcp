import os
import json
import pymssql
import logging
import socket
import decimal
import datetime
import uuid
from contextlib import closing
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
from typing import Any
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.instrumentation.pymssql import PyMSSQLInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer(__name__)

AsyncioInstrumentor().instrument()
PyMSSQLInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)

logging.basicConfig(
    level=logging.INFO
)
logger = logging.getLogger("mcp_mssql_server")

configure_azure_monitor(
    logger_name="mcp_mssql_server"
)

connection_string = {
    "server": os.getenv("MSSQL_SERVER"),
    "user": os.getenv("MSSQL_USER"),
    "password": os.getenv("MSSQL_PASSWORD"),
    "database": os.getenv("MSSQL_DATABASE")
}

logger.info("Starting MCP MSSQL Server")

class Database:
    def __init__(self):
        self._init_database()

    def _init_database(self):
        """Initialize the database connection and test it"""
        logger.debug("Connecting to the database to test connection")
        try:
            conn = pymssql.connect(**connection_string)
            conn.close()
            logger.debug("Connection to the database established successfully")
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            raise

    def _execute_query(self, query: str, params: dict[str, Any] | tuple | list | None = None) -> list[dict[str, Any]]:
        """Execute a SQL query and return the results"""
        logger.info(f"Query: {query}")
        try:
            with closing(pymssql.connect(**connection_string)) as conn:
                with closing(conn.cursor()) as cursor:
                    if params:

                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)

                    if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
                        conn.commit()
                        affected = cursor.rowcount
                        logger.info(f"Rows affected: {affected}")
                        return [{"affected_rows": affected}]

                    columns = [column[0] for column in cursor.description] if cursor.description else []
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    logger.info(f"Number results: {len(results)}")
                    return results
        except Exception as e:
            logger.error(f"Exception: {e}")
            raise

    def make_json_safe(self, obj):
        if isinstance(obj, list):
            return [self.make_json_safe(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self.make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        else:
            return obj

async def main():
    logger.info("Starting MSSQL Server")
    db = Database()
    server = Server(
        os.getenv("MCP_SERVER_NAME", "mcp_mssql_server"),
        os.getenv("MCP_SERVER_VERSION", "1.0.0")
    )
    logger.debug("Loaded configuration and initialized database connection")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools for the MCP server"""
        return [
            types.Tool(
                name="read_query",
                description="Execute SELECT queries on the MSSQL database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL query to execute"},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="list_tables",
                description="List database tables",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """MCP server tool execution handler"""
        with tracer.start_as_current_span("handle_call_tool", kind=SpanKind.SERVER) as span:
            try:
                if name == "list_tables":
                    span.set_attribute("http.request.method", "POST")
                    span.set_attribute("url.path", "/list_tables")
                    span.set_attribute("server.address", socket.gethostname())
                    span.set_attribute("server.port", 8080)
                    span.set_attribute("url.scheme", "https")
                    # Get all table names
                    tables = db._execute_query(
                        """
                        SELECT TABLE_NAME as name 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE'
                        """
                    )
                    table_info = {}
                    for table in tables:
                        table_name = table["name"]
                        columns = db._execute_query(
                            """
                            SELECT COLUMN_NAME as name, DATA_TYPE as type
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME = %s
                            """,
                            (table_name,)
                        )
                        table_info[table_name] = columns
                    span.set_attribute("http.response.status_code", 200)
                    return [
                        types.TextContent(
                            type="text", text=json.dumps(table_info, ensure_ascii=False, indent=2)
                        )
                    ]

                if not arguments:
                    raise ValueError("No arguments provided for tool execution")

                if name == "read_query":
                    span.set_attribute("http.request.method", "POST")
                    span.set_attribute("url.path", "/read_query")
                    span.set_attribute("server.address", socket.gethostname())
                    span.set_attribute("server.port", 8080)
                    span.set_attribute("url.scheme", "https")
                    query_upper = arguments["query"].strip().upper()
                    if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
                        raise ValueError("Invalid query type for read_query, must be a SELECT or WITH statement")
                    results = db._execute_query(arguments["query"])
                    span.set_attribute("http.response.status_code", 200)

                    response = {"results": []}
                    for result in results:
                        response["results"].append(result)
                    # Before json.dumps:
                    safe_response = db.make_json_safe(response)
                    return [
                        types.TextContent(
                            type="text", text=json.dumps(safe_response, ensure_ascii=False, indent=2)
                        )
                    ]

                raise ValueError(f"Error: {name}")
            except pymssql.Error as e:
                span.record_exception(e)
                span.set_attribute("http.response.status_code", 400)
                raise ValueError(f"PYMSSQL Error: {str(e)}")
                return [types.TextContent(type="text", text=f"PYMSSQL Error: {str(e)}")]
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("http.response.status_code", 400)
                raise ValueError(f"Exception: {str(e)}")
                return [types.TextContent(type="text", text=f"Exception: {str(e)}")]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Starting MCP server with stdio")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=os.getenv("MCP_SERVER_NAME", "mcp_mssql_server"),
                server_version=os.getenv("MCP_SERVER_VERSION", "1.0.0"),
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
