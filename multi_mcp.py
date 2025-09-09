import io
import pandas as pd
import inspect
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastmcp import Client


# ----------------- 설정 -----------------
MCP_SERVERS = [
    {"name": "calculator tools", "url": "http://127.0.0.1:8002/mcp2"},
    {"name": "test tools", "url": "http://127.0.0.1:8001/mcp1"}
]

clients: Dict[str, Client] = {}
tools_cache: Dict[str, Dict[str, Any]] = {}

app = FastAPI(
    title="FastMCP Tools API",
    description="여러 MCP 서버의 도구를 동적으로 가져와 테스트할 수 있는 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------- 유틸리티 -----------------
def get_python_type(json_type: str) -> type:
    """JSON Schema 타입을 Python 타입으로 변환"""
    mapping = {'string': str, 'integer': int, 'number': float, 'boolean': bool}
    return mapping.get(json_type, str)


async def call_tool(tool_name: str, params: Dict[str, Any], server_name: str) -> Any:
    """
    MCP 서버의 도구 호출
    
    Args:
        tool_name: 실행할 도구 이름
        params: 도구 입력 파라미터
        server_name: MCP 서버 이름

    Returns:
        도구 실행 결과
    """
    client = clients.get(server_name)
    if not client:
        raise HTTPException(status_code=503, detail=f"{server_name} MCP 서버 연결 불가")

    params = {k: v for k, v in params.items() if v is not None}
    try:
        result = await client.call_tool(tool_name, params)
        if hasattr(result, "structured_content") and result.structured_content:
            return result.structured_content
        if hasattr(result, "data") and result.data is not None:
            return {"result": result.data}
        if hasattr(result, "content") and result.content:
            if isinstance(result.content, list) and len(result.content) > 0:
                first = result.content[0]
                if hasattr(first, "text"):
                    import json
                    try:
                        return json.loads(first.text)
                    except:
                        return {"result": first.text}
            return {"result": str(result.content)}
        return {"result": "Success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{tool_name} 실행 오류: {e}")


def create_dynamic_endpoint(tool_name: str, tool_data: Dict[str, Any], server_name: str):
    """
    MCP 도구에 대한 동적 GET 엔드포인트 생성

    Args:
        tool_name: 도구 이름
        tool_data: 도구 메타데이터
        server_name: MCP 서버 이름 (Swagger 태그용)
    """
    input_schema = tool_data.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))

    param_info = {}
    for name, schema in properties.items():
        param_info[name] = {
            "type": get_python_type(schema.get("type", "string")),
            "description": schema.get("description", f"{name} parameter"),
            "title": schema.get("title", name),
            "required": name in required_fields
        }

    async def tool_endpoint(**kwargs):
        return await call_tool(tool_name, kwargs, server_name)

    def create_signature():
        sig_params = []
        for name, info in param_info.items():
            param_type = info["type"]
            param = inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=param_type if info["required"] else Optional[param_type],
                default=Query(
                    ... if info["required"] else None,
                    description=info["description"],
                    title=info["title"]
                )
            )
            sig_params.append(param)
        return inspect.Signature(sig_params)

    tool_endpoint.__signature__ = create_signature()

    app.get(
        f"/{tool_name}",
        summary=tool_data.get("title", tool_name),
        description=tool_data.get("description", f"{tool_name} 도구 실행"),
        tags=[server_name],
        responses={200: {"description": "성공"}, 500: {"description": "도구 오류"}, 503: {"description": "서버 연결 실패"}}
    )(tool_endpoint)


# ----------------- 이벤트 -----------------
@app.on_event("startup")
async def startup_event():
    """MCP 서버 연결 및 도구 로드"""
    for server in MCP_SERVERS:
        name, url = server["name"], server["url"]
        try:
            client = Client(url)
            await client.__aenter__()
            clients[name] = client

            tools_response = await client.list_tools_mcp()
            tools_cache[name] = {}
            for tool in tools_response.tools:
                tool_data = {
                    "name": tool.name,
                    "title": tool.title,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "outputSchema": tool.outputSchema
                }
                tools_cache[name][tool.name] = tool_data
                create_dynamic_endpoint(tool.name, tool_data, name)
        except Exception:
            # 실패 시 클라이언트 추가하지 않음
            continue


@app.on_event("shutdown")
async def shutdown_event():
    """모든 MCP 클라이언트 종료"""
    for client in clients.values():
        try:
            await client.__aexit__(None, None, None)
        except:
            pass


# ----------------- 엔드포인트 -----------------
@app.get("/", tags=["시스템"])
async def root():
    """
    사용 가능한 MCP 서버와 도구 목록 반환
    """
    result = []
    for server_name, tools in tools_cache.items():
        server_tools = [
            {
                "name": t_name,
                "title": t_data.get("title"),
                "description": t_data.get("description"),
                "endpoint": f"/{t_name}",
                "parameters": list(t_data.get("inputSchema", {}).get("properties", {}).keys())
            }
            for t_name, t_data in tools.items()
        ]
        result.append({"server": server_name, "tools": server_tools, "total": len(server_tools)})
    return {"available_servers": result}


@app.get("/docs", response_class=HTMLResponse)
async def swagger_ui():
    """Swagger UI 반환"""
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="Dynamic FastMCP Tools API - Swagger UI")

@app.get("/export_tools", summary="MCP 도구 리스트를 엑셀로 내보내기")
async def export_tools(url: str = Query(..., description="MCP 서버 URL")):
    """
    MCP 서버 URL 입력 시, 도구 목록을 엑셀로 만들어 반환
    """
    client = Client(url)
    await client.__aenter__()
    try:
        tools_response = await client.list_tools_mcp()
        data = []
        for tool in tools_response.tools:
            input_params = list(tool.inputSchema.get("properties", {}).keys())
            output_keys = list(tool.outputSchema.get("properties", {}).keys()) if tool.outputSchema else []
            data.append({
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "endpoint": f"/{tool.name}",
                "parameters": ", ".join(input_params),
                "output_schema": ", ".join(output_keys)
            })
        df = pd.DataFrame(data)

        # 엑셀 버퍼 생성
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="tools")
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=tools.xlsx"}
        )
    finally:
        await client.__aexit__(None, None, None)
# ----------------- 실행 -----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)