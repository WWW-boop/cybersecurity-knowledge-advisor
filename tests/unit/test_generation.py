"""Provider-neutral context and provider response handling."""

import json

import httpx
import pytest

from cybersecurity_advisor.generation.answering import (
    OllamaProvider,
    OpenAIResponsesProvider,
    build_context,
)


def test_build_context_numbers_sources_and_respects_limit() -> None:
    context, sources = build_context(
        [
            {
                "chunk_id": "chunk-1",
                "content": "Use multi-factor authentication.",
                "citation": "CISA, MFA",
                "url": "https://example.com/mfa",
                "retrievers": ["dense", "graph"],
                "hybrid_score": 0.9,
            }
        ],
        max_chars=1000,
    )

    assert context.startswith("[S1] CISA, MFA")
    assert sources == [
        {
            "source_id": "S1",
            "chunk_id": "chunk-1",
            "citation": "CISA, MFA",
            "url": "https://example.com/mfa",
            "retrievers": ["dense", "graph"],
            "score": 0.9,
        }
    ]


@pytest.mark.parametrize(
    ("provider", "expected_answer", "expected_usage"),
    [
        (
            OpenAIResponsesProvider(
                api_key="test",
                model="api-model",
                base_url="https://api.example/v1",
                timeout=1,
                max_output_tokens=100,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={
                            "model": "api-model",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "API answer [S1]"}],
                                }
                            ],
                            "usage": {"input_tokens": 20, "output_tokens": 5},
                        },
                    )
                ),
            ),
            "API answer [S1]",
            (20, 5),
        ),
        (
            OllamaProvider(
                model="local-model",
                base_url="http://ollama.example",
                timeout=1,
                max_output_tokens=100,
                temperature=0.1,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={
                            "model": "local-model",
                            "response": "Local answer [S1]",
                            "prompt_eval_count": 18,
                            "eval_count": 4,
                        },
                    )
                ),
            ),
            "Local answer [S1]",
            (18, 4),
        ),
    ],
)
def test_generation_providers_return_common_result(
    provider: OpenAIResponsesProvider | OllamaProvider,
    expected_answer: str,
    expected_usage: tuple[int, int],
) -> None:
    result = provider.generate("Use evidence", "Question and evidence")

    assert result.answer == expected_answer
    assert (result.input_tokens, result.output_tokens) == expected_usage


def test_ollama_disables_thinking_so_token_budget_reaches_answer() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.read()
        assert json.loads(request.content)["think"] is False
        return httpx.Response(200, json={"response": "Answer [S1]"})

    provider = OllamaProvider(
        model="qwen3.5:4b",
        base_url="http://ollama.example",
        timeout=1,
        max_output_tokens=500,
        temperature=0.1,
        transport=httpx.MockTransport(respond),
    )

    assert provider.generate("Use evidence", "Question and evidence").answer == "Answer [S1]"
