"""Emby 演员头像同步的手动入口. 周期同步由 ``EmbyActorSync`` 自行驱动."""

from fastapi import APIRouter, HTTPException

from ...emby import SyncReport, SyncRequest
from ..deps import RuntimeDep

router = APIRouter(prefix="/emby", tags=["emby"])


@router.get("/libraries")
async def list_emby_libraries(runtime: RuntimeDep) -> list[str]:
    """Emby 里的媒体库名, 供同步时选择范围."""
    if runtime.emby_sync is None:
        raise HTTPException(status_code=503, detail="同步服务未启动")
    try:
        return await runtime.emby_sync.libraries()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"无法读取 Emby 媒体库: {exc}") from exc


@router.post("/sync-actors")
async def sync_actors(runtime: RuntimeDep, req: SyncRequest | None = None) -> SyncReport:
    """立刻同步一轮并返回统计; 未启用时同样可调用, 方便填好地址后先试一次."""
    if runtime.emby_sync is None:
        raise HTTPException(status_code=503, detail="同步服务未启动")
    return await runtime.emby_sync.run_once(req)
