#!/usr/bin/env python3
"""
Runtime Readiness Analyzer MCP Server
Analyzes if a project can run on the local machine
"""

import asyncio
import json
import os
import platform
import psutil
from typing import Any, List
from mcp.server import Server
from mcp.types import Tool, TextContent

# ================== MCP Server Initialization ==================
server = Server("runtime-readiness-analyzer")

# ================== Tool Definitions ==================
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="check_system_resources",
            description="Check CPU, RAM, disk space and GPU availability on local machine",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="analyze_project_dependencies",
            description="Analyze project dependencies from requirements.txt or package.json",
            inputSchema={
                "type": "object",
                "properties": {"project_path": {"type": "string", "description": "Path to project directory"}},
                "required": ["project_path"]
            }
        ),
        Tool(
            name="detect_heavy_requirements",
            description="Detect ML/AI frameworks and estimate resource requirements",
            inputSchema={
                "type": "object",
                "properties": {"project_path": {"type": "string", "description": "Path to project directory"}},
                "required": ["project_path"]
            }
        ),
        Tool(
            name="generate_readiness_report",
            description="Generate comprehensive readiness assessment report",
            inputSchema={
                "type": "object",
                "properties": {"project_path": {"type": "string", "description": "Path to project directory"}},
                "required": ["project_path"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool execution"""
    if name == "check_system_resources":
        return await check_system_resources()
    elif name == "analyze_project_dependencies":
        return await analyze_project_dependencies(arguments["project_path"])
    elif name == "detect_heavy_requirements":
        return await detect_heavy_requirements(arguments["project_path"])
    elif name == "generate_readiness_report":
        return await generate_readiness_report(arguments["project_path"])
    else:
        raise ValueError(f"Unknown tool: {name}")

# ================== Implementation Functions ==================
async def check_system_resources() -> List[TextContent]:
    """Check local system resources"""
    try:
        cpu_count = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        memory_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        disk_free_gb = disk.free / (1024**3)

        # GPU detection
        gpu_available = False
        gpu_info = "No GPU detected"
        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_info = f"CUDA available: {torch.cuda.get_device_name(0)}"
        except ImportError:
            pass

        result = {
            "cpu": {
                "physical_cores": cpu_count,
                "logical_cores": cpu_count_logical,
                "max_frequency_mhz": cpu_freq.max if cpu_freq else "unknown"
            },
            "memory": {
                "total_gb": round(memory_gb, 2),
                "available_gb": round(memory_available_gb, 2),
                "percent_used": memory.percent
            },
            "disk": {
                "total_gb": round(disk_total_gb, 2),
                "free_gb": round(disk_free_gb, 2),
                "percent_used": disk.percent
            },
            "gpu": {
                "available": gpu_available,
                "info": gpu_info
            },
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python_version": platform.python_version()
            }
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error checking system resources: {str(e)}")]

async def analyze_project_dependencies(project_path: str) -> List[TextContent]:
    """Analyze Python dependencies from requirements.txt"""
    try:
        python_packages = []
        req_file = os.path.join(project_path, "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                python_packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return [TextContent(type="text", text=json.dumps({"python_packages": python_packages}, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error analyzing dependencies: {str(e)}")]

async def detect_heavy_requirements(project_path: str) -> List[TextContent]:
    """Detect heavy computational requirements (GPU, large ML models)"""
    heavy_indicators = []
    req_file = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_file):
        with open(req_file, "r") as f:
            reqs = f.read().lower()
            if any(lib in reqs for lib in ["tensorflow", "torch", "keras"]):
                heavy_indicators.append(TextContent(type="text", text="ML framework detected - may require GPU/RAM"))
            if any(lib in reqs for lib in ["transformers", "diffusers"]):
                heavy_indicators.append(TextContent(type="text", text="Large ML models detected - high GPU/VRAM recommended"))

    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read().lower()
                    if "torch.cuda" in code or "tensorflow.device" in code:
                        heavy_indicators.append(TextContent(type="text", text=f"GPU usage detected in {file}"))
                    if any(model in code for model in ["bert", "gpt", "resnet"]):
                        heavy_indicators.append(TextContent(type="text", text=f"Large ML model reference detected in {file}"))

    if not heavy_indicators:
        heavy_indicators.append(TextContent(type="text", text="No heavy computational requirements detected"))

    return heavy_indicators

async def generate_readiness_report(project_path: str) -> List[TextContent]:
    """Generate readiness report combining all checks"""
    report: List[TextContent] = []

    resources_check = await check_system_resources()
    dependencies_check = await analyze_project_dependencies(project_path)
    heavy_check = await detect_heavy_requirements(project_path)

    report.append(TextContent(type="text", text="=== System Resources Check ==="))
    report.extend(resources_check)

    report.append(TextContent(type="text", text="=== Project Dependencies Check ==="))
    report.extend(dependencies_check)

    report.append(TextContent(type="text", text="=== Heavy Requirements Check ==="))
    report.extend(heavy_check)

    # ================== Readiness Logic ==================
    ready = True
    issues = []

    # GPU check
    resources_json = json.loads(resources_check[0].text)
    gpu_available = resources_json.get("gpu", {}).get("available", False)
    for item in heavy_check:
        if "GPU usage detected" in item.text and not gpu_available:
            ready = False
            issues.append("GPU is required but not available")

    # RAM check
    available_memory = resources_json.get("memory", {}).get("available_gb", 0)
    if available_memory < 4:
        ready = False
        issues.append(f"Not enough RAM: {available_memory} GB available")

    verdict_text = "✅ Project is ready to run!" if ready else f"⚠️ Project may not run properly: {', '.join(issues)}"
    report.append(TextContent(type="text", text="=== Verdict ==="))
    report.append(TextContent(type="text", text=verdict_text))

    return report

# ================== Main Entry Point ==================
async def main():
    """Main entry point for MCP server"""
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
