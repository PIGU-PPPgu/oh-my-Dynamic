"""
通用 LLM 客户端 —— 统一的模型调用层。

支持多种大模型后端：
  - GLM（智谱 AI）：zhipuai SDK 或 OpenAI 兼容接口
  - OpenAI（GPT-4o 等）：openai SDK
  - Anthropic（Claude）：anthropic SDK
  - Google（Gemini）：google-genai SDK
  - 中国模型：DeepSeek、通义千问/Qwen、Moonshot/Kimi、硅基流动
  - 任意 OpenAI 兼容接口

配置方式（优先级从高到低）：
  1. 代码中传 model="provider/model-name"
  2. 环境变量 LLM_DEFAULT_MODEL
  3. 默认 glm-5.1（向后兼容）

支持的模型名格式：
  - "glm-5.1" / "glm-4-flash"           → 智谱 GLM
  - "gpt-5.2" / "gpt-5-mini"              → OpenAI
  - "claude-sonnet-4-6"                   → Anthropic Claude
  - "gemini-3.5-flash"                    → Google Gemini
  - "deepseek-chat" / "qwen-plus" 等     → 中国 OpenAI 兼容接口
  - "openrouter/xxx"                      → OpenRouter
"""

from __future__ import annotations
import os
import time
from typing import Optional


_PROVIDER_ENV = {
    "zhipu": ("ZHIPUAI_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    "moonshot": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    "siliconflow": ("SILICONFLOW_API_KEY",),
    "openai_compatible": ("OPENAI_API_KEY",),
}

_OPENAI_COMPAT_BASE_URLS = {
    "zhipu": ("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    "deepseek": ("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    "qwen": ("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "moonshot": ("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
    "siliconflow": ("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
    "openrouter": ("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
}

_EXPLICIT_PREFIXES = {
    "openrouter": "openrouter",
    "zhipu": "zhipu",
    "glm": "zhipu",
    "deepseek": "deepseek",
    "qwen": "qwen",
    "dashscope": "qwen",
    "tongyi": "qwen",
    "moonshot": "moonshot",
    "kimi": "moonshot",
    "siliconflow": "siliconflow",
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
}


# --------------------------------------------------------------------------- #
# Provider 自动检测
# --------------------------------------------------------------------------- #

def _detect_provider(model: str) -> str:
    """根据模型名自动推断 provider"""
    m = model.lower()
    if "/" in m:
        prefix = m.split("/", 1)[0]
        if prefix in _EXPLICIT_PREFIXES:
            return _EXPLICIT_PREFIXES[prefix]
    if m.startswith("openrouter/"):
        return "openrouter"
    if m.startswith("glm-") or "chatglm" in m:
        return "zhipu"
    if m.startswith("deepseek-"):
        return "deepseek"
    if m.startswith("qwen-") or m.startswith("tongyi-"):
        return "qwen"
    if m.startswith("moonshot-") or m.startswith("kimi-"):
        return "moonshot"
    if m.startswith("gpt-") or m.startswith("o1-") or m.startswith("o3-") or m.startswith("o4-"):
        return "openai"
    if "claude" in m:
        return "anthropic"
    if m.startswith("gemini-"):
        return "google"
    # 其他走 OpenAI 兼容接口
    return "openai_compatible"


def _get_env_keys(provider: str) -> tuple[str, ...]:
    """返回 provider 支持的 API Key 环境变量名。"""
    return _PROVIDER_ENV.get(provider, ("OPENAI_API_KEY",))


def _get_api_key(provider: str) -> str:
    """根据 provider 获取对应 API Key"""
    env_names = _get_env_keys(provider)
    key = next((os.environ.get(name) for name in env_names if os.environ.get(name)), None)
    if not key:
        # 回退尝试通用 key
        key = os.environ.get("LLM_API_KEY")
    if not key:
        hint = " 或 ".join(f"export {name}=your_key" for name in env_names)
        raise ValueError(
            f"模型 provider '{provider}' 需要 API Key。\n"
            f"请设置环境变量: {hint}\n"
            f"或设置通用 key: export LLM_API_KEY=your_key"
        )
    return key


def _strip_provider_prefix(provider: str, model: str) -> str:
    """允许 deepseek/deepseek-chat 这类显式 provider 前缀。"""
    if "/" not in model:
        return model
    prefix, actual = model.split("/", 1)
    if _EXPLICIT_PREFIXES.get(prefix.lower()) == provider:
        return actual
    return model


def _compatible_base_url(provider: str, env_default: str = "https://api.openai.com/v1") -> str:
    env_name, default = _OPENAI_COMPAT_BASE_URLS.get(provider, ("LLM_BASE_URL", env_default))
    return os.environ.get(env_name, default)


# --------------------------------------------------------------------------- #
# 各 Provider 调用实现
# --------------------------------------------------------------------------- #

def _call_zhipu(api_key: str, model: str, system_prompt: str, user_prompt: str,
                temperature: float, max_retries: int, retry_delay: float) -> str:
    """智谱 GLM：优先 zhipuai SDK，回退 OpenAI 兼容"""
    model = _strip_provider_prefix("zhipu", model)
    # 尝试 zhipuai SDK
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)
        return _retry_call(
            lambda: client.chat.completions.create(
                model=model, temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            ),
            max_retries=max_retries, retry_delay=retry_delay,
        )
    except ImportError:
        pass

    # 回退 OpenAI 兼容接口
    base_url = _compatible_base_url("zhipu")
    return _call_openai_compatible(api_key, base_url, model, system_prompt,
                                   user_prompt, temperature, max_retries, retry_delay)


def _call_openai(api_key: str, model: str, system_prompt: str, user_prompt: str,
                 temperature: float, max_retries: int, retry_delay: float) -> str:
    """OpenAI GPT 系列"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    return _retry_call(
        lambda: client.chat.completions.create(
            model=model, temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        ),
        max_retries=max_retries, retry_delay=retry_delay,
    )


def _call_anthropic(api_key: str, model: str, system_prompt: str, user_prompt: str,
                    temperature: float, max_retries: int, retry_delay: float) -> str:
    """Anthropic Claude 系列"""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    def _do():
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Anthropic 返回 content blocks
        text = "".join(block.text for block in resp.content if block.type == "text")
        if not text.strip():
            raise ValueError("模型返回空响应")
        return text.strip()
    return _retry_fn(_do, max_retries=max_retries, retry_delay=retry_delay)


def _call_google(api_key: str, model: str, system_prompt: str, user_prompt: str,
                 temperature: float, max_retries: int, retry_delay: float) -> str:
    """Google Gemini 系列"""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
    )
    def _do():
        resp = gemini_model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature),
        )
        text = resp.text
        if not text or not text.strip():
            raise ValueError("模型返回空响应")
        return text.strip()
    return _retry_fn(_do, max_retries=max_retries, retry_delay=retry_delay)


def _call_openrouter(api_key: str, model: str, system_prompt: str, user_prompt: str,
                     temperature: float, max_retries: int, retry_delay: float) -> str:
    """OpenRouter（去掉 openrouter/ 前缀后的模型名）"""
    actual_model = _strip_provider_prefix("openrouter", model)
    base_url = _compatible_base_url("openrouter")
    return _call_openai_compatible(api_key, base_url, actual_model, system_prompt,
                                   user_prompt, temperature, max_retries, retry_delay)


def _call_china_compatible(provider: str, api_key: str, model: str,
                           system_prompt: str, user_prompt: str,
                           temperature: float, max_retries: int,
                           retry_delay: float) -> str:
    """中国厂商的 OpenAI 兼容接口。"""
    actual_model = _strip_provider_prefix(provider, model)
    base_url = _compatible_base_url(provider)
    return _call_openai_compatible(api_key, base_url, actual_model, system_prompt,
                                   user_prompt, temperature, max_retries, retry_delay)


def _call_openai_compatible(api_key: str, base_url: str, model: str,
                            system_prompt: str, user_prompt: str,
                            temperature: float, max_retries: int, retry_delay: float) -> str:
    """OpenAI 兼容接口（DeepSeek、通义千问、Moonshot 等）"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    return _retry_call(
        lambda: client.chat.completions.create(
            model=model, temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        ),
        max_retries=max_retries, retry_delay=retry_delay,
    )


# --------------------------------------------------------------------------- #
# 重试逻辑
# --------------------------------------------------------------------------- #

def _extract_content(response) -> str:
    """从 OpenAI 格式 response 提取文本"""
    content = response.choices[0].message.content
    if content and content.strip():
        return content.strip()
    raise ValueError("模型返回空响应")


def _retry_call(fn, max_retries: int = 3, retry_delay: float = 5.0) -> str:
    """重试 OpenAI 格式的 chat.completions.create 调用"""
    last_exc: Exception = RuntimeError("所有重试失败")
    for attempt in range(max_retries):
        try:
            return _extract_content(fn())
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                print(f"  [retry {attempt+1}/{max_retries}] {e}")
                time.sleep(retry_delay * (attempt + 1))
    raise last_exc


def _retry_fn(fn, max_retries: int = 3, retry_delay: float = 5.0) -> str:
    """重试任意函数调用"""
    last_exc: Exception = RuntimeError("所有重试失败")
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                print(f"  [retry {attempt+1}/{max_retries}] {e}")
                time.sleep(retry_delay * (attempt + 1))
    raise last_exc


# --------------------------------------------------------------------------- #
# 主入口（向后兼容 call_glm）
# --------------------------------------------------------------------------- #

# Provider 调用分发在 call_glm() 中通过 if/elif 实现
# （因为 _call_openai_compatible 需要 base_url 参数，不适合 dict dispatch）


def call_glm(
    system_prompt: str,
    user_prompt: str,
    model: str = "",
    temperature: float = 0.3,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> str:
    """
    统一的 LLM 调用入口（向后兼容 call_glm）。

    根据 model 名称自动选择 provider 和 API Key。

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户消息
        model: 模型名称（默认从 LLM_DEFAULT_MODEL 或 glm-5.1）
        temperature: 温度
        max_retries: 最大重试次数
        retry_delay: 重试间隔基数（实际为 delay * attempt）

    Returns:
        模型返回的文本
    """
    # 解析实际 model
    if not model:
        model = os.environ.get("LLM_DEFAULT_MODEL", "glm-5.1")

    provider = _detect_provider(model)
    api_key = _get_api_key(provider)

    # 分发到对应 provider
    if provider == "zhipu":
        return _call_zhipu(api_key, model, system_prompt, user_prompt,
                           temperature, max_retries, retry_delay)
    elif provider == "openai":
        return _call_openai(api_key, model, system_prompt, user_prompt,
                            temperature, max_retries, retry_delay)
    elif provider == "anthropic":
        return _call_anthropic(api_key, model, system_prompt, user_prompt,
                               temperature, max_retries, retry_delay)
    elif provider == "google":
        return _call_google(api_key, model, system_prompt, user_prompt,
                            temperature, max_retries, retry_delay)
    elif provider == "openrouter":
        return _call_openrouter(api_key, model, system_prompt, user_prompt,
                                temperature, max_retries, retry_delay)
    elif provider in {"deepseek", "qwen", "moonshot", "siliconflow"}:
        return _call_china_compatible(provider, api_key, model, system_prompt,
                                      user_prompt, temperature, max_retries,
                                      retry_delay)
    else:
        # openai_compatible：需要额外的 base_url
        base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        return _call_openai_compatible(api_key, base_url, model, system_prompt,
                                       user_prompt, temperature, max_retries, retry_delay)


# --------------------------------------------------------------------------- #
# 便捷：列出可用 provider
# --------------------------------------------------------------------------- #

def list_providers() -> dict:
    """返回所有支持的 provider 及其环境变量"""
    return {
        "zhipu":     {"sdk": "zhipuai",     "env": "ZHIPUAI_API_KEY",    "models": ["glm-5.1", "glm-4-flash", "glm-4-plus"]},
        "openai":    {"sdk": "openai",       "env": "OPENAI_API_KEY",     "models": ["gpt-5.2", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano"]},
        "anthropic": {"sdk": "anthropic",    "env": "ANTHROPIC_API_KEY",  "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"]},
        "google":    {"sdk": "google-generativeai", "env": "GOOGLE_API_KEY", "models": ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-flash-latest"]},
        "openrouter":{"sdk": "openai",       "env": "OPENROUTER_API_KEY", "models": ["openrouter/openai/gpt-5.2", "openrouter/anthropic/claude-sonnet-4.6", "openrouter/google/gemini-3.5-flash"]},
        "deepseek":  {"sdk": "openai",       "env": "DEEPSEEK_API_KEY",   "models": ["deepseek-chat", "deepseek-reasoner"]},
        "qwen":      {"sdk": "openai",       "env": "DASHSCOPE_API_KEY",  "models": ["qwen-plus", "qwen-max", "qwen-turbo"]},
        "moonshot":  {"sdk": "openai",       "env": "MOONSHOT_API_KEY",   "models": ["moonshot-v1-8k", "moonshot-v1-32k", "kimi-k2"]},
        "siliconflow":{"sdk": "openai",      "env": "SILICONFLOW_API_KEY","models": ["siliconflow/deepseek-ai/DeepSeek-V3"]},
        "compatible":{"sdk": "openai",       "env": "OPENAI_API_KEY",     "models": ["custom-model-with-LLM_BASE_URL"]},
    }
