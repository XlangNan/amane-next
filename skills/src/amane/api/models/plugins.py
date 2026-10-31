from pydantic import BaseModel, Field

from ...plugins.manager import PluginLoadFailure
from ...plugins.models import PluginConfig, SourceDescriptor


class PluginConfigUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, object] = Field(default_factory=dict)


class PluginResponse(BaseModel):
    descriptor: SourceDescriptor
    config: PluginConfig
    config_schema: dict[str, object]
    path: str | None = None


class PluginListResponse(BaseModel):
    items: list[PluginResponse]
    failures: list[PluginLoadFailure] = Field(default_factory=list)
