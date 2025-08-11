"""
SQL Database Tools for DeerFlow Data Analysis

Provides database query and data extraction capabilities.
Adapted from external data analysis module with DeerFlow configuration integration.
"""

import json
import os
from typing import Any
import pandas as pd
import pymysql
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.config.configuration import Configuration


class SQLQuerySchema(BaseModel):
    """Schema for SQL query tool parameters."""
    sql_query: str = Field(
        description="SQL query string to execute on the configured MySQL database"
    )


class ExtractDataSchema(BaseModel):
    """Schema for data extraction tool parameters."""
    sql_query: str = Field(
        description="SQL query string to extract data from MySQL database"
    )
    df_name: str = Field(
        description="Variable name for storing the extracted pandas DataFrame"
    )


def _get_database_connection(config: Configuration) -> pymysql.Connection:
    """
    Create database connection using DeerFlow configuration.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        pymysql.Connection: Database connection object
    """
    # Get database config from environment or config
    db_config = getattr(config, 'database_config', None) or {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'root'), 
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'telco_data'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'charset': 'utf8'
    }
    
    return pymysql.connect(**db_config)


@tool(args_schema=SQLQuerySchema)
def sql_query_tool(sql_query: str) -> str:
    """
    Execute SQL queries on configured MySQL database.
    
    This tool connects to the MySQL database specified in DeerFlow configuration
    and executes the provided SQL query, returning results as JSON string.
    Use this for data exploration and querying operations.
    
    Args:
        sql_query: SQL query string to execute
        
    Returns:
        JSON string containing query results
    """
    try:
        # Get configuration (in actual usage, this would come from context)
        from src.config.configuration import Configuration
        config = Configuration()  # This will be passed properly in the actual implementation
        
        connection = _get_database_connection(config)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql_query)
                results = cursor.fetchall()
                return json.dumps(results, ensure_ascii=False, default=str)
        finally:
            connection.close()
            
    except Exception as e:
        return f"❌ SQL query execution failed: {str(e)}"


@tool(args_schema=ExtractDataSchema) 
def extract_data_tool(sql_query: str, df_name: str) -> str:
    """
    Extract data from MySQL database to pandas DataFrame.
    
    This tool executes an SQL query and stores the results as a pandas DataFrame
    in the global namespace for subsequent analysis operations. Use this when
    you need to perform data analysis or visualization on database content.
    
    Args:
        sql_query: SQL query string to extract data
        df_name: Variable name for storing the DataFrame
        
    Returns:
        Success message or error details
    """
    try:
        # Get configuration (in actual usage, this would come from context)
        from src.config.configuration import Configuration
        config = Configuration()  # This will be passed properly in the actual implementation
        
        connection = _get_database_connection(config)
        
        try:
            # Execute query and create DataFrame
            df = pd.read_sql(sql_query, connection)
            
            # Store in global namespace for access by other tools
            globals()[df_name] = df
            
            return f"✅ Successfully created pandas DataFrame '{df_name}' with {len(df)} rows and {len(df.columns)} columns from MySQL database"
            
        finally:
            connection.close()
            
    except Exception as e:
        return f"❌ Data extraction failed: {str(e)}"


# Tool list for easy import
sql_tools = [sql_query_tool, extract_data_tool]