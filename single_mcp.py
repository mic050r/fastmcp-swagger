# 단일 FastMCP 서버 지원
import asyncio
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from fastmcp import Client
import inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP 서버 설정
MCP_URL = "http://127.0.0.1:8002/mcp2"
client: Optional[Client] = None
tools_cache: Dict[str, Any] = {}

# FastAPI 앱 생성
app = FastAPI(
    title="FastMCP Tools API",
    description="FastMCP 도구들을 동적으로 가져와 테스트할 수 있는 API",
    version="1.0.0"
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_python_type(json_type: str) -> type:
    """JSON Schema 타입을 Python 타입으로 변환"""
    mapping = {"string": str, "integer": int, "number": float, "boolean": bool}
    return mapping.get(json_type, str)

async def call_tool(tool_name: str, params: Dict[str, Any]):
    """MCP 도구 호출"""
    params = {k: v for k, v in params.items() if v is not None}
    try:
        result = await client.call_tool(tool_name, params)
        
        if hasattr(result, 'structured_content') and result.structured_content:
            return result.structured_content
        elif hasattr(result, 'data') and result.data is not None:
            return {"result": result.data}
        elif hasattr(result, 'content') and result.content:
            content = result.content[0] if isinstance(result.content, list) else result.content
            try:
                import json
                return json.loads(content.text)
            except:
                return {"result": getattr(content, 'text', str(content))}
        else:
            return {"result": "Success"}
    except Exception as e:
        logger.error(f"도구 '{tool_name}' 실행 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"도구 실행 중 오류: {str(e)}")

def create_dynamic_endpoint(tool_name: str, tool_data: Dict[str, Any]):
    """도구별 GET 엔드포인트 동적 생성"""
    input_schema = tool_data.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))

    param_info = {}
    for name, schema in properties.items():
        param_info[name] = {
            "type": get_python_type(schema.get("type", "string")),
            "description": schema.get("description", name),
            "title": schema.get("title", name),
            "required": name in required_fields
        }

    async def tool_endpoint(**kwargs):
        return await call_tool(tool_name, kwargs)

    # 시그니처 생성
    sig_params = []
    for name, info in param_info.items():
        default = Query(... if info["required"] else None, description=info["description"], title=info["title"])
        annotation = info["type"] if info["required"] else Optional[info["type"]]
        sig_params.append(inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation, default=default))

    tool_endpoint.__signature__ = inspect.Signature(sig_params)

    app.get(f"/{tool_name}", summary=tool_data.get("title") or tool_name,
            description=tool_data.get("description", f"{tool_name} 도구를 실행합니다."),
            tags=["FastMCP Tools"],
            responses={200: {"description": "성공"}, 500: {"description": "서버 오류"}, 503: {"description": "MCP 서버 연결 불가"}})(tool_endpoint)

    logger.info(f"GET API 생성됨: /{tool_name}")

# Startup / Shutdown 이벤트
@app.on_event("startup")
async def startup_event():
    global client, tools_cache
    try:
        client = Client(MCP_URL)
        await client.__aenter__()
        tools_response = await client.list_tools_mcp()
        logger.info(f"MCP 서버에서 {len(tools_response.tools)} 개 도구 발견")

        for tool in tools_response.tools:
            tool_data = {
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "outputSchema": tool.outputSchema
            }
            tools_cache[tool.name] = tool_data
            create_dynamic_endpoint(tool.name, tool_data)
            logger.info(f"도구 로드: {tool.name} - {tool.description}")

        logger.info(f"{len(tools_response.tools)}개 도구 API 생성 완료")
    except Exception as e:
        logger.error(f"MCP 서버 연결 실패: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global client
    if client:
        try:
            await client.__aexit__(None, None, None)
            logger.info("MCP 클라이언트 종료 완료")
        except:
            pass

# 기본 라우트
@app.get("/", tags=["시스템"])
async def root():
    """사용 가능한 도구 목록"""
    tool_list = []
    for name, data in tools_cache.items():
        tool_list.append({
            "name": name,
            "title": data.get("title"),
            "description": data.get("description"),
            "endpoint": f"GET /{name}",
            "parameters": list(data.get("inputSchema", {}).get("properties", {}).keys())
        })
    return {
        "service": "Dynamic FastMCP Tools API",
        "mcp_server": MCP_URL,
        "available_tools": tool_list,
        "total": len(tool_list),
        "swagger_ui": "/docs"
    }

@app.get("/docs", response_class=HTMLResponse)
async def swagger_ui():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="FastMCP Tools API - Swagger UI")

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    print(f"MCP Server URL: {MCP_URL}")
    print("Starting server...")
    print("Swagger UI: http://localhost:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
