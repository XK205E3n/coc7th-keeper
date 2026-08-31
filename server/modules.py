# -*- coding: utf-8 -*-
"""模组数据层（M1.4）· v2 格式。

- 扫描 `modules/` 目录（环境变量 `COC_MODULES_DIR` 可覆盖）
- 读取 v2 元数据：`meta.json`（schema `trpg-module/v1`）+ `scenes.json`
- 提供：列表 / 详情 / 场景查询 / 预制角色 / 附件路径解析
- 校验清单（拆解说明 §6 的轻量实现）供测试与开发期检查

隐私边界：meta / scenes 均为表侧内容；kp-notes.md 等只按需由
AI 守密人（M2）读取，本层绝不把它们暴露给玩家视图。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from server import config

MODULE_SCHEMA = "trpg-module/v1"


def modules_dir() -> Path:
    env = os.environ.get("COC_MODULES_DIR")
    if env:
        return Path(env).resolve()
    return (config.PROJECT_ROOT / "modules").resolve()


def _module_path(module_id: str) -> Path:
    """返回模组目录；非法 id（路径穿越）直接报错。"""
    safe = Path(module_id).name
    if safe != module_id or module_id in ("", ".", ".."):
        raise ValueError(f"非法的模组标识: {module_id!r}")
    return modules_dir() / safe


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


# ---------------- 列表 / 详情 ----------------

def list_modules() -> list[dict]:
    """扫描 modules/ 下所有 v2 模组（meta.json 合法且 schema 匹配）。"""
    out = []
    base = modules_dir()
    if not base.is_dir():
        return out
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        meta = _read_json(entry / "meta.json")
        if isinstance(meta, dict) and meta.get("schema") == MODULE_SCHEMA:
            out.append(meta)
    return out


def get_module(module_id: str) -> dict | None:
    meta = _read_json(_module_path(module_id) / "meta.json")
    if not isinstance(meta, dict) or meta.get("schema") != MODULE_SCHEMA:
        return None
    return meta


# ---------------- 场景 ----------------

def get_scenes(module_id: str) -> list[dict]:
    """返回 scenes.json 中的场景列表（按 meta.scene_flow 顺序优先，否则原序）。"""
    data = _read_json(_module_path(module_id) / "scenes.json", default={})
    if not isinstance(data, dict):
        return []
    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        return []
    flow = get_scene_flow(module_id)
    if flow:
        by_id = {s.get("id"): s for s in scenes if isinstance(s, dict) and s.get("id")}
        ordered = [by_id[sid] for sid in flow if sid in by_id]
        extras = [s for s in scenes if s.get("id") not in by_id or s.get("id") not in flow]
        return ordered + extras
    return scenes


def get_scene_flow(module_id: str) -> list[str]:
    meta = get_module(module_id) or {}
    flow = meta.get("scene_flow")
    return [str(s) for s in flow] if isinstance(flow, list) else []


def get_scene(module_id: str, scene_id: str) -> dict | None:
    for s in get_scenes(module_id):
        if s.get("id") == scene_id:
            return s
    return None


def find_scene(module_id: str, ref: str) -> dict | None:
    """按场景 id 或场景名（name）查找场景；找不到返回 None（M2.6 场景切换用）。"""
    lowered = ref.strip().lower()
    if not lowered:
        return None
    for s in get_scenes(module_id):
        if str(s.get("id", "")).lower() == lowered:
            return s
    for s in get_scenes(module_id):
        if str(s.get("name", "")).strip().lower() == lowered:
            return s
    return None


# ---------------- 预制角色 / 附件 ----------------

def list_pregens(module_id: str) -> list[dict]:
    """读取 pregens/ 下的角色卡 JSON（schema coc7-character/v1）。"""
    pregens = _module_path(module_id) / "pregens"
    out = []
    if pregens.is_dir():
        for f in sorted(pregens.glob("*.json")):
            char = _read_json(f)
            if isinstance(char, dict):
                out.append(char)
    return out


def handout_path(module_id: str, rel: str) -> Path | None:
    """解析 handouts/ 下的附件相对路径；越界/缺失返回 None（防穿越）。"""
    base = (_module_path(module_id) / "handouts").resolve()
    target = (base / rel).resolve()
    if not target.is_file():
        return None
    try:
        target.relative_to(base)
    except ValueError:
        return None
    return target


def module_dir(module_id: str) -> Path:
    """返回模组目录路径（读文件用）。"""
    return _module_path(module_id)


# ---------------- 线索表（clues.md → 结构化，M7 建议：线索台账副本源） ----------------

_CLUE_RE = re.compile(
    r"(?m)^\s*[-*]\s*\[[ xX]\]\s*\*\*(C-?[A-Za-z0-9_-]+)\*\*\s*(.*?)(?=^\s*[-*]\s*\[[ xX]\]\s*\*\*C-|\Z)",
    re.S,
)


def list_clues(module_id: str) -> list[dict]:
    """解析模组 clues.md 为结构化线索清单。

    clues.md 条目形如 `- [ ] **C-01** 内容……`（[x] 表示已发现）——
    提取 `{"id", "text"}`；多行/嵌套条目并入同一条（作为线索台账的文案副本）。
    返回按出现顺序的列表；文件缺失返回 []。
    """
    path = _module_path(module_id) / "clues.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    out: list[dict] = []
    for m in _CLUE_RE.finditer(text):
        cid = m.group(1).strip()
        body = m.group(2).strip()
        if cid:
            out.append({"id": cid, "text": body})
    return out


# ---------------- 校验（拆解说明 §6 轻量版） ----------------

def validate_module(module_id: str) -> list[str]:
    """返回校验错误列表；空列表 = 通过。"""
    errors: list[str] = []
    meta = get_module(module_id)
    if meta is None:
        return [f"meta.json 缺失或 schema 不是 {MODULE_SCHEMA}"]
    for field in ("id", "number", "cn", "system", "summary", "files"):
        if field not in meta:
            errors.append(f"meta.json 缺必填字段: {field}")
    files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
    root = _module_path(module_id)
    for key, rel in files.items():
        if not (root / rel).exists():
            errors.append(f"files.{key} 声明 {rel!r} 不存在")
    scenes = _read_json(root / "scenes.json", default={})
    if not isinstance(scenes, dict) or not isinstance(scenes.get("scenes"), list):
        errors.append("scenes.json 缺失或 scenes 不是数组")
    else:
        ids = {s.get("id") for s in scenes["scenes"] if isinstance(s, dict)}
        flow = meta.get("scene_flow", [])
        for sid in flow:
            if sid not in ids:
                errors.append(f"scene_flow 中的场景 {sid!r} 在 scenes.json 中缺失")
        for s in scenes["scenes"]:
            if not isinstance(s, dict) or not s.get("id"):
                errors.append("scenes.json 存在无 id 的场景")
    return errors
