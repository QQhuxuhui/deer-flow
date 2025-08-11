"""
Python Execution and Visualization Tools for DeerFlow Data Analysis

Provides advanced Python code execution and data visualization capabilities.
Adapted from external data analysis module with DeerFlow integration.
"""

import os
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.config.configuration import Configuration


class PythonCodeSchema(BaseModel):
    """Schema for Python code execution tool."""
    py_code: str = Field(
        description="Valid Python code string to execute (non-plotting code only)"
    )


class VisualizationSchema(BaseModel):
    """Schema for visualization tool."""
    py_code: str = Field(
        description="Python visualization code using matplotlib/seaborn"
    )
    figure_name: str = Field(
        description="Variable name for the matplotlib figure object (e.g., 'fig')",
        default="fig"
    )


def _get_chart_output_path(config: Configuration = None) -> str:
    """
    Get chart output directory from configuration.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        Path to chart output directory
    """
    if config and hasattr(config, 'chart_output_path'):
        return config.chart_output_path
    
    # Default path relative to project root
    return os.path.join(os.getcwd(), "static", "images")


@tool(args_schema=PythonCodeSchema)
def python_execution_tool(py_code: str) -> str:
    """
    Execute Python code for data processing and analysis.
    
    This tool executes non-plotting Python code and returns the results.
    Use this for data manipulation, statistical calculations, and general 
    Python operations. For visualization tasks, use visualization_tool instead.
    
    Args:
        py_code: Python code string to execute
        
    Returns:
        Execution results or error message
    """
    try:
        # Get global namespace for variable persistence
        global_vars = globals()
        
        try:
            # Try to evaluate as expression first
            result = eval(py_code, global_vars)
            return str(result)
        except:
            # If not an expression, execute as statements
            global_vars_before = set(global_vars.keys())
            exec(py_code, global_vars)
            global_vars_after = set(global_vars.keys())
            
            # Check for new variables created
            new_vars = global_vars_after - global_vars_before
            if new_vars:
                result = {var: global_vars[var] for var in new_vars}
                return f"✅ Code executed successfully. New variables: {str(result)}"
            else:
                return "✅ Code executed successfully"
                
    except Exception as e:
        return f"❌ Python code execution failed: {str(e)}"


@tool(args_schema=VisualizationSchema)
def visualization_tool(py_code: str, figure_name: str = "fig") -> str:
    """
    Execute Python visualization code and save charts.
    
    This tool executes matplotlib/seaborn plotting code and saves the resulting
    charts to the configured output directory. The code must create a figure
    object and assign it to the specified variable name.
    
    Requirements:
    - Code must create figure using plt.figure() or plt.subplots()
    - Assign figure to specified variable name (default: 'fig')
    - Do not use plt.show() 
    - Include fig.tight_layout() for better formatting
    - Use English text for labels, titles, legends
    
    Args:
        py_code: Python visualization code
        figure_name: Variable name for the figure object
        
    Returns:
        Success message with image path or error details
    """
    try:
        # Get configuration for output path
        from src.config.configuration import Configuration
        config = Configuration()  # This will be passed properly in actual implementation
        
        # Setup matplotlib backend
        current_backend = matplotlib.get_backend()
        matplotlib.use('Agg')  # Use non-interactive backend
        
        # Prepare execution environment
        local_vars = {
            "plt": plt,
            "pd": pd, 
            "sns": sns
        }
        
        # Get output directory and ensure it exists
        output_dir = _get_chart_output_path(config)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Execute visualization code
            global_vars = globals()
            exec(py_code, global_vars, local_vars)
            global_vars.update(local_vars)
            
            # Retrieve the figure object
            fig = local_vars.get(figure_name)
            if not fig:
                return f"⚠️ Figure object '{figure_name}' not found. Ensure code creates figure and assigns to '{figure_name}'"
            
            # Save figure
            image_filename = f"{figure_name}.png"
            image_path = os.path.join(output_dir, image_filename)
            fig.savefig(image_path, bbox_inches='tight', dpi=300)
            
            # Return relative path for web access
            relative_path = os.path.join("static", "images", image_filename)
            return f"✅ Visualization saved successfully at: {relative_path}"
            
        finally:
            # Cleanup
            plt.close('all')
            matplotlib.use(current_backend)
            
    except Exception as e:
        return f"❌ Visualization generation failed: {str(e)}"


# Tool list for easy import
python_tools = [python_execution_tool, visualization_tool]