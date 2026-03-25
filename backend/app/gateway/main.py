#!/usr/bin/env python3
"""
DeerFlow Gateway 启动入口
用于 PyInstaller 打包

架构说明：
==========
DeerFlowGateway 是一个单一可执行文件，集成了：

1. Gateway API (FastAPI, 端口 8001)
   - /api/models - 模型管理
   - /api/mcp - MCP 配置
   - /api/memory - 记忆管理
   - /api/skills - 技能管理
   - /api/threads - 线程管理
   - /api/artifacts - 文件管理
   - 等等...

2. 嵌入式 LangGraph 运行时 (app/gateway/routers/langgraph.py)
   - /api/langgraph/threads - 创建线程
   - /api/langgraph/threads/{id}/runs/stream - 流式对话
   - /api/langgraph/assistants - 助手列表
   - 使用 DeerFlowClient 在进程内运行 Agent，无需独立 LangGraph Server

3. 前端静态文件服务（可选）
   - 设置 DEERFLOW_STATIC_DIR 环境变量启用
   - SPA 模式：非 API 路由返回 index.html

关键特性：
- 单进程部署：无需独立的 LangGraph Server (port 2024)
- 零网络开销：Agent 运行时在进程内调用
- 简化打包：只需一个可执行文件

使用方法：
---------
# 基本启动（默认端口 8001）
./DeerFlowGateway

# 指定端口
./DeerFlowGateway --port 9000

# 跳过 API 密钥检查（用于测试）
./DeerFlowGateway --skip-key-check

# 启用前端静态文件服务
DEERFLOW_STATIC_DIR=/path/to/frontend/_next ./DeerFlowGateway

环境变量：
- DEER_FLOW_CONFIG_PATH: 配置文件路径 (默认: 同目录 config.yaml)
- DEER_FLOW_EXTENSIONS_CONFIG_PATH: 扩展配置路径 (默认: 同目录 extensions_config.json)
- DEERFLOW_STATIC_DIR: 前端静态文件目录（可选）
- ZHIPU_API_KEY: 智谱 API 密钥（或其他 LLM 提供商密钥）
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
import uvicorn

logger = logging.getLogger(__name__)

# 默认配置（智谱 AI）
DEFAULT_CONFIG = {
    "config_version": 3,
    "models": [
        {
            "name": "glm-5-turbo",
            "display_name": "GLM-5-Turbo",
            "use": "deerflow.models.zhipu_thinking:ZhipuChatModel",
            "model": "glm-5-turbo",
            "api_key": "$ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "max_tokens": 8192,
            "temperature": 0.7,
            "thinking_enabled": True,
            "supports_thinking": True,
            "supports_vision": False,
        },
        {
            "name": "glm-5",
            "display_name": "GLM-5",
            "use": "deerflow.models.zhipu_thinking:ZhipuChatModel",
            "model": "glm-5",
            "api_key": "$ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "max_tokens": 8192,
            "temperature": 0.7,
            "thinking_enabled": True,
            "supports_thinking": True,
            "supports_vision": False,
        },
        {
            "name": "glm-4.7",
            "display_name": "GLM-4.7",
            "use": "deerflow.models.zhipu_thinking:ZhipuChatModel",
            "model": "glm-4.7",
            "api_key": "$ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "max_tokens": 8192,
            "temperature": 0.7,
            "thinking_enabled": True,
            "supports_thinking": True,
            "supports_vision": False,
        },
        {
            "name": "glm-4.6V",
            "display_name": "GLM-4.6V",
            "use": "langchain_openai:ChatOpenAI",
            "model": "glm-4.6V",
            "api_key": "$ZHIPU_API_KEY",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "max_tokens": 8192,
            "temperature": 0.7,
            "supports_thinking": False,
            "supports_vision": True,
        },
    ],
    "default_model": "glm-5-turbo",
    "sandbox": {
        "use": "deerflow.sandbox.local:LocalSandboxProvider",
    },
    "skills": {
        "path": "skills",
        "container_path": "/mnt/skills",
    },
    "title": {
        "enabled": True,
        "max_words": 6,
        "max_chars": 24,
    },
    "memory": {
        "enabled": True,
        "storage_path": ".deer-flow/memory.json",
        "debounce_seconds": 30,
        "model_name": None,
        "max_facts": 100,
        "fact_confidence_threshold": 0.7,
        "injection_enabled": True,
        "max_injection_tokens": 2000,
    },
}


def get_base_path() -> Path:
    """获取基础路径（支持 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式
        return Path(sys._MEIPASS).parent
    else:
        # 开发模式
        return Path(__file__).parent.parent.parent.parent


def ensure_config():
    """确保配置文件存在，如果不存在则创建默认配置"""
    base_path = get_base_path()
    config_path = os.environ.get("DEER_FLOW_CONFIG_PATH")

    if config_path:
        config_file = Path(config_path)
    else:
        config_file = base_path / "config.yaml"

    if not config_file.exists():
        logger.info(f"配置文件不存在，创建默认配置: {config_file}")
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(DEFAULT_CONFIG, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"已创建默认配置文件: {config_file}")
        except Exception as e:
            logger.warning(f"无法创建配置文件: {e}，使用内存中的默认配置")
            # 设置环境变量指向一个临时配置
            os.environ["DEER_FLOW_CONFIG_PATH"] = "memory://default"

    # 设置环境变量
    if not os.environ.get("DEER_FLOW_CONFIG_PATH"):
        os.environ["DEER_FLOW_CONFIG_PATH"] = str(config_file)

    if not os.environ.get("DEER_FLOW_EXTENSIONS_CONFIG_PATH"):
        extensions_path = base_path / "extensions_config.json"
        if extensions_path.exists():
            os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(extensions_path)


def check_api_key():
    """检查 API 密钥是否已配置"""
    # 重新加载环境变量
    api_key = os.environ.get("ZHIPU_API_KEY", "")
    if not api_key or api_key == "your-zhipu-api-key":
        logger.warning("=" * 60)
        logger.warning("ZHIPU_API_KEY 未配置！")
        logger.warning("请设置环境变量或创建 .env 文件")
        logger.warning("示例: export ZHIPU_API_KEY=your_api_key")
        logger.warning("=" * 60)
        # 返回 True 允许程序继续运行（后续可通过页面配置）
        return True
    return True


def main():
    parser = argparse.ArgumentParser(description="DeerFlow Gateway API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind (default: 8001)")
    parser.add_argument("--skip-key-check", action="store_true", help="Skip API key check")
    args = parser.parse_args()

    # 加载 .env 文件
    base_path = get_base_path()
    env_file = base_path / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"已加载环境变量: {env_file}")

    # 确保配置文件存在
    ensure_config()

    # 检查 API 密钥
    if not args.skip_key_check:
        check_api_key()

    # 导入并创建应用
    from app.gateway.app import create_app
    app = create_app()

    # 启动服务器
    logger.info(f"启动 DeerFlow Gateway...")
    logger.info(f"监听地址: http://{args.host}:{args.port}")
    logger.info(f"API 文档: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
