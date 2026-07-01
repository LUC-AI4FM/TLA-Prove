"""Sampling-parameter regression tests for the Ollama inference client.

repeat_penalty > 1.0 corrupts formal-language generation: on the 20-row
benchmark, chattla:20b-fc128best scored 0/20 SANY with repeat_penalty=1.3
while the same checkpoint produced TLC-gold specs at repeat_penalty=1.0
(duplicated declarations, mangled identifiers like `NumPHILOS`, and invented
keywords like `CONSTDEF` are the penalty avoiding already-used tokens).
These tests pin the client to a penalty-free default with an env override.
"""

import importlib


class _FakeOllamaClient:
    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return {"response": " Probe ----\nVARIABLE x\nInit == x = 0\nNext == x' = x\n===="}


def _client_with_fake(module):
    # Bypass __init__: it lazily imports the ollama package, which is not a
    # test dependency. The fake stands in for ollama.Client.
    client = module.ChatTLAClient.__new__(module.ChatTLAClient)
    client.model = "chattla:test"
    client.reasoning = "medium"
    client._temp_override = None
    client._last_plan_used = False
    fake = _FakeOllamaClient()
    client._client = fake
    return client, fake


def test_generate_spec_defaults_to_no_repeat_penalty() -> None:
    import src.inference.ollama_client as module

    reloaded = importlib.reload(module)
    client, fake = _client_with_fake(reloaded)

    client.generate_spec("a simple counter", rag_k=0)

    assert fake.calls, "expected a generate() call"
    assert fake.calls[0]["options"]["repeat_penalty"] == 1.0


def test_repeat_penalty_honors_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CHATTLA_REPEAT_PENALTY", "1.15")

    import src.inference.ollama_client as module

    reloaded = importlib.reload(module)
    try:
        client, fake = _client_with_fake(reloaded)
        client.generate_spec("a simple counter", rag_k=0)
        assert fake.calls[0]["options"]["repeat_penalty"] == 1.15
    finally:
        monkeypatch.delenv("CHATTLA_REPEAT_PENALTY")
        importlib.reload(module)


def test_self_correct_uses_same_repeat_penalty_default() -> None:
    import src.inference.ollama_client as module

    reloaded = importlib.reload(module)
    client, fake = _client_with_fake(reloaded)

    client._self_correct("---- MODULE Probe ----\n====", "SANY error: something")

    assert fake.calls, "expected a generate() call"
    assert fake.calls[0]["options"]["repeat_penalty"] == 1.0
