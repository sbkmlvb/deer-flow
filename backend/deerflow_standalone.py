#!/usr/bin/env python3
"""
DeerFlow 独立打包入口 v4 (完全独立架构)
DeerFlow Standalone Entry Point - Fully Bundled

核心架构:
  - 直接嵌入 DeerFlowClient，无需 LangGraph 服务器
  - FastAPI 提供 HTTP API + 静态文件服务
  - 前端 Next.js 预编译静态文件

使用方法:
  python deerflow_standalone.py                    # 启动服务
  python deerflow_standalone.py --check           # 检查依赖
  python deerflow_standalone.py --port 2026        # 指定端口
"""

import argparse
import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Generator, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEERFLOW_VERSION = "2.0"

DEFAULT_MODELS = [
    {
        "name": "gpt-4",
        "display_name": "GPT-4",
        "description": "OpenAI GPT-4 模型",
        "use": "langchain_openai.ChatOpenAI",
        "model": "gpt-4",
        "supports_thinking": False,
        "supports_vision": True,
    },
    {
        "name": "gpt-4o",
        "display_name": "GPT-4o",
        "description": "OpenAI GPT-4o 模型",
        "use": "langchain_openai.ChatOpenAI",
        "model": "gpt-4o",
        "supports_thinking": False,
        "supports_vision": True,
    },
    {
        "name": "claude-sonnet-4-20250514",
        "display_name": "Claude Sonnet 4",
        "description": "Anthropic Claude Sonnet 4 模型",
        "use": "langchain_anthropic.ChatAnthropic",
        "model": "claude-sonnet-4-20250514",
        "supports_thinking": False,
        "supports_vision": True,
    },
]


def get_base_path() -> Path:
    """获取基础路径（兼容 PyInstaller onefile 模式）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_config_path_from_module() -> Path:
    """获取配置文件路径"""
    base_path = get_base_path()

    config_path = os.environ.get('DEER_FLOW_CONFIG_PATH')
    if config_path:
        return Path(config_path)

    for check_path in [
        base_path / "config.yaml",
        base_path / "_internal" / "config.yaml",
        Path.cwd() / "config.yaml",
    ]:
        if check_path.exists():
            return check_path

    return base_path / "config.yaml"


def load_config_from_path(config_path: Path) -> dict:
    """从路径加载配置"""
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return {}


def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_for_port(port: int, timeout: int = 60) -> bool:
    """等待端口就绪"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def setup_python_path():
    """设置 Python 路径以便正确导入模块"""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent

    packages_harness = str(base_path / "packages" / "harness")
    if packages_harness not in sys.path:
        sys.path.insert(0, packages_harness)

    backend_path = str(base_path)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


def get_resource_path(relative_path: str = "") -> Path:
    """获取资源文件路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return base_path / relative_path if relative_path else base_path


def find_frontend_dir() -> Optional[Path]:
    """查找前端构建目录"""
    possible_dirs = [
        Path("frontend/.next"),
        Path("dist/frontend/.next"),
        Path(__file__).parent / "frontend" / ".next",
        Path(__file__).parent.parent / "frontend" / ".next",
        get_resource_path("frontend/.next"),
        get_resource_path("dist/frontend/.next"),
        get_resource_path("_internal/frontend/.next"),
    ]

    for d in possible_dirs:
        if d.exists() and (d / "server").exists():
            logger.info(f"Frontend found: {d.parent}")
            return d.parent

    logger.warning("Frontend directory not found")
    return None


def find_node_bin() -> Optional[Path]:
    """查找 Node.js 二进制文件目录"""
    possible_dirs = [
        Path("node_bin"),
        Path(__file__).parent / "node_bin",
        Path(__file__).parent.parent / "node_bin",
        get_resource_path("node_bin"),
        get_resource_path("_internal/node_bin"),
    ]

    for d in possible_dirs:
        if d.exists() and (d / "bin" / "node").exists():
            logger.info(f"Node.js found: {d / 'bin' / 'node'}")
            return d

    logger.warning("Node.js binary not found")
    return None


def check_python_deps() -> bool:
    """检查 Python 依赖"""
    required = ['fastapi', 'uvicorn', 'pydantic', 'langchain_core', 'langchain_openai']
    missing = []

    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)

    if missing:
        logger.error(f"Missing packages: {', '.join(missing)}")
        return False

    logger.info("Python dependencies OK")
    return True


class DeerFlowStandaloneAPI:
    """DeerFlow 独立版 API 服务（嵌入 DeerFlowClient）"""

    def __init__(self, frontend_dir: Optional[Path] = None):
        self.frontend_dir = frontend_dir
        self.client = None
        self.loop = None
        self.thread = None
        self.running = False
        self.node_process: Optional[subprocess.Popen] = None

    def _init_client(self):
        """初始化 DeerFlowClient（在线程中）"""
        setup_python_path()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            sys.path.insert(0, str(Path(__file__).parent / "packages" / "harness"))
            from deerflow.client import DeerFlowClient

            self.client = DeerFlowClient()
            logger.info("DeerFlowClient initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DeerFlowClient: {e}")
            self.client = None

        self.running = True
        self.loop.run_forever()

    def _start_node_frontend(self):
        """启动 Node.js 前端服务"""
        node_bin_dir = find_node_bin()
        if not node_bin_dir:
            logger.warning("Node.js binary not found, skipping frontend")
            return False

        node_bin = node_bin_dir / "bin" / "node"
        if not node_bin.exists():
            logger.warning("Node.js binary not found at expected path")
            return False

        frontend_dir = find_frontend_dir()
        if not frontend_dir:
            logger.warning("Frontend directory not found, skipping frontend")
            return False

        next_bin = self._find_next_bin(frontend_dir)
        if not next_bin:
            logger.warning("Next.js binary not found, skipping frontend")
            return False

        env = os.environ.copy()
        env['PORT'] = '3000'
        env['HOSTNAME'] = '127.0.0.1'
        env['NODE_ENV'] = 'production'
        env.pop('NODE_PATH', None)

        try:
            logger.info("Starting Node.js frontend...")
            self.node_process = subprocess.Popen(
                [str(node_bin), str(next_bin), "start", "-p", "3000", "-H", "127.0.0.1"],
                cwd=str(frontend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            logger.info("Node.js frontend started")
            return True
        except Exception as e:
            logger.error(f"Failed to start Node.js frontend: {e}")
            return False

    def _find_next_bin(self, frontend_dir: Path) -> Optional[Path]:
        """查找 Next.js 二进制文件（支持 pnpm 结构）"""
        next_bin = frontend_dir / "node_modules" / "next" / "dist" / "bin" / "next"
        if next_bin.exists():
            return next_bin

        pnpm_store = frontend_dir / "node_modules" / ".pnpm"
        if pnpm_store.exists():
            for item in pnpm_store.iterdir():
                if item.is_dir() and item.name.startswith("next@"):
                    next_bin = item / "node_modules" / "next" / "dist" / "bin" / "next"
                    if next_bin.exists():
                        logger.info(f"Found Next.js in pnpm store: {item.name}")
                        return next_bin

        return None

    def start(self):
        """启动 API 服务"""
        self._start_node_frontend()

        self.thread = threading.Thread(target=self._init_client, daemon=True)
        self.thread.start()

        for _ in range(30):
            if self.client is not None:
                break
            time.sleep(0.5)

        if self.client is None:
            logger.warning("DeerFlowClient not ready yet")

    def stop(self):
        """停止 API 服务"""
        self.running = False

        if self.node_process:
            try:
                self.node_process.terminate()
                self.node_process.wait(timeout=5)
            except Exception:
                self.node_process.kill()
            self.node_process = None

        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=5)

    def chat(self, message: str, thread_id: Optional[str] = None, **kwargs) -> dict:
        """发送消息并获取响应"""
        if self.client is None:
            return {"error": "Client not initialized"}

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        try:
            # chat 是同步方法，直接调用
            response = self.client.chat(message, thread_id=thread_id, **kwargs)
            return {"response": response, "thread_id": thread_id}
        except Exception as e:
            return {"error": str(e)}

    def stream(self, message: str, thread_id: Optional[str] = None, **kwargs):
        """流式发送消息"""
        if self.client is None:
            yield {"error": "Client not initialized"}
            return

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        def run_stream():
            return self.client.stream(message, thread_id=thread_id, **kwargs)

        try:
            for event in self.client.stream(message, thread_id=thread_id, **kwargs):
                yield {"type": event.type, "data": event.data}
        except Exception as e:
            yield {"error": str(e)}


def create_standalone_app(frontend_dir: Optional[Path] = None):
    """创建独立的 FastAPI 应用（带 DeerFlowClient 嵌入）"""

    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="DeerFlow Standalone")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_path = frontend_dir
    api_service = DeerFlowStandaloneAPI(frontend_dir)

    @app.on_event("startup")
    async def startup():
        logger.info("Starting DeerFlow Standalone...")
        api_service.start()
        logger.info("DeerFlow Standalone ready")

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Shutting down DeerFlow Standalone...")
        api_service.stop()

    if frontend_path and frontend_path.exists():
        next_dir = frontend_path / ".next"
        if next_dir.exists():
            app.mount("/_next", StaticFiles(directory=str(next_dir / "static"), html=False), name="next_static")

    @app.get("/")
    async def root():
        """重定向到前端"""
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="http://127.0.0.1:3000/", status_code=307)

    @app.get("/workspace")
    async def workspace():
        """工作区"""
        import urllib.request
        try:
            response = urllib.request.urlopen("http://127.0.0.1:3000/workspace", timeout=2)
            from starlette.responses import Response
            return Response(content=response.read(), media_type=response.headers.get("content-type", "text/html"))
        except Exception:
            return JSONResponse({"message": "DeerFlow Workspace"})

    class ChatRequest(BaseModel):
        message: str
        thread_id: Optional[str] = None
        model_name: Optional[str] = None
        thinking_enabled: bool = True
        plan_mode: bool = False

    class StreamRequest(BaseModel):
        message: str
        thread_id: Optional[str] = None
        model_name: Optional[str] = None
        thinking_enabled: bool = True

    class ModelConfig(BaseModel):
        name: str
        display_name: Optional[str] = None
        description: Optional[str] = None
        use: str = "langchain_openai.ChatOpenAI"
        model: str = ""
        api_key: Optional[str] = None
        base_url: Optional[str] = None
        supports_thinking: bool = False
        supports_vision: bool = False

    class ModelsConfigRequest(BaseModel):
        models: list[ModelConfig]
        default_model: str = "gpt-4"

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "healthy",
            "service": "deer-flow-standalone",
            "version": DEERFLOW_VERSION,
            "client_ready": api_service.client is not None
        })

    @app.get("/api/models")
    async def list_models():
        """列出可用模型"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")
        try:
            return api_service.client.list_models()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/models/config")
    async def get_models_config():
        """获取模型配置"""
        config_path = get_config_path_from_module()
        config = load_config_from_path(config_path)
        return {
            "models": config.get('models', DEFAULT_MODELS),
            "default_model": config.get('default_model', 'gpt-4'),
        }

    @app.post("/api/models/config")
    async def update_models_config(request: ModelsConfigRequest):
        """更新模型配置"""
        import yaml
        config = {}
        config_path = get_config_path_from_module()

        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
        except Exception:
            pass

        models_data = []
        for m in request.models:
            model_dict = m.model_dump(exclude_none=True)
            models_data.append(model_dict)

        config['models'] = models_data
        config['default_model'] = request.default_model

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)
            return {"success": True, "message": "Configuration saved"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/models/{model_name}")
    async def model_operation(model_name: str):
        """模型操作（占位）"""
        raise HTTPException(status_code=501, detail="Not implemented")

    @app.get("/api/skills")
    async def list_skills(enabled_only: bool = False):
        """列出可用技能"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")
        try:
            return api_service.client.list_skills(enabled_only=enabled_only)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        """发送聊天消息"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")

        try:
            result = api_service.chat(
                message=request.message,
                thread_id=request.thread_id,
                model_name=request.model_name,
                thinking_enabled=request.thinking_enabled,
                plan_mode=request.plan_mode
            )
            if "error" in result:
                raise HTTPException(status_code=500, detail=result["error"])
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/chat/stream")
    async def stream(request: StreamRequest):
        """流式聊天（简单轮询实现，实际生产应用 SSE）"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")

        from fastapi.responses import StreamingResponse

        def generate():
            try:
                for event in api_service.stream(
                    message=request.message,
                    thread_id=request.thread_id,
                    model_name=request.model_name,
                    thinking_enabled=request.thinking_enabled
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/memory")
    async def get_memory():
        """获取记忆数据"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")
        try:
            return api_service.client.get_memory()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # LangGraph API 兼容层 - 让前端能正常工作
    # ========================================================================

    # 线程存储（简单内存实现）
    threads_store: dict[str, dict] = {}
    runs_store: dict[str, dict] = {}
    messages_store: dict[str, list] = {}

    class CreateThreadRequest(BaseModel):
        metadata: Optional[dict] = None

    class CreateRunRequest(BaseModel):
        assistant_id: str = "lead_agent"
        input: Optional[dict] = None
        config: Optional[dict] = None
        metadata: Optional[dict] = None

    @app.post("/api/langgraph/threads")
    async def create_thread(request: CreateThreadRequest = CreateThreadRequest()):
        """创建新线程 - LangGraph API 兼容"""
        thread_id = str(uuid.uuid4())
        threads_store[thread_id] = {
            "thread_id": thread_id,
            "created_at": time.time(),
            "metadata": request.metadata or {},
        }
        messages_store[thread_id] = []
        return {"thread_id": thread_id, "metadata": request.metadata or {}}

    @app.get("/api/langgraph/threads")
    async def list_threads():
        """列出所有线程"""
        results = []
        for thread_id, thread_data in threads_store.items():
            results.append({
                "thread_id": thread_id,
                "metadata": thread_data.get("metadata", {}),
                "created_at": thread_data.get("created_at", 0),
            })
        return {"threads": results}

    @app.post("/api/langgraph/threads/search")
    async def search_threads(request: dict = {}):
        """搜索线程"""
        # 简单实现：返回所有线程
        results = []
        for thread_id, thread_data in threads_store.items():
            results.append({
                "thread_id": thread_id,
                "metadata": thread_data.get("metadata", {}),
                "created_at": thread_data.get("created_at", 0),
                "messages_count": len(messages_store.get(thread_id, [])),
            })
        return {"threads": results}

    @app.get("/api/langgraph/threads/{thread_id}")
    async def get_thread(thread_id: str):
        """获取线程信息"""
        if thread_id not in threads_store:
            # 自动创建线程
            threads_store[thread_id] = {
                "thread_id": thread_id,
                "created_at": time.time(),
                "metadata": {},
            }
            messages_store[thread_id] = []
        return threads_store[thread_id]

    @app.delete("/api/langgraph/threads/{thread_id}")
    async def delete_thread(thread_id: str):
        """删除线程"""
        threads_store.pop(thread_id, None)
        messages_store.pop(thread_id, None)
        runs_store.pop(thread_id, None)
        return {"status": "deleted"}

    @app.post("/api/langgraph/threads/{thread_id}/runs")
    async def create_run(thread_id: str, request: CreateRunRequest):
        """创建运行"""
        if thread_id not in threads_store:
            threads_store[thread_id] = {
                "thread_id": thread_id,
                "created_at": time.time(),
                "metadata": {},
            }
            messages_store[thread_id] = []

        run_id = str(uuid.uuid4())

        # 从 input 中提取消息
        messages = request.input or {}
        message_content = ""
        if "messages" in messages:
            for msg in messages["messages"]:
                if isinstance(msg, dict) and msg.get("type") == "human":
                    message_content = msg.get("content", "")
                    break
                elif hasattr(msg, "content"):
                    message_content = msg.content
                    break

        # 获取配置
        config = request.config or {}
        configurable = config.get("configurable", {})
        model_name = configurable.get("model_name")
        thinking_enabled = configurable.get("thinking_enabled", True)

        # 调用 chat
        result = api_service.chat(
            message=message_content,
            thread_id=thread_id,
            model_name=model_name,
            thinking_enabled=thinking_enabled,
        )

        response_text = result.get("response", "")

        # 保存消息
        messages_store[thread_id].append({
            "type": "human",
            "content": message_content,
        })
        messages_store[thread_id].append({
            "type": "ai",
            "content": response_text,
        })

        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "status": "success",
            "result": {"messages": messages_store[thread_id]},
        }

    @app.post("/api/langgraph/threads/{thread_id}/runs/stream")
    async def stream_run(thread_id: str, request: CreateRunRequest):
        """流式运行 - SSE"""
        if api_service.client is None:
            raise HTTPException(status_code=503, detail="Client not initialized")

        if thread_id not in threads_store:
            threads_store[thread_id] = {
                "thread_id": thread_id,
                "created_at": time.time(),
                "metadata": {},
            }
            messages_store[thread_id] = []

        from fastapi.responses import StreamingResponse
        import json

        # 从 input 中提取消息
        messages = request.input or {}
        message_content = ""
        if "messages" in messages:
            for msg in messages["messages"]:
                if isinstance(msg, dict) and msg.get("type") == "human":
                    message_content = msg.get("content", "")
                    break
                elif hasattr(msg, "content"):
                    message_content = msg.content
                    break

        config = request.config or {}
        configurable = config.get("configurable", {})
        model_name = configurable.get("model_name")
        thinking_enabled = configurable.get("thinking_enabled", True)

        def generate():
            run_id = str(uuid.uuid4())
            full_response = ""

            # 发送开始事件
            yield f"event: metadata\ndata: {json.dumps({'run_id': run_id})}\n\n"

            try:
                for event in api_service.stream(
                    message=message_content,
                    thread_id=thread_id,
                    model_name=model_name,
                    thinking_enabled=thinking_enabled,
                ):
                    event_type = event.get("type", "values")
                    event_data = event.get("data", {})

                    if event_type == "messages-tuple":
                        # 转换为 LangGraph 格式
                        content = event_data.get("content", "")
                        if content:
                            full_response += content
                            yield f"event: messages/tuple\ndata: {json.dumps({'type': 'ai', 'content': content})}\n\n"
                    else:
                        yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

                # 保存消息
                messages_store[thread_id].append({
                    "type": "human",
                    "content": message_content,
                })
                messages_store[thread_id].append({
                    "type": "ai",
                    "content": full_response,
                })

                # 发送结束事件
                yield f"event: end\ndata: {json.dumps({'run_id': run_id})}\n\n"

            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/langgraph/threads/{thread_id}/history")
    async def get_thread_history(thread_id: str):
        """获取线程历史"""
        if thread_id not in messages_store:
            return {"messages": []}
        return {"messages": messages_store[thread_id]}

    @app.get("/api/langgraph/threads/{thread_id}/runs/{run_id}")
    async def get_run(thread_id: str, run_id: str):
        """获取运行状态"""
        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "status": "completed",
        }

    @app.get("/api/langgraph/threads/{thread_id}/state")
    async def get_thread_state(thread_id: str):
        """获取线程状态"""
        return {
            "values": {
                "messages": messages_store.get(thread_id, []),
            },
            "next": [],
            "created_at": threads_store.get(thread_id, {}).get("created_at", time.time()),
        }

    @app.post("/api/langgraph/threads/{thread_id}/runs/wait")
    async def wait_run(thread_id: str, request: CreateRunRequest):
        """等待运行完成"""
        return await create_run(thread_id, request)

    # Suggestions API
    @app.post("/api/threads/{thread_id}/suggestions")
    async def get_suggestions(thread_id: str, request: dict = {}):
        """获取建议"""
        # 返回一些默认建议
        return {
            "suggestions": [
                {"text": "帮我分析一下当前的灯光设置"},
                {"text": "创建一个新的场景"},
                {"text": "查询可用的灯具列表"},
            ]
        }

    # MCP Config API
    @app.get("/api/mcp/config")
    async def get_mcp_config():
        """获取 MCP 配置"""
        return {
            "mcp_servers": {
                "jraicontroller": {
                    "enabled": True,
                    "type": "stdio",
                    "description": "JRAiController 灯光控制系统"
                }
            }
        }

    @app.put("/api/mcp/config")
    async def update_mcp_config(config: dict):
        """更新 MCP 配置"""
        return {"success": True, "message": "Config updated"}

    # Agents API
    @app.get("/api/agents")
    async def list_agents():
        """列出可用 agents"""
        return {
            "agents": [
                {
                    "id": "lead_agent",
                    "name": "Lead Agent",
                    "description": "主代理，处理所有对话"
                }
            ],
            "default_agent": "lead_agent"
        }

    # Models Config API
    @app.get("/api/models/config")
    async def get_models_config():
        """获取模型配置"""
        if api_service.client is None:
            return {"models": [], "default_model": None}
        try:
            models = api_service.client.list_models()
            return {
                "models": models.get("models", []),
                "default_model": models.get("models", [{}])[0].get("name") if models.get("models") else None
            }
        except Exception:
            return {"models": [], "default_model": None}

    # Skills API
    @app.get("/api/skills")
    async def list_skills():
        """列出所有 skills"""
        return {
            "skills": [
                {
                    "name": "lighting-control",
                    "description": "灯光控制技能",
                    "license": "MIT",
                    "category": "public",
                    "enabled": True
                }
            ]
        }

    @app.get("/api/skills/{skill_name}")
    async def get_skill(skill_name: str):
        """获取 skill 详情"""
        return {
            "name": skill_name,
            "description": "灯光控制技能",
            "license": "MIT",
            "category": "public",
            "enabled": True
        }

    @app.put("/api/skills/{skill_name}")
    async def update_skill(skill_name: str, request: dict):
        """更新 skill 状态"""
        return {
            "name": skill_name,
            "description": "灯光控制技能",
            "license": "MIT",
            "category": "public",
            "enabled": request.get("enabled", True)
        }

    # Memory API
    @app.get("/api/memory")
    async def get_memory():
        """获取记忆数据"""
        return {
            "version": "1.0",
            "lastUpdated": "",
            "user": {
                "workContext": {"summary": "", "updatedAt": ""},
                "personalContext": {"summary": "", "updatedAt": ""},
                "topOfMind": {"summary": "", "updatedAt": ""}
            },
            "history": {
                "recentMonths": {"summary": "", "updatedAt": ""},
                "earlierContext": {"summary": "", "updatedAt": ""},
                "longTermBackground": {"summary": "", "updatedAt": ""}
            },
            "facts": []
        }

    @app.post("/api/memory/reload")
    async def reload_memory():
        """重新加载记忆"""
        return await get_memory()

    @app.get("/api/memory/config")
    async def get_memory_config():
        """获取记忆配置"""
        return {
            "enabled": True,
            "storage_path": "memory.json",
            "debounce_seconds": 30,
            "max_facts": 100,
            "fact_confidence_threshold": 0.7,
            "injection_enabled": True,
            "max_injection_tokens": 2000
        }

    @app.get("/api/memory/status")
    async def get_memory_status():
        """获取记忆状态"""
        return {
            "config": await get_memory_config(),
            "data": await get_memory()
        }

    # User Profile API
    @app.get("/api/user-profile")
    async def get_user_profile():
        """获取用户配置"""
        return {"content": None}

    @app.put("/api/user-profile")
    async def update_user_profile(request: dict):
        """更新用户配置"""
        return {"content": request.get("content", "")}

    # Agents detailed API
    @app.get("/api/agents/check")
    async def check_agent_name(name: str):
        """检查 agent 名称是否可用"""
        return {"available": True, "name": name.lower()}

    @app.get("/api/agents/{name}")
    async def get_agent(name: str):
        """获取 agent 详情"""
        return {
            "name": name,
            "description": "自定义代理",
            "model": None,
            "tool_groups": None,
            "soul": ""
        }

    @app.post("/api/agents")
    async def create_agent(request: dict):
        """创建 agent"""
        return {
            "name": request.get("name", "new-agent"),
            "description": request.get("description", ""),
            "model": request.get("model"),
            "tool_groups": request.get("tool_groups"),
            "soul": request.get("soul", "")
        }

    @app.put("/api/agents/{name}")
    async def update_agent(name: str, request: dict):
        """更新 agent"""
        return {
            "name": name,
            "description": request.get("description", ""),
            "model": request.get("model"),
            "tool_groups": request.get("tool_groups"),
            "soul": request.get("soul")
        }

    @app.delete("/api/agents/{name}")
    async def delete_agent(name: str):
        """删除 agent"""
        return None  # 204 No Content

    return app


def main():
    setup_python_path()

    parser = argparse.ArgumentParser(description="DeerFlow Standalone")
    parser.add_argument("--port", type=int, default=2026, help="Port to run on")
    parser.add_argument("--frontend-dir", help="Frontend build directory")
    parser.add_argument("--check", action="store_true", help="Check dependencies")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    if args.check:
        print("Checking DeerFlow dependencies...")
        print("-" * 40)

        python_ok = check_python_deps()
        frontend_ok = find_frontend_dir() is not None

        print("-" * 40)
        print(f"Python Dependencies: {'OK' if python_ok else 'MISSING'}")
        print(f"Frontend Build:     {'OK' if frontend_ok else 'MISSING'}")
        print("-" * 40)

        if python_ok:
            print("Ready to run DeerFlow Standalone")
            return 0
        else:
            print("Missing dependencies")
            return 1

    frontend_dir = None
    if args.frontend_dir:
        frontend_dir = Path(args.frontend_dir)
    else:
        frontend_dir = find_frontend_dir()

    if frontend_dir:
        logger.info(f"Frontend directory: {frontend_dir}")

    if not check_python_deps():
        logger.error("Missing Python dependencies")
        return 1

    app = create_standalone_app(frontend_dir)

    logger.info(f"Starting DeerFlow Standalone on {args.host}:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
