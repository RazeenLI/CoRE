"""
HFLLMClient: Lightweight Hugging Face LLM Wrapper
HFLLMClient：轻量级 Hugging Face 大语言模型封装器

This module provides a minimal client for loading and calling local Hugging Face
causal language models, such as Qwen ("Qwen/Qwen3-8B") or Llama ("meta-llama/Llama-3.1-8B-Instruct"). It only handles model loading,
chat-template formatting, and text generation.

本模块提供一个最小化的 Hugging Face 本地大语言模型调用接口，例如 Qwen 或 Llama。
它只负责模型加载、chat template 格式化和文本生成。

Important:
重要说明：

- The LLM client should be created only once per experiment/run.
- Each agent should share the same client instance instead of loading the model again.
- Agent-specific logic, prompt construction, JSON parsing, schema validation, and routing
  should be implemented outside this class.

- 每次实验 / 运行中，LLM client 只应该创建一次。
- 所有 agent 应该共享同一个 client 实例，而不是每个 agent 重新加载模型。
- agent 的 prompt 构造、JSON 解析、schema 校验和流程路由逻辑不应该放在这个类里。

Example:
示例：

    from core.llm_client import HFLLMClient
    from agents.profiler_agent import ProfilerAgent
    from agents.matcher_agent import MatcherAgent
    from agents.evolution_agent import EvolutionAgent

    llm = HFLLMClient(
        model_name="Qwen/Qwen3-8B",
        default_mode="non_thinking",
        debug=False,
    )

    llm = HFLLMClient(
        model_name="Qwen/Qwen3-8B",
        default_mode="thinking",
        debug=False,
    )


    profiler = ProfilerAgent(llm_client=llm)
    matcher = MatcherAgent(llm_client=llm)
    evolution = EvolutionAgent(llm_client=llm)

    messages = [
        {"role": "system", "content": "You are a schema matching assistant."},
        {"role": "user", "content": "Match incoming columns to the existing schema."}
    ]

    output = llm.generate(messages, max_new_tokens=512)
    result = llm.generate_json(
        prompt,
        mode="thinking",
        strip_thinking=True,
    )
    print(output)
"""

import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


GenerationMode = Literal["thinking", "non_thinking"]


@dataclass(frozen=True)
class DecodingConfig:
    do_sample: bool = False
    temperature: float = 0.0


DETERMINISTIC_DECODING = DecodingConfig()


def supports_thinking(model_name: str) -> bool:
    return "qwen3" in model_name.lower()


class HFLLMClient:
    def __init__(
        self,
        model_name: str,
        device_map: str = "auto",
        trust_remote_code: bool = True,
        default_mode: GenerationMode = "non_thinking",
        debug: bool = False,
    ) -> None:
        self.model_name = model_name
        self.default_mode = default_mode
        self.debug = debug
        self.supports_thinking = supports_thinking(model_name)
        self.usage_records: list[dict[str, Any]] = []
        self.current_caller: str | None = None

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=trust_remote_code,
        )

        dtype = self._infer_dtype()

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=dtype,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
        )

        self.model.eval()

        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _infer_dtype(self) -> torch.dtype:
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        if torch.cuda.is_available():
            return torch.float16
        return torch.float32

    def _input_device(self) -> torch.device:
        return self.model.get_input_embeddings().weight.device

    def _get_decoding_config(
        self,
        mode: GenerationMode,
    ) -> DecodingConfig:
        if mode not in {"thinking", "non_thinking"}:
            raise ValueError(f"Unsupported generation mode: {mode}")

        return DETERMINISTIC_DECODING

    def _build_prompt(
        self,
        messages: list[dict[str, str]],
        mode: GenerationMode,
    ) -> str:
        kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }

        if self.supports_thinking:
            kwargs["enable_thinking"] = mode == "thinking"

        return self.tokenizer.apply_chat_template(
            messages,
            **kwargs,
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int = 2048,
        mode: GenerationMode | None = None,
        strip_thinking: bool = True,
    ) -> str:
        mode = mode or self.default_mode

        if mode == "thinking" and not self.supports_thinking:
            raise ValueError(
                f"Model '{self.model_name}' does not support thinking mode."
            )

        prompt = self._build_prompt(messages, mode)

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            add_special_tokens=False,
        ).to(self._input_device())

        decoding = self._get_decoding_config(mode)

        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            "do_sample": decoding.do_sample,
        }

        # In Transformers, temperature=0 is represented by greedy decoding.
        # Do not pass temperature when sampling is disabled.
        if decoding.do_sample:
            generation_kwargs["temperature"] = decoding.temperature

        started_at = perf_counter()
        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                **generation_kwargs,
            )

        input_len = inputs["input_ids"].shape[-1]
        generated_ids = outputs[0][input_len:]
        self.usage_records.append(
            {
                "caller": self.current_caller or "unknown",
                "model": self.model_name,
                "mode": mode,
                "input_tokens": int(input_len),
                "output_tokens": int(generated_ids.shape[-1]),
                "elapsed_seconds": perf_counter() - started_at,
            }
        )

        text = self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()

        if strip_thinking:
            text = strip_qwen_thinking(text)

        if self.debug:
            print("RAW LLM OUTPUT:")
            print(text)
            print("=" * 80)

        return text

    def generate_json(
        self,
        prompt: str,
        max_new_tokens: int = 4096,
        mode: GenerationMode | None = None,
        strip_thinking: bool = True,
    ) -> dict[str, Any]:
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        text = self.generate(
            messages=messages,
            max_new_tokens=max_new_tokens,
            mode=mode,
            strip_thinking=strip_thinking,
        )

        return extract_json_object(text)

    def usage_summary(self) -> dict[str, Any]:
        """Return serializable per-call and aggregate token/cost inputs."""
        by_caller: dict[str, dict[str, Any]] = {}
        for record in self.usage_records:
            caller = str(record["caller"])
            entry = by_caller.setdefault(
                caller,
                {"call_count": 0, "input_tokens": 0, "output_tokens": 0,
                 "elapsed_seconds": 0.0},
            )
            entry["call_count"] += 1
            entry["input_tokens"] += record["input_tokens"]
            entry["output_tokens"] += record["output_tokens"]
            entry["elapsed_seconds"] += record["elapsed_seconds"]
        return {
            "model": self.model_name,
            "call_count": len(self.usage_records),
            "input_tokens": sum(r["input_tokens"] for r in self.usage_records),
            "output_tokens": sum(r["output_tokens"] for r in self.usage_records),
            "elapsed_seconds": sum(r["elapsed_seconds"] for r in self.usage_records),
            "by_caller": by_caller,
            "calls": list(self.usage_records),
        }


def strip_qwen_thinking(text: str) -> str:
    text = text.strip()

    return re.sub(
        r"(?s)<think>.*?</think>",
        "",
        text,
    ).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        text,
        flags=re.DOTALL,
    )

    if code_block_match:
        return json.loads(code_block_match.group(1))

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and start < end:
        json_text = text[start : end + 1]
        return json.loads(json_text)

    raise ValueError(f"Could not extract JSON object from LLM output:\n{text}")
