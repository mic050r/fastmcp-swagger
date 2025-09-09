from fastmcp import FastMCP
from typing import Dict, Any, List, Optional
from datetime import datetime
import random
import hashlib
from collections import Counter
import re

mcp = FastMCP("test tools")

# 날씨 정보 도구 (모의 데이터)
@mcp.tool
def get_weather(city: str) -> Dict[str, Any]:
    """날씨 정보 조회 도구 (모의 데이터) - 서울, 부산, 대구, 인천, 광주, 대전, 울산 지원"""
    mock_weather_data = {
        "서울": {"temperature": 15.5, "description": "맑음"},
        "부산": {"temperature": 18.2, "description": "흐림"},
        "대구": {"temperature": 16.8, "description": "비"},
        "인천": {"temperature": 14.3, "description": "맑음"},
        "광주": {"temperature": 17.1, "description": "흐림"},
        "대전": {"temperature": 15.9, "description": "맑음"},
        "울산": {"temperature": 16.5, "description": "비"},
    }
    
    city_data = mock_weather_data.get(city)
    if city_data:
        return {
            "city": city,
            "temperature": city_data["temperature"],
            "description": city_data["description"],
            "status": "success"
        }
    else:
        return {
            "city": city,
            "error": f"{city}의 날씨 정보를 찾을 수 없습니다",
            "available_cities": list(mock_weather_data.keys())
        }

# 텍스트 분석 도구
@mcp.tool
def analyze_text(text: str) -> Dict[str, Any]:
    """텍스트 분석 도구 - 단어 수, 문자 수, 문장 수, 가장 많이 사용된 단어들을 분석"""
    # 단어 수 계산
    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)
    
    # 문자 수 계산
    character_count = len(text)
    
    # 문장 수 계산
    sentences = re.split(r"[.!?]+", text)
    sentence_count = len([s for s in sentences if s.strip()])
    
    # 가장 많이 사용된 단어들
    word_freq = Counter(words)
    most_common_words = word_freq.most_common(5)
    
    return {
        "word_count": word_count,
        "character_count": character_count,
        "sentence_count": sentence_count,
        "most_common_words": most_common_words,
        "analysis_summary": f"총 {word_count}개 단어, {character_count}개 문자, {sentence_count}개 문장"
    }

# 현재 시간 도구
@mcp.tool
def get_current_time() -> Dict[str, Any]:
    """현재 시간 조회 도구"""
    now = datetime.now()
    return {
        "current_time": now.isoformat(),
        "formatted_time": now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초"),
        "timestamp": now.timestamp(),
        "day_of_week": now.strftime("%A")
    }

# 랜덤 숫자 생성 도구
@mcp.tool
def generate_random_number(min_val: int = 1, max_val: int = 100) -> Dict[str, Any]:
    """랜덤 숫자 생성 도구 - 지정된 범위에서 랜덤 숫자를 생성"""
    random_num = random.randint(min_val, max_val)
    return {
        "random_number": random_num,
        "range": f"{min_val} ~ {max_val}",
        "timestamp": datetime.now().isoformat()
    }

# URL 단축 도구 (모의)
@mcp.tool
def shorten_url(url: str) -> Dict[str, Any]:
    """URL 단축 도구 (모의) - 긴 URL을 짧은 URL로 변환"""
    short_code = hashlib.md5(url.encode()).hexdigest()[:8]
    short_url = f"https://short.ly/{short_code}"
    
    return {
        "original_url": url,
        "short_url": short_url,
        "short_code": short_code,
        "created_at": datetime.now().isoformat()
    }

# 색상 변환 도구
@mcp.tool
def convert_color(hex_color: str) -> Dict[str, Any]:
    """HEX 색상을 RGB로 변환하는 도구"""
    try:
        # # 제거
        hex_color = hex_color.lstrip("#")
        
        if len(hex_color) != 6:
            return {"error": "올바른 HEX 색상 형식이 아닙니다 (#RRGGBB)"}
        
        # RGB 값 추출
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        return {
            "hex": f"#{hex_color.upper()}",
            "rgb": {"r": r, "g": g, "b": b},
            "rgb_string": f"rgb({r}, {g}, {b})",
            "converted_at": datetime.now().isoformat()
        }
    except ValueError:
        return {"error": "올바른 HEX 색상 형식이 아닙니다"}

# 메모리 저장소 (간단한 인메모리 저장)
memory_store = {}

@mcp.tool
def save_to_memory(key: str, value: str) -> Dict[str, Any]:
    """메모리에 데이터 저장"""
    memory_store[key] = {
        "value": value,
        "saved_at": datetime.now().isoformat()
    }
    return {
        "key": key,
        "message": "데이터가 저장되었습니다",
        "saved_at": memory_store[key]["saved_at"]
    }

@mcp.tool
def retrieve_from_memory(key: str) -> Dict[str, Any]:
    """메모리에서 데이터 조회"""
    if key in memory_store:
        return memory_store[key]
    else:
        return {"error": "키를 찾을 수 없습니다", "available_keys": list(memory_store.keys())}

@mcp.tool
def list_memory_keys() -> Dict[str, Any]:
    """저장된 모든 키 목록 조회"""
    return {
        "keys": list(memory_store.keys()),
        "count": len(memory_store),
        "retrieved_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
   mcp.run(transport="http", host="127.0.0.1", port=8001, path="/mcp1")