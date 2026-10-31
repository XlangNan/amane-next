from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError

from ...config import ConfigManager, PluginConfig
from ...plugins.manager import PluginManager
from ..deps import ConfigDep, PluginManagerDep, RuntimeDep
from ..models.plugins import PluginConfigUpdate, PluginListResponse, PluginResponse
from ..support.path_validation import validate_plugin_install_path

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _plugin_response(manager: PluginManager, config: PluginConfig, plugin_id: str) -> PluginResponse:
    descriptor = manager.descriptor(plugin_id)
    origin = manager.origin(plugin_id)
    if descriptor is None or manager.get(plugin_id) is None:
        raise HTTPException(status_code=404, detail="插件不存在")
    return PluginResponse(
        descriptor=descriptor,
        config=config,
        config_schema=manager.plugin_config_schema(plugin_id),
        path=origin.path if origin is not None else None,
    )


def _plugin_list(manager: PluginManager, config: ConfigManager) -> PluginListResponse:
    items = [
        _plugin_response(manager, config.hot.plugins.get(descriptor.id, PluginConfig()), descriptor.id)
        for descriptor in manager.plugin_descriptors()
    ]
    return PluginListResponse(items=items, failures=list(manager.failures))


@router.get("", response_model=PluginListResponse)
async def list_plugins(config: ConfigDep, manager: PluginManagerDep) -> PluginListResponse:
    return _plugin_list(manager, config)


@router.post("", response_model=PluginListResponse, status_code=201)
async def install_plugin(
    config: ConfigDep,
    runtime: RuntimeDep,
    file: Annotated[UploadFile | None, File(description="Zip containing plugin.py")] = None,
    path: Annotated[str | None, Form(description="Server path to a plugin directory or zip")] = None,
) -> PluginListResponse:
    filename = (file.filename or "").strip() if file is not None else ""
    source_path = path.strip() if path is not None else ""
    if bool(filename) == bool(source_path):
        raise HTTPException(status_code=422, detail="请提供 zip 文件或服务器路径（不能同时提供）")
    try:
        if source_path:
            resolved = await validate_plugin_install_path(source_path, runtime.safe_dirs)
            manager = await runtime.install_plugin_from_path(resolved)
        else:
            if file is None or not filename.lower().endswith(".zip"):
                raise HTTPException(status_code=422, detail="只接受 zip 文件")
            payload = await file.read()
            manager = await runtime.install_plugin_archive(payload)
    except HTTPException:
        raise
    except (ValueError, TypeError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _plugin_list(manager, config)


@router.post("/reload", response_model=PluginListResponse)
async def reload_plugins(config: ConfigDep, runtime: RuntimeDep) -> PluginListResponse:
    manager = await runtime.reload_plugins()
    return _plugin_list(manager, config)


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(plugin_id: str, config: ConfigDep, manager: PluginManagerDep) -> PluginResponse:
    return _plugin_response(manager, config.hot.plugins.get(plugin_id, PluginConfig()), plugin_id)


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    plugin_id: str,
    req: PluginConfigUpdate,
    config: ConfigDep,
    runtime: RuntimeDep,
    manager: PluginManagerDep,
) -> PluginResponse:
    if manager.get(plugin_id) is None:
        raise HTTPException(status_code=404, detail="插件不存在")
    current = config.hot.plugins.get(plugin_id, PluginConfig())
    merged = PluginConfig(
        enabled=current.enabled if req.enabled is None else req.enabled, config={**current.config, **req.config}
    )
    patch = {"plugins": {plugin_id: merged.model_dump(mode="json")}}
    try:
        preview = config.preview(patch)
        manager.validate_hot_settings(preview, require_available=False)
        config.update(patch)
    except (KeyError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await runtime.apply_rebuild()
    return _plugin_response(manager, config.hot.plugins[plugin_id], plugin_id)


@router.delete("/{plugin_id}", status_code=204)
async def uninstall_plugin(plugin_id: str, runtime: RuntimeDep, manager: PluginManagerDep) -> Response:
    if manager.get(plugin_id) is None:
        raise HTTPException(status_code=404, detail="插件不存在")
    try:
        await runtime.uninstall_plugin_tree(plugin_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="插件不存在") from None
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(status_code=204)
