from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ...config import HotSettings, NotifyConfig
from ...events import Event, EventType
from ...notify import build_test_message, send_markdown
from ..deps import ConfigDep, PluginManagerDep, RuntimeDep

logger = structlog.get_logger()

router = APIRouter(prefix="/config", tags=["config"])


def _dingtalk_target(cfg: NotifyConfig) -> tuple[bool, str, str, str]:
    return (cfg.dingtalk_enabled, cfg.dingtalk_webhook, cfg.dingtalk_secret, cfg.dingtalk_keyword)


@router.get("")
async def get_config(config: ConfigDep) -> HotSettings:
    return config.hot


@router.patch("")
async def update_config(req: dict[str, Any], config: ConfigDep, runtime: RuntimeDep) -> HotSettings:
    """先用当前会话的插件目录校验新路由和插件配置, 再持久化."""
    changed_sections = list(req.keys())
    logger.info("config update requested", sections=changed_sections)

    notify_before = config.hot.notify.model_copy()
    emby_before = config.hot.emby.model_copy()
    try:
        preview = config.preview(req)
        if runtime.plugin_manager is not None:
            runtime.plugin_manager.validate_hot_settings(preview, require_available=False)
        config.update(req)
    except (KeyError, ValidationError, ValueError) as e:
        logger.warning("config update rejected", error=str(e), sections=changed_sections)
        raise HTTPException(status_code=422, detail=str(e)) from e

    await runtime.apply_rebuild()
    logger.info("runtime rebuilt after config update", sections=changed_sections)

    # 钉钉地址 / 密钥 / 关键词刚改过: 立刻发一条确认, 填错了当场从日志里看得出来.
    notify_after = config.hot.notify
    if (
        notify_after.dingtalk_enabled
        and notify_after.dingtalk_webhook
        and _dingtalk_target(notify_after) != _dingtalk_target(notify_before)
    ):
        title, text = build_test_message(notify_after.dingtalk_keyword)
        failure = await send_markdown(runtime.web_client, notify_after, title, text)
        if failure is None:
            logger.info("dingtalk confirmation sent")
        else:
            logger.warning("dingtalk confirmation failed", error=failure)

    # Emby 刚启用或地址 / 密钥改过: 立刻在后台同步一轮, 不必等下一个周期.
    emby_after = config.hot.emby
    if (
        emby_after.enabled
        and emby_after.url
        and emby_after.api_key
        and (emby_after.enabled, emby_after.url, emby_after.api_key)
        != (emby_before.enabled, emby_before.url, emby_before.api_key)
        and runtime.emby_sync is not None
    ):
        runtime.emby_sync.trigger()

    await runtime.event_bus.broadcast(Event(type=EventType.LOG, data={"type": "config.updated"}))

    return config.hot


@router.get("/schema")
async def get_config_schema(plugin_manager: PluginManagerDep) -> dict:
    return plugin_manager.augment_config_schema(HotSettings.model_json_schema())
