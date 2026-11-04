"""首页仪表盘: 一次请求取回各项总数与最近任务. 最近更新的影片走既有的 ``GET /metadata``."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ...db.models import TaskStatus
from ..deps import ConfigDep, RepoDep, RuntimeDep

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RECENT_TASKS = 8


class DashboardTask(BaseModel):
    id: int
    type: str
    status: TaskStatus
    label: str | None = None
    """任务相关的番号 (有则显示)."""
    error: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class DashboardResponse(BaseModel):
    metadata: int
    actors: int
    media_files: int
    libraries: int
    untranslated: int
    """标题或简介里仍含日文假名的影片数; 翻译未启用时仍会统计."""
    translate_enabled: bool
    worker_paused: bool
    tasks_queued: int
    tasks_running: int
    tasks_done: int
    tasks_failed: int
    recent_tasks: list[DashboardTask]


@router.get("")
async def get_dashboard(repo: RepoDep, runtime: RuntimeDep, config: ConfigDep) -> DashboardResponse:
    counts = await repo.dashboard_counts()
    tasks = await repo.list_tasks(limit=_RECENT_TASKS)
    by_status = counts.tasks_by_status
    return DashboardResponse(
        metadata=counts.metadata,
        actors=counts.actors,
        media_files=counts.media_files,
        libraries=counts.libraries,
        untranslated=counts.untranslated,
        translate_enabled=config.hot.translate.enabled,
        worker_paused=runtime.worker.is_paused,
        tasks_queued=by_status.get(TaskStatus.QUEUED, 0),
        tasks_running=by_status.get(TaskStatus.RUNNING, 0),
        tasks_done=by_status.get(TaskStatus.DONE, 0),
        tasks_failed=by_status.get(TaskStatus.FAILED, 0),
        recent_tasks=[
            DashboardTask(
                id=task.id,
                type=str(task.type),
                status=task.status,
                label=_label(task.payload),
                error=task.error,
                created_at=_utc(task.created_at),
                finished_at=_utc(task.finished_at),
            )
            for task in tasks
            if task.id is not None
        ],
    )


def _label(payload: dict[str, object]) -> str | None:
    number = payload.get("number")
    return number if isinstance(number, str) and number else None


def _utc(value: datetime | None) -> datetime | None:
    """SQLite 读回的时间不带时区, 补上 UTC 前端才不会按本地时间误读."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
