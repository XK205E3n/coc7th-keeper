# -*- coding: utf-8 -*-
"""LLM 输出上限（max_tokens）测试：截断检测 / reasoning_content 隐私铁律 / 房主调限端点。"""
from __future__ import annotations

import json as _json
from types import SimpleNamespace

import pytest

from server import store
from server.gm.llm import LLMClient, LLMResult


# ---------------- 工具：伪造 OpenAI 响应 ----------------

def _fake_resp(content, finish_reason, reasoning=None):
    """构造 OpenAI 兼容响应：message 可带 reasoning_content（推理模型）。"""
    msg = SimpleNamespace(content=content)
    if reasoning is not None:
        msg.reasoning_content = reasoning
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason=finish_reason)])


def _install_fake_openai(monkeypatch, resp):
    """把 openai.AsyncOpenAI 换成返回固定响应的假客户端。"""
    class _FakeCompletions:
        async def create(self, **kwargs):
            return resp

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeAsyncOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)


# ---------------- 截断检测 + reasoning_content 隐私铁律 ----------------

@pytest.mark.anyio
async def test_chat_detailed_truncation(monkeypatch):
    """finish_reason=length → truncated=True；content 为 None 时绝不返回思考内容。"""
    _install_fake_openai(monkeypatch,
                         _fake_resp(None, "length", reasoning="（思考过程，不应外泄）"))
    llm = LLMClient(api_key="sk-test", model="mimo-v2.5", max_tokens=2000)
    res = await llm.chat_detailed([{"role": "user", "content": "hi"}])
    assert res is not None
    assert res.truncated is True
    assert res.content is None
    assert res.finish_reason == "length"
    # chat() 同样只返回最终输出（None），思考内容绝不外泄
    assert await llm.chat([{"role": "user", "content": "hi"}]) is None


@pytest.mark.anyio
async def test_chat_detailed_reasoning_never_leaks(monkeypatch):
    """响应含 reasoning_content 时：只返回 content，思考内容绝不出现。"""
    _install_fake_openai(monkeypatch,
                         _fake_resp("最终答案", "stop", reasoning="机密思考过程"))
    llm = LLMClient(api_key="sk-test", model="mimo-v2.5")
    res = await llm.chat_detailed([{"role": "user", "content": "hi"}])
    assert res is not None
    assert res.content == "最终答案" and res.truncated is False
    assert "机密思考过程" not in (res.content or "")
    assert "机密思考过程" not in str(res)          # LLMResult 只含 content/truncated/finish_reason
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "最终答案"


@pytest.mark.anyio
async def test_chat_detailed_ok(monkeypatch):
    """正常完成：finish_reason=stop，content 返回，truncated=False。"""
    _install_fake_openai(monkeypatch, _fake_resp("{\"ok\": true}", "stop"))
    llm = LLMClient(api_key="sk-test", model="mimo-v2.5")
    res = await llm.chat_detailed([{"role": "user", "content": "hi"}], json_mode=True)
    assert res is not None and res.content == '{"ok": true}' and res.truncated is False


# ---------------- max_tokens 配置优先级 ----------------

def test_llm_from_config_max_tokens():
    """显式传入（每局覆盖）优先；否则用 config 的 model.max_tokens。"""
    from server import config
    cfg = config.default_config()
    cfg["model"]["max_tokens"] = 6000
    llm = LLMClient.from_config(cfg=cfg, secrets={"api_key": ""}, max_tokens=9000)
    assert llm.max_tokens == 9000
    llm2 = LLMClient.from_config(cfg=cfg, secrets={"api_key": ""})
    assert llm2.max_tokens == 6000
    llm3 = LLMClient.from_config(cfg=config.default_config(), secrets={"api_key": ""})
    assert llm3.max_tokens == 4000          # 默认值


# ---------------- 管线透传截断标志 ----------------

@pytest.mark.anyio
async def test_run_round_reports_truncated(client):
    """管线把截断标志透传（FakeLLM 用 chat_detailed 报告截断）。"""
    from server.gm.pipeline import run_round

    d = client.post("/api/games", json={"name": "截断团", "host_name": "爱丽丝"}).json()
    key = d["game_key"]
    headers = {"X-Player-Token": d["host_token"]}
    assert client.post(f"/api/games/{key}/characters",
                       json={"action": "auto", "name": "爱丽丝"},
                       headers=headers).status_code == 200
    client.post(f"/api/games/{key}/actions", json={"text": "我四处看看"}, headers=headers)

    class TruncatedLLM:
        available = True
        max_tokens = 2000

        async def chat_detailed(self, messages, **kw):
            if "裁判阶段" in messages[-1]["content"]:
                return LLMResult(_json.dumps({"dice_checks": [], "private_notes": ""}),
                                 truncated=True)
            return LLMResult(_json.dumps({"narrative": "无事发生", "state_changes": []}),
                             truncated=False)

    result = await run_round(key, llm=TruncatedLLM())
    assert result["truncated"] is True
    assert result["truncated_stage"] == "adjudicate"
    assert result["llm_max_tokens"] == 2000


# ---------------- 房主调限端点 ----------------

def test_llm_limit_endpoint(client):
    """房主可调本局上限；公共视图可见；非房主 401；越界 400。"""
    d = client.post("/api/games", json={"name": "上限团", "host_name": "房主"}).json()
    key = d["game_key"]
    host = {"X-Host-Token": d["host_token"]}
    # 房主调高
    r = client.post(f"/api/games/{key}/llm-limit", json={"max_tokens": 8000}, headers=host)
    assert r.status_code == 200 and r.json()["max_tokens"] == 8000
    # 公共视图可见（前端据此显示当前上限）
    view = client.get(f"/api/games/{key}").json()["game"]
    assert view["max_tokens"] == 8000
    # 普通玩家（非房主）→ 401
    join = client.post(f"/api/games/{key}/join", json={"name": "阿"},
                       headers={"X-Join-Token": d["invite_token"]}).json()
    p2 = {"X-Player-Token": join["player_token"]}
    assert client.post(f"/api/games/{key}/llm-limit",
                       json={"max_tokens": 8000}, headers=p2).status_code == 401
    # 越界 → 400
    assert client.post(f"/api/games/{key}/llm-limit",
                       json={"max_tokens": 500}, headers=host).status_code == 400
    assert client.post(f"/api/games/{key}/llm-limit",
                       json={"max_tokens": 99999}, headers=host).status_code == 400


def test_notify_llm_limit_persists_system_message(client):
    """截断时落 system 消息（刷新可恢复；只含提示，绝不含思考内容）。"""
    from server.api.games import _notify_llm_limit
    d = client.post("/api/games", json={"name": "通知团", "host_name": "房主"}).json()
    key = d["game_key"]
    st = store.get_store(key)
    _notify_llm_limit(st, key, {"round": 1, "llm_max_tokens": 2000})
    msgs = st.list_messages(key)
    sys_msgs = [m for m in msgs if m["kind"] == "system"]
    assert sys_msgs
    payload = sys_msgs[-1]["payload"]
    assert "2000" in payload["text"] and "建议" in payload["text"]
    assert payload["suggested"] == 4000
    assert "reasoning" not in _json.dumps(payload, ensure_ascii=False).lower()
