"""Rust-cache eviction with explicit tokenizer substitutes; no model loads."""
import json
import threading
from types import SimpleNamespace

import pytest

from services.api.context import LlmTokenizer
from services.api.embedding import EmbeddingService
from services.api.settings import Settings


class TestRustTokenizer:
    __test__ = False
    loads = 0
    @classmethod
    def from_file(cls, path):
        cls.loads += 1
        return cls()
    def no_truncation(self):
        pass
    def no_padding(self):
        pass
    def encode(self, text, **kwargs):
        return SimpleNamespace(ids=list(range(len(text))))


def configured(tmp_path, monkeypatch):
    import tokenizers
    monkeypatch.setattr(tokenizers, "Tokenizer", TestRustTokenizer)
    TestRustTokenizer.loads = 0
    settings = Settings(tmp_path)
    for directory in [settings.llm_tokenizer_dir, settings.embedding_dir]:
        directory.mkdir(parents=True)
        (directory / "tokenizer.json").write_text("{}", encoding="utf-8")
    (settings.llm_tokenizer_dir / "tokenizer_config.json").write_text(json.dumps({"chat_template": "{{ messages | tojson }}"}), encoding="utf-8")
    return settings


def test_api_qwen_cache_release_preserves_template_identity_and_same_message_counts(tmp_path, monkeypatch):
    tokenizer = LlmTokenizer(configured(tmp_path, monkeypatch))
    messages = [{"role": "user", "content": "Contrôle 😀 : 72 V [S001]."}]
    original_identity = tokenizer.identity()
    original_count = tokenizer.count_messages(messages)
    original_config, original_template = tokenizer._config, tokenizer._template
    first_serialized = tokenizer.serialized(messages)
    released = tokenizer.release_tokenizer()
    assert released["state"] == "released" and tokenizer._tokenizer is None
    assert released["next_reload_measurement"] == "pending" and released["message_count_parity"]["state"] == "pending_same_serialized_input"
    assert tokenizer._config is original_config and tokenizer._template is original_template
    assert tokenizer.identity() == original_identity
    assert tokenizer.serialized(messages) == first_serialized and TestRustTokenizer.loads == 1
    assert tokenizer.count_messages(messages) == original_count and TestRustTokenizer.loads == 2
    state = tokenizer.lifecycle()
    assert state["load_count"] == 2 and state["last_load"]["reload_after_release"] is True
    assert state["last_release"]["next_reload_measurement"] == "observed"
    assert state["last_release"]["message_count_parity"]["state"] == "observed" and state["last_release"]["message_count_parity"]["counts_equal"] is True
    assert "content" not in json.dumps(state) and "Contrôle" not in json.dumps(state)
    tokenizer.count_messages([{"role": "user", "content": "Another input"}])
    assert tokenizer.lifecycle()["last_release"]["message_count_parity"]["counts_equal"] is None


def test_api_e5_cache_release_preserves_identity_and_same_prefixed_counts(tmp_path, monkeypatch):
    embedding = EmbeddingService(configured(tmp_path, monkeypatch))
    embedding._identity = {"fingerprint": "explicit-test-identity"}
    original_count = embedding.count("CCU-21 😀", passage=False)
    released = embedding.release_tokenizer()
    assert embedding._tokenizer is None and embedding._session is None
    assert embedding.identity() == {"fingerprint": "explicit-test-identity"}
    assert released["next_reload_measurement"] == "pending"
    assert embedding.count("CCU-21 😀", passage=False) == original_count
    state = embedding.lifecycle()
    assert state["tokenizer_load_count"] == 2 and state["last_tokenizer_load"]["reload_after_release"] is True
    assert state["last_tokenizer_release"]["count_parity"]["counts_equal"] is True
    assert state["last_tokenizer_release"]["next_reload_measurement"] == "observed"
    assert "CCU-21" not in json.dumps(state)


@pytest.mark.parametrize("cache_class", [EmbeddingService, LlmTokenizer])
def test_api_cache_release_waits_for_running_encode_without_freeing_its_handle(tmp_path, monkeypatch, cache_class):
    cache = cache_class(configured(tmp_path, monkeypatch))
    entered, finish, release_started, released = [threading.Event() for _ in range(4)]
    errors = []
    class BlockingTokenizer(TestRustTokenizer):
        def encode(self, text, **kwargs):
            entered.set()
            if not finish.wait(timeout=5):
                raise RuntimeError("test encoding was not released")
            return super().encode(text, **kwargs)
    cache._tokenizer = BlockingTokenizer()
    def encode():
        try:
            assert cache.count("same text") > 0
        except BaseException as error:
            errors.append(error)
    def release():
        release_started.set()
        cache.release_tokenizer()
        released.set()
    encode_thread, release_thread = threading.Thread(target=encode), threading.Thread(target=release)
    encode_thread.start()
    assert entered.wait(timeout=5)
    release_thread.start()
    assert release_started.wait(timeout=5) and not released.wait(timeout=.05)
    assert cache._tokenizer is not None
    finish.set()
    encode_thread.join(timeout=5)
    release_thread.join(timeout=5)
    assert not encode_thread.is_alive() and not release_thread.is_alive() and not errors
    assert released.is_set() and cache._tokenizer is None
