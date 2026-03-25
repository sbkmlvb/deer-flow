"""智谱 AI 思考模式 Provider

支持智谱 AI GLM 系列模型的深度思考功能，支持流式响应。

智谱 AI API 直接返回 reasoning_content 字段，无需特殊处理。

使用方法:
在 config.yaml 中配置:
  - name: glm-5-turbo
    display_name: GLM-5-Turbo
    use: deerflow.models.zhipu_thinking:ZhipuChatModel
    model: glm-5-turbo
    api_key: $ZHIPU_API_KEY
    base_url: https://open.bigmodel.cn/api/coding/paas/v4
    thinking_enabled: true
    supports_thinking: true
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import (
    _convert_delta_to_message_chunk,
    _create_usage_metadata,
)

logger = logging.getLogger(__name__)


def _with_reasoning_content(
    message: AIMessage | AIMessageChunk,
    reasoning: str | None,
    *,
    preserve_whitespace: bool = False,
):
    if not reasoning:
        return message

    additional_kwargs = dict(message.additional_kwargs)
    if preserve_whitespace:
        existing = additional_kwargs.get("reasoning_content")
        additional_kwargs["reasoning_content"] = (
            f"{existing}{reasoning}" if isinstance(existing, str) else reasoning
        )
    else:
        merged: list[str] = []
        for value in [additional_kwargs.get("reasoning_content"), reasoning]:
            if not value:
                continue
            normalized = value.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        additional_kwargs["reasoning_content"] = "\n\n".join(merged) if merged else None

    return message.model_copy(update={"additional_kwargs": additional_kwargs})


class ZhipuChatModel(ChatOpenAI):
    """智谱 AI 思考模式 Provider
    
    继承 ChatOpenAI 以复用 OpenAI 兼容 API
    智谱 AI 直接返回 reasoning_content 字段（在 delta 中）
    """
    
    thinking_enabled: bool = True
    
    model_config = {"extra": "allow", "arbitrary_types_allowed": True}
    
    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
    
    @property
    def _default_params(self) -> dict[str, Any]:
        params = super()._default_params
        if self.thinking_enabled:
            if "extra_body" not in params:
                params["extra_body"] = {}
            params["extra_body"]["thinking"] = {"type": "enabled"}
        return params
    
    @property
    def _client_params(self) -> dict[str, Any]:
        params = super()._client_params
        if self.thinking_enabled:
            if "extra_body" not in params:
                params["extra_body"] = {}
            params["extra_body"]["thinking"] = {"type": "enabled"}
        return params
    
    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if self.thinking_enabled:
            if "extra_body" not in payload:
                payload["extra_body"] = {}
            payload["extra_body"]["thinking"] = {"type": "enabled"}
        return payload
    
    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        if chunk.get("type") == "content.delta":
            return None

        token_usage = chunk.get("usage")
        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        usage_metadata = (
            _create_usage_metadata(token_usage, chunk.get("service_tier"))
            if token_usage
            else None
        )

        if len(choices) == 0:
            generation_chunk = ChatGenerationChunk(
                message=default_chunk_class(content="", usage_metadata=usage_metadata),
                generation_info=base_generation_info,
            )
            if self.output_version == "v1":
                generation_chunk.message.content = []
                generation_chunk.message.response_metadata["output_version"] = "v1"
            return generation_chunk

        choice = choices[0]
        delta = choice.get("delta")
        if delta is None:
            return None

        message_chunk = _convert_delta_to_message_chunk(delta, default_chunk_class)
        generation_info = {**base_generation_info} if base_generation_info else {}

        if finish_reason := choice.get("finish_reason"):
            generation_info["finish_reason"] = finish_reason
            if model_name := chunk.get("model"):
                generation_info["model_name"] = model_name
            if system_fingerprint := chunk.get("system_fingerprint"):
                generation_info["system_fingerprint"] = system_fingerprint
            if service_tier := chunk.get("service_tier"):
                generation_info["service_tier"] = service_tier

        logprobs = choice.get("logprobs")
        if logprobs:
            generation_info["logprobs"] = logprobs

        reasoning = delta.get("reasoning_content") if isinstance(delta, Mapping) else None
        if isinstance(message_chunk, AIMessageChunk):
            if usage_metadata:
                message_chunk.usage_metadata = usage_metadata
            if reasoning:
                message_chunk = _with_reasoning_content(
                    message_chunk,
                    reasoning,
                    preserve_whitespace=True,
                )

        message_chunk.response_metadata["model_provider"] = "openai"
        return ChatGenerationChunk(
            message=message_chunk,
            generation_info=generation_info or None,
        )
    
    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()
        choices = response_dict.get("choices", [])

        generations: list[ChatGeneration] = []
        for index, generation in enumerate(result.generations):
            choice = choices[index] if index < len(choices) else {}
            message = generation.message
            if isinstance(message, AIMessage):
                choice_message = choice.get("message", {}) if isinstance(choice, Mapping) else {}
                reasoning = choice_message.get("reasoning_content")
                
                updated_message = message
                if reasoning:
                    updated_message = _with_reasoning_content(updated_message, reasoning)

                generation = ChatGeneration(
                    message=updated_message,
                    generation_info=generation.generation_info,
                )

            generations.append(generation)

        return ChatResult(generations=generations, llm_output=result.llm_output)
