#!/usr/bin/env python3
"""
llm.py — one place the Extend LLM talks to Claude, so the provider is a config switch.

Set EXTEND_LLM_PROVIDER to bill through your COMPANY's account instead of a personal Anthropic key:
  anthropic (default) — Anthropic API key or `ant auth login` profile (ANTHROPIC_API_KEY / org key)
  bedrock             — Amazon Bedrock (AWS creds; AWS_REGION). No Anthropic key. Model id: anthropic.claude-opus-4-8
  vertex              — Google Vertex AI (GCP ADC; ANTHROPIC_VERTEX_PROJECT_ID + CLOUD_ML_REGION). No Anthropic key.
  foundry             — Microsoft Foundry (AZURE_* / api key + resource)
  aws                 — Claude Platform on AWS (SigV4; AWS_REGION + ANTHROPIC_AWS_WORKSPACE_ID)

Model via EXTEND_LLM_MODEL (defaults to the right per-provider Opus 4.8 id). Every engine calls complete().
Install extras as needed: pip install "anthropic[vertex]"  /  "anthropic[aws]".
"""
import os

_DEFAULT_MODEL = {
    "anthropic": "claude-opus-4-8",
    "aws": "claude-opus-4-8",
    "bedrock": "anthropic.claude-opus-4-8",   # Bedrock model ids take the anthropic. prefix
    "vertex": "claude-opus-4-8",              # Vertex uses the bare id
    "foundry": "claude-opus-4-8",
}
_client = None


def provider() -> str:
    return os.environ.get("EXTEND_LLM_PROVIDER", "anthropic").lower()


def model() -> str:
    return os.environ.get("EXTEND_LLM_MODEL") or _DEFAULT_MODEL.get(provider(), "claude-opus-4-8")


def _make_client():
    p = provider()
    try:
        if p == "bedrock":
            from anthropic import AnthropicBedrockMantle
            return AnthropicBedrockMantle(aws_region=os.environ.get("AWS_REGION", "us-east-1"))
        if p == "vertex":
            from anthropic import AnthropicVertex
            return AnthropicVertex(project_id=os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"),
                                   region=os.environ.get("CLOUD_ML_REGION", "global"))
        if p == "foundry":
            from anthropic import AnthropicFoundry
            return AnthropicFoundry(api_key=os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"),
                                    resource=os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE"))
        if p == "aws":
            from anthropic import AnthropicAWS
            return AnthropicAWS()
        from anthropic import Anthropic  # default: Anthropic API key / org key / ant-auth profile
        return Anthropic()
    except ImportError as e:
        raise RuntimeError(f"provider {p!r} needs an SDK extra — pip install \"anthropic[{p}]\" ({e})")


def client():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def complete(system: str, messages: list[dict], max_tokens: int = 4000) -> str:
    """Provider-agnostic text completion. messages = [{'role','content'}]. Returns concatenated text."""
    resp = client().messages.create(model=model(), max_tokens=max_tokens, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
