# -*- coding: utf-8 -*-
"""模组 API（M1.4）：/api/modules。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from server import modules as m

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("")
def list_modules() -> dict:
    """模组列表（v2 元数据）。"""
    return {"modules": m.list_modules(), "count": len(m.list_modules())}


@router.get("/{module_id}")
def get_module(module_id: str) -> dict:
    meta = m.get_module(module_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"模组 {module_id} 不存在")
    return {"module": meta}


@router.get("/{module_id}/scenes")
def get_scenes(module_id: str) -> dict:
    if m.get_module(module_id) is None:
        raise HTTPException(status_code=404, detail=f"模组 {module_id} 不存在")
    return {"module_id": module_id, "scene_flow": m.get_scene_flow(module_id),
            "scenes": m.get_scenes(module_id)}


@router.get("/{module_id}/scenes/{scene_id}")
def get_scene(module_id: str, scene_id: str) -> dict:
    scene = m.get_scene(module_id, scene_id)
    if scene is None:
        raise HTTPException(status_code=404,
                            detail=f"模组 {module_id} 场景 {scene_id} 不存在")
    return {"module_id": module_id, "scene": scene}


@router.get("/{module_id}/pregens")
def get_pregens(module_id: str) -> dict:
    if m.get_module(module_id) is None:
        raise HTTPException(status_code=404, detail=f"模组 {module_id} 不存在")
    return {"module_id": module_id, "pregens": m.list_pregens(module_id)}


@router.get("/{module_id}/handouts/{file_path:path}")
def get_handout(module_id: str, file_path: str) -> FileResponse:
    """附件图片服务（M4）：/api/modules/{id}/handouts/{相对路径}。"""
    p = m.handout_path(module_id, file_path)
    if p is None:
        raise HTTPException(status_code=404, detail=f"附件不存在: {file_path}")
    return FileResponse(str(p))
