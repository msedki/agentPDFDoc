"""Frontières réelles YAML → API/runtime, sans modèle ni processus natif."""

import copy
import hashlib
import json

import pytest
import yaml

from services.api.errors import ApiError
from services.api.settings import Settings
from services.runtime.artifacts import ROOT
from services.runtime.profile_setup import user_profile
from services.runtime.supervisor import environment, load_profile


def delivered():
    return yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))


def written(tmp_path, profile):
    target = tmp_path / "profile.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return target


def digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("source", ["config/local16.yaml", "config/local16-4b.yaml",
                                    "RAG_Local_Agents/config/local16.yaml",
                                    "RAG_Local_Agents/config/local16-4b.yaml"])
def test_both_loaders_preserve_delivered_dictionary_and_fingerprint(source):
    path = ROOT / source
    original = yaml.safe_load(path.read_text(encoding="utf-8"))
    before = digest(original)
    for loaded in (Settings.load(path).profile, load_profile(path)):
        assert loaded == original and digest(loaded) == before


@pytest.mark.parametrize("loader", [Settings.load, load_profile], ids=["api", "runtime"])
@pytest.mark.parametrize("path,value", [
    (("unexpected",), "do-not-echo-this-value"),
    (("pdf", "max_file_mb"), 200),
    (("resources", "scheduling", "unknown"), False),
    (("llm", "output_tokens_by_mode", "comparee"), 1536),
    (("embedding", "qualification", "unknown"), True),
    (("runtime", "unknown"), "do-not-echo-this-value"),
    (("app", "port"), "8785"),
    (("app", "port"), True),
    (("app", "port"), 65536),
    (("schema_version",), True),
    (("schema_version",), 2.0),
    (("app", "offline"), 1),
    (("app", "log_document_text"), 0),
    (("embedding", "normalize_l2"), 1),
    (("llm", "max_active_generations"), True),
    (("pdf", "max_file_mib"), "0.2"),
    (("pdf", "max_file_mib"), True),
    (("pdf", "max_page_render_pixels"), 0),
    (("retrieval", "rrf_k"), -1),
    (("llm", "temperature"), float("nan")),
    (("llm", "top_p"), 1.1),
    (("resources",), []),
    (("app",), None),
    (("sqlite",), None),
    (("ui", "pdf_max_device_pixel_ratio"), float("inf")),
])
def test_invalid_keys_shapes_and_types_are_refused_before_side_effects(tmp_path, loader, path, value):
    profile = delivered()
    node = profile
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    target = written(tmp_path, profile)
    with pytest.raises((ApiError, ValueError)) as refused:
        loader(target)
    assert "do-not-echo-this-value" not in str(refused.value)
    assert list(tmp_path.iterdir()) == [target]
    if isinstance(refused.value, ApiError):
        assert refused.value.code == "invalid_profile" and refused.value.status == 400
        assert ".".join(path) in refused.value.details["keys"]


@pytest.mark.parametrize("loader", [Settings.load, load_profile], ids=["api", "runtime"])
@pytest.mark.parametrize("changes,keys", [
    ({"app": {"port": 6333}}, ["app.port", "qdrant.url"]),
    ({"chunking": {"target_tokens": 500}}, ["chunking.target_tokens", "chunking.max_prefixed_tokens"]),
    ({"chunking": {"overlap_max_tokens": 320}}, ["chunking.overlap_max_tokens", "chunking.target_tokens"]),
    ({"llm": {"num_ctx": 7000}}, ["llm.num_ctx", "retrieval.max_evidence_llm_tokens"]),
    ({"llm": {"output_tokens_by_mode": {"ordinary": 1600}}},
     ["llm.output_tokens_by_mode.ordinary", "llm.num_predict"]),
    ({"security": {"session_idle_minutes": 800}},
     ["security.session_idle_minutes", "security.session_absolute_hours"]),
    ({"security": {"launch_link_ttl_seconds": 3601}}, ["security.launch_link_ttl_seconds"]),
    ({"security": {"environment": "production"}},
     ["security.tls_cert_file", "security.tls_key_file"]),
])
def test_incompatible_consumed_values_are_refused(tmp_path, loader, changes, keys):
    profile = delivered()
    for section, values in changes.items():
        profile[section].update(values)
    with pytest.raises((ApiError, ValueError)) as refused:
        loader(written(tmp_path, profile))
    if isinstance(refused.value, ApiError):
        assert set(keys).issubset(refused.value.details["keys"])


def test_api_v1_stays_explicit_and_runtime_requires_v2(tmp_path):
    profile = {"schema_version": 1, "llm": {"base_url": "http://localhost:11434"},
               "qdrant": {"url": "http://[::1]:6333"}}
    path = written(tmp_path, profile)
    assert Settings.load(path).profile == profile
    with pytest.raises(ValueError, match="Profil version2 requis"):
        load_profile(path)


@pytest.mark.parametrize("url", ["http://user:private@127.0.0.1:6333", "http://127.0.0.1:6333/path",
                                  "http://127.0.0.1:6333?private=value", "http://127.0.0.1:6333#fragment"])
def test_api_local_service_url_does_not_accept_credentials_or_suffixes(tmp_path, url):
    profile = delivered()
    profile["qdrant"]["url"] = url
    with pytest.raises(ApiError) as refused:
        Settings.load(written(tmp_path, profile))
    assert "private" not in refused.value.message


def test_generated_user_and_restored_profiles_keep_legitimate_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("services.runtime.profile_setup.port_free", lambda port: True)
    base = delivered()
    generated = user_profile(base, tmp_path / "Donnees utilisateur", program_root=tmp_path / "Programme",
                             ports={"app": 8795, "qdrant": 6343, "ollama": 11445})
    for profile in (generated, copy.deepcopy(generated)):
        path = written(tmp_path, profile)
        assert Settings.load(path).profile == profile and load_profile(path) == profile
    assert set(generated["runtime"]) == {"host_lock_path", "backups_dir", "restore_storage_dir",
                                         "huggingface_cache_dir"}
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize("limit", [0.2, 1.5, 200])
def test_fractional_pdf_limits_and_paths_are_not_normalized(tmp_path, limit):
    profile = delivered()
    profile["pdf"]["max_file_mib"] = limit
    profile["app"]["data_dir"] = "Donnees été/../Bibliothèque"
    profile["llm"]["tokenizer_dir"] = r"D:\Modeles\Qwen"
    path = written(tmp_path, profile)
    for loaded in (Settings.load(path).profile, load_profile(path)):
        assert loaded == profile and digest(loaded) == digest(profile)
        assert type(loaded["pdf"]["max_file_mib"]) is type(limit)


@pytest.mark.parametrize("section,key", [("app", "data_dir"), ("app", "port"), ("llm", "num_ctx"),
                                          ("llm", "model"), ("llm", "tokenizer_dir"),
                                          ("embedding", "local_dir"), ("embedding", "onnx_file"),
                                          ("pdf", "artifacts_path"), ("pdf", "tessdata_dir"),
                                          ("pdf", "tesseract_cmd"), ("pdf", "ocr_languages")])
def test_runtime_requires_keys_it_indexes_and_api_retains_its_defaults(tmp_path, section, key):
    profile = delivered()
    del profile[section][key]
    path = written(tmp_path, profile)
    assert Settings.load(path).profile == profile
    with pytest.raises(ValueError) as refused:
        load_profile(path)
    assert f"{section}.{key}" in str(refused.value)


def test_runtime_requires_the_sqlite_table_indexed_by_restore(tmp_path):
    profile = delivered()
    del profile["sqlite"]
    path = written(tmp_path, profile)
    assert Settings.load(path).profile == profile
    with pytest.raises(ValueError, match="sqlite"):
        load_profile(path)


def test_pydantic_error_does_not_render_private_input_in_traceback(tmp_path):
    import traceback

    profile = delivered()
    profile["runtime"] = {"host_lock_path": ["private-path-do-not-echo"]}
    path = written(tmp_path, profile)
    for loader in (Settings.load, load_profile):
        with pytest.raises((ApiError, ValueError)) as refused:
            loader(path)
        assert "private-path-do-not-echo" not in "".join(traceback.format_exception(refused.value))


@pytest.mark.parametrize("loader", [Settings.load, load_profile], ids=["api", "runtime"])
@pytest.mark.parametrize("budgets", [None, {"factual": 384}], ids=["absent", "partial"])
def test_implicit_output_budgets_cannot_exceed_the_context_output_reservation(tmp_path, loader, budgets):
    profile = delivered()
    profile["llm"]["num_predict"] = 384
    profile["llm"]["num_ctx"] = 7040
    if budgets is None:
        profile["llm"].pop("output_tokens_by_mode")
    else:
        profile["llm"]["output_tokens_by_mode"] = budgets
    with pytest.raises((ApiError, ValueError)) as refused:
        loader(written(tmp_path, profile))
    if isinstance(refused.value, ApiError):
        assert "llm.output_tokens_by_mode.ordinary" in refused.value.details["keys"]


@pytest.mark.parametrize("limit", [0, -1, 300, 1.5])
def test_ollama_numeric_keep_alive_is_preserved_without_string_coercion(tmp_path, limit):
    profile = delivered()
    profile["llm"]["keep_alive"] = limit
    path = written(tmp_path, profile)
    for loaded in (Settings.load(path).profile, load_profile(path)):
        assert type(loaded["llm"]["keep_alive"]) is type(limit)
        assert loaded == profile


def test_keep_alive_still_refuses_boolean_and_non_finite_numbers(tmp_path):
    profile = delivered()
    for value in (False, float("inf")):
        profile["llm"]["keep_alive"] = value
        with pytest.raises(ApiError) as refused:
            Settings.load(written(tmp_path, profile))
        assert all(key.startswith("llm.keep_alive") for key in refused.value.details["keys"])


def test_api_implicit_http_port_is_compared_with_explicit_ports(tmp_path):
    profile = {"schema_version": 1, "llm": {"base_url": "http://127.0.0.1"},
               "qdrant": {"url": "http://127.0.0.1:80"}}
    with pytest.raises(ApiError) as refused:
        Settings.load(written(tmp_path, profile))
    assert set(refused.value.details["keys"]) == {"llm.base_url", "qdrant.url"}


def test_api_can_keep_one_implicit_http_port_without_a_collision(tmp_path):
    profile = {"schema_version": 1, "llm": {"base_url": "http://127.0.0.1"},
               "qdrant": {"url": "http://127.0.0.1:6333"}}
    assert Settings.load(written(tmp_path, profile)).profile == profile


@pytest.mark.parametrize("value,expected", [(1.5, "1.5s"), (1e-7, "0.0000001s"), (-1.5, "-1.5s"),
                                           (0.0, "0.0s"), (0, "0"), (-1, "-1"), ("10m", "10m")])
def test_native_keep_alive_preserves_fractional_seconds_and_profile_identity(tmp_path, value, expected):
    profile = delivered()
    profile["llm"]["keep_alive"] = value
    path = written(tmp_path, profile)
    loaded = load_profile(path)
    before = digest(loaded)
    env = environment(loaded, tmp_path, path)
    assert env["OLLAMA_KEEP_ALIVE"] == expected
    assert digest(loaded) == before and loaded == profile
