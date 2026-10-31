from __future__ import annotations

import io
import zipfile
from pathlib import Path

from .models import SECRETS_HOT_FILENAME
from .recorder import task_dir_for


def build_record_zip(log_dir: Path, task_id: int, *, include_secrets: bool = False) -> bytes:
    """默认排除 ``.secrets.hot.json``. ``include_secrets=True`` 时用密文配置替换 ``config.hot.json``, 并要求旁路密文文件存在."""
    root = task_dir_for(log_dir, task_id)
    if not root.is_dir() or not (root / "manifest.json").is_file():
        raise FileNotFoundError(f"record not found for task {task_id}")

    secrets_path = root / SECRETS_HOT_FILENAME
    if include_secrets and not secrets_path.is_file():
        raise PermissionError("secrets snapshot not available for this task")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            # 旁路密文不得以原文件名进入 zip; include_secrets 时改写入 config.hot.json
            if path.name == SECRETS_HOT_FILENAME:
                continue
            if include_secrets and path.name == "config.hot.json":
                zf.writestr(str(Path(f"task-{task_id}") / "config.hot.json"), secrets_path.read_bytes())
                continue
            if include_secrets and path.name == "manifest.json":
                import json

                data = json.loads(path.read_text(encoding="utf-8"))
                data["redacted"] = False
                zf.writestr(
                    str(Path(f"task-{task_id}") / "manifest.json"),
                    (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(),
                )
                continue
            zf.write(path, arcname=str(Path(f"task-{task_id}") / rel))
    return buf.getvalue()
