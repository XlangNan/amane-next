import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from .args import build_args
from .binary import ensure_binary
from .tool import get_preset_meta

if TYPE_CHECKING:
    from ..config import SrConfig

logger = structlog.get_logger()


@dataclass
class SrResult:
    success: bool
    output: Path | None = None
    error: str | None = None
    duration_ms: float = 0
    input_size: int = 0
    output_size: int = 0
    stdout: str = ""
    stderr: str = ""


async def run_SR(input: Path, output: Path, config: SrConfig, data_dir: Path, *, timeout: float = 600) -> SrResult:
    """不抛异常; 失败时 SrResult.success 为 False."""
    started = time.monotonic()
    pm = get_preset_meta(config.preset)
    tool = pm.tool
    log = logger.bind(preset=config.preset, tool=tool, input=str(input), output=str(output))

    input_size = input.stat().st_size if input.is_file() else 0

    try:
        # 确保二进制可用
        binary_path = await ensure_binary(tool, data_dir)
        log.debug("sr binary ready", path=str(binary_path))

        # 生成参数
        args = build_args(input, output, config)
        log.debug("sr args", args=args)

        # 确保输出目录存在
        if input.is_file():
            output.parent.mkdir(parents=True, exist_ok=True)
        else:
            output.mkdir(parents=True, exist_ok=True)

        # realesrgan 从 CWD 解析模型路径
        log.info("sr process starting")
        proc = await asyncio.create_subprocess_exec(
            binary_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=binary_path.parent,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            duration = (time.monotonic() - started) * 1000
            log.error("sr process timeout", timeout=timeout)
            return SrResult(False, error=f"进程超时 ({timeout=}s)", duration_ms=duration)

        duration = (time.monotonic() - started) * 1000
        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")

        if proc.returncode != 0:
            log.error("sr process failed", returncode=proc.returncode, stderr=stderr)
            return SrResult(
                False,
                error=f"非零返回值 {proc.returncode}: {stderr[:200]}",
                duration_ms=duration,
                stdout=stdout,
                stderr=stderr,
            )

        # 校验输出
        output_size = output.stat().st_size if output.is_file() else 0
        if output.is_file() or (output.is_dir() and any(output.iterdir())):
            if input_size and output_size:
                log.info(
                    "sr completed",
                    input_size=_fmt_size(input_size),
                    output_size=_fmt_size(output_size),
                    ratio=f"{output_size / input_size:.1f}x",
                    duration_ms=round(duration),
                )
            else:
                log.info("sr completed", duration_ms=round(duration))
            return SrResult(
                True, output, duration_ms=duration, input_size=input_size, output_size=output_size, stdout=stdout
            )
        return SrResult(False, error="进程正常退出但无输出文件", duration_ms=duration, stdout=stdout, stderr=stderr)

    except ValueError as e:
        duration = (time.monotonic() - started) * 1000
        log.error("sr config error", error=str(e))
        return SrResult(False, error=str(e), duration_ms=duration)

    except FileNotFoundError as e:
        duration = (time.monotonic() - started) * 1000
        log.error("sr binary not found", error=str(e))
        return SrResult(False, error=f"二进制不存在: {e}", duration_ms=duration)

    except OSError as e:
        duration = (time.monotonic() - started) * 1000
        log.error("sr io error", error=str(e))
        return SrResult(False, error=str(e), duration_ms=duration)

    except Exception as e:
        duration = (time.monotonic() - started) * 1000
        log.error("sr unexpected error", error=str(e), exc_info=True)
        return SrResult(False, error=str(e), duration_ms=duration)


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n}{unit}"
        n //= 1024
    return f"{n}GB"
