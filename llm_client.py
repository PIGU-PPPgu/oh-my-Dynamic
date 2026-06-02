"""
GLM-5.1 API 客户端 —— 统一的模型调用层。

支持：
  - zhipuai SDK（推荐）
  - OpenAI 兼容接口（备选）

GLM-5.1 的坑：
  - tool_call 不稳定 → 这里只做纯文本调用
  - 偶尔超时 → 内置重试
  - 偶尔不听 system prompt → 在 user prompt 里重复关键指令
"""

from __future__ import annotations
import os
import json
import time
from typing import Optional


# 默认配置（可被环境变量覆盖）
DEFAULT_API_KEY = "f92944362576476ab66c424899617160.bUm4pMI38ZwPCDjW"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"


def _get_api_key() -> str:
    """从环境变量或默认配置获取 API Key"""
    key = os.environ.get("ZHIPUAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or DEFAULT_API_KEY
    if not key:
        raise ValueError(
            "请设置环境变量 ZHIPUAI_API_KEY 或 OPENAI_API_KEY\n"
            "export ZHIPUAI_API_KEY=your_key_here"
        )
    return key


def call_glm(
    system_prompt: str,
    user_prompt: str,
    model: str = "glm-5.1",
    temperature: float = 0.3,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> str:
    """
    调用 GLM-5.1，返回纯文本响应。
    
    不依赖 tool_call，纯 prompt → response。
    """
    # 尝试 zhipuai SDK
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=_get_api_key())
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.choices[0].message.content
                if content and content.strip():
                    return content.strip()
                raise ValueError("模型返回空响应")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  [retry {attempt+1}/{max_retries}] {e}")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise
    except ImportError:
        pass
    
    # 备选：OpenAI 兼容接口
    try:
        from openai import OpenAI
        base_url = os.environ.get("GLM_BASE_URL", DEFAULT_BASE_URL)
        client = OpenAI(api_key=_get_api_key(), base_url=base_url)
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.choices[0].message.content
                if content and content.strip():
                    return content.strip()
                raise ValueError("模型返回空响应")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  [retry {attempt+1}/{max_retries}] {e}")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise
    except ImportError:
        pass
    
    raise RuntimeError(
        "无法调用 GLM-5.1。请安装 zhipuai 或 openai SDK：\n"
        "  pip install zhipuai\n"
        "  或 pip install openai"
    )
