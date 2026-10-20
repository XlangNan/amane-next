from typing import Annotated

from fastapi import Depends, HTTPException, Request

from ..agent import AgentService
from ..app.runtime import AppRuntime
from ..config import ConfigManager
from ..db.repository import Repository
from ..plugins.manager import PluginManager


def get_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def get_repository(request: Request) -> Repository:
    return request.app.state.runtime.repo


def get_config_manager(request: Request) -> ConfigManager:
    return request.app.state.runtime.config


def get_agent_service(request: Request) -> AgentService:
    service = request.app.state.runtime.agent_service
    if service is None:
        raise HTTPException(503, detail="Amane 未初始化")
    return service


def get_plugin_manager(request: Request) -> PluginManager:
    manager = request.app.state.runtime.plugin_manager
    if manager is None:
        raise HTTPException(503, detail="来源插件目录未初始化")
    return manager


ConfigDep = Annotated[ConfigManager, Depends(get_config_manager)]
RepoDep = Annotated[Repository, Depends(get_repository)]
RuntimeDep = Annotated[AppRuntime, Depends(get_runtime)]
AgentDep = Annotated[AgentService, Depends(get_agent_service)]
PluginManagerDep = Annotated[PluginManager, Depends(get_plugin_manager)]
