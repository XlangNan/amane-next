"""下载并导入 r18.dev dump. ETag 持久化到 state_dir/r18_import.json, 远程未变化时跳过.
必须在 worker 中执行, 不能在 cron 循环内联 (下载体量为 GB 级).
dsn 未配置时返回失败, 不抛异常.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ..crawlers.r18dev import R18Importer, RemoteMeta
from .models import R18ImportPayload, R18ImportResult
from .protocol import TaskHandler, TaskResult

if TYPE_CHECKING:
    from ..config import R18Config
    from ..net.http import WebClient

logger = structlog.get_logger()


class R18ImportHandler(TaskHandler[R18ImportPayload, R18ImportResult]):
    def __init__(self, config: R18Config, web_client: WebClient, state_dir: Path):
        super().__init__(payload_t=R18ImportPayload, result_t=R18ImportResult)
        self._config = config
        self._web = web_client
        self._state_path = state_dir / "r18_import.json"

    def _load_meta(self) -> RemoteMeta | None:
        if not self._state_path.exists():
            return None
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return RemoteMeta(**data)
        except ValueError, TypeError, OSError:
            return None

    def _save_meta(self, meta: RemoteMeta) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(meta._asdict()), encoding="utf-8")

    async def handle(self, payload: R18ImportPayload) -> TaskResult[R18ImportResult]:
        if not self._config.enabled:
            return TaskResult(success=False, error="r18.dsn 未配置, 无法导入")

        # 远程未变化则跳过下载; force 时忽略比对.
        current = None if payload.force else self._load_meta()
        importer = R18Importer(self._config, self._web)
        success, error, meta = await importer.run(current_meta=current)

        if not success:
            return TaskResult(success=False, error=error)

        # meta is None 仅当无 download_url 且默认导入; 有 meta 才更新状态.
        imported = not (current is not None and meta is not None and meta.same_as(current))
        if meta is not None and imported:
            self._save_meta(meta)

        return TaskResult(success=True, result=R18ImportResult(imported=imported, etag=meta.etag if meta else None))
