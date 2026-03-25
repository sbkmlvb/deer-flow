"""
DeerFlow 模型配置 API
提供模型配置的管理接口
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])

CONFIG_FILE_NAME = "config.yaml"
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


class ModelConfig(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    use: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    supports_thinking: bool = False
    supports_vision: bool = False


class ModelsConfigRequest(BaseModel):
    models: list[ModelConfig]
    default_model: str = "gpt-4"


def get_config_path() -> Path:
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS).parent
    else:
        base_path = Path(__file__).parent.parent

    config_path = os.environ.get('DEER_FLOW_CONFIG_PATH')
    if config_path:
        return Path(config_path)

    for check_path in [
        base_path / "config.yaml",
        base_path.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]:
        if check_path.exists():
            return check_path

    return base_path / "config.yaml"


def load_config() -> dict:
    """加载配置文件"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return {}


def save_config(config: dict) -> bool:
    """保存配置文件"""
    config_path = get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


@router.get("/")
async def list_models():
    """获取模型列表"""
    config = load_config()
    models = config.get('models', DEFAULT_MODELS)

    default_model = config.get('default_model', 'gpt-4')

    return {
        "models": models,
        "default_model": default_model,
    }


@router.get("/config")
async def get_models_config():
    """获取模型配置"""
    config = load_config()
    return {
        "models": config.get('models', DEFAULT_MODELS),
        "default_model": config.get('default_model', 'gpt-4'),
    }


@router.post("/config")
async def update_models_config(request: ModelsConfigRequest):
    """更新模型配置"""
    config = load_config()

    models_data = []
    for m in request.models:
        model_dict = m.model_dump(exclude_none=True)
        if model_dict.get('api_key'):
            model_dict['api_key'] = os.path.expandvars(model_dict['api_key'])
        if model_dict.get('base_url'):
            model_dict['base_url'] = os.path.expandvars(model_dict['base_url'])
        models_data.append(model_dict)

    config['models'] = models_data
    config['default_model'] = request.default_model

    if save_config(config):
        return {"success": True, "message": "Configuration saved"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")


@router.post("/add")
async def add_model(model: ModelConfig):
    """添加模型"""
    config = load_config()
    models = config.get('models', [])

    for existing in models:
        if existing.get('name') == model.name:
            raise HTTPException(status_code=400, detail=f"Model {model.name} already exists")

    model_dict = model.model_dump(exclude_none=True)
    if model_dict.get('api_key'):
        model_dict['api_key'] = os.path.expandvars(model_dict['api_key'])
    if model_dict.get('base_url'):
        model_dict['base_url'] = os.path.expandvars(model_dict['base_url'])

    models.append(model_dict)
    config['models'] = models

    if save_config(config):
        return {"success": True, "model": model_dict}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")


@router.delete("/{model_name}")
async def delete_model(model_name: str):
    """删除模型"""
    config = load_config()
    models = config.get('models', [])

    original_count = len(models)
    models = [m for m in models if m.get('name') != model_name]

    if len(models) == original_count:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    config['models'] = models

    if save_config(config):
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")


@router.put("/{model_name}")
async def update_model(model_name: str, model: ModelConfig):
    """更新模型"""
    config = load_config()
    models = config.get('models', [])

    found = False
    for i, existing in enumerate(models):
        if existing.get('name') == model_name:
            model_dict = model.model_dump(exclude_none=True)
            if model_dict.get('api_key'):
                model_dict['api_key'] = os.path.expandvars(model_dict['api_key'])
            if model_dict.get('base_url'):
                model_dict['base_url'] = os.path.expandvars(model_dict['base_url'])
            models[i] = model_dict
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    config['models'] = models

    if save_config(config):
        return {"success": True, "model": models[found - 1] if found else None}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")


@router.post("/set-default/{model_name}")
async def set_default_model(model_name: str):
    """设置默认模型"""
    config = load_config()
    models = config.get('models', [])

    model_exists = any(m.get('name') == model_name for m in models)
    if not model_exists:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")

    config['default_model'] = model_name

    if save_config(config):
        return {"success": True, "default_model": model_name}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")
