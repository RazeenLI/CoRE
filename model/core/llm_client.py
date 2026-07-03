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

    llm = HFLLMClient(model_name="Qwen/Qwen3-8B")

    profiler = ProfilerAgent(llm_client=llm)
    matcher = MatcherAgent(llm_client=llm)
    evolution = EvolutionAgent(llm_client=llm)

    messages = [
        {"role": "system", "content": "You are a schema matching assistant."},
        {"role": "user", "content": "Match incoming columns to the existing schema."}
    ]

    output = llm.generate(messages, max_new_tokens=512, temperature=0.0)
    print(output)
"""

import torch
import json
import re
from typing import Any
from transformers import AutoTokenizer, AutoModelForCausalLM


class HFLLMClient:
    def __init__(
        self,
        model_name: str,
        device_map: str = "auto",
        trust_remote_code: bool = True,
    ):
        self.model_name = model_name

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=trust_remote_code,
        )

        dtype = self._infer_dtype()

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
        )

        self.model.eval()

        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _infer_dtype(self):
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        if torch.cuda.is_available():
            return torch.float16
        return torch.float32

    def generate(
        self,
        messages,
        max_new_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            add_special_tokens=False,
        ).to(self.model.device)

        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }

        if temperature > 0:
            generation_kwargs.update({
                "do_sample": True,
                "temperature": temperature,
            })
        else:
            generation_kwargs.update({
                "do_sample": False,
            })

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                **generation_kwargs,
            )

        input_len = inputs["input_ids"].shape[-1]
        generated_ids = outputs[0][input_len:]

        return self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()
    
    def generate_json(
        self,
        prompt: str,
        max_new_tokens: int = 2048,
        temperature: float = 0.0,
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
            temperature=temperature,
        )

        return extract_json_object(text)
    

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