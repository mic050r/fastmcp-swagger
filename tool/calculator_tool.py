from fastmcp import FastMCP

mcp = FastMCP("calculator tools")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@mcp.tool
def subtract(a: int, b: int) -> int:
    """Subtract b from a"""
    return a - b

@mcp.tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b

@mcp.tool
def divide(a: int, b: int) -> float:
    """Divide a by b"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

@mcp.tool
def greet(name: str) -> str:
    """Return a greeting message"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    # 로컬 127.0.0.1, 포트 8000, path="/mcp"로 실행
    mcp.run(transport="http", host="127.0.0.1", port=8002, path="/mcp2")
