from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ActorCrawler


class ActorCrawlerRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type[ActorCrawler]] = {}

    def register(self, cls: type[ActorCrawler]) -> None:
        name = str(cls.profile().name)
        self._classes[name] = cls

    def get(self, name: str) -> type[ActorCrawler] | None:
        return self._classes.get(str(name))

    def classes(self) -> tuple[type[ActorCrawler], ...]:
        return tuple(self._classes.values())

    def sites(self) -> list[str]:
        return sorted(self._classes)


actor_registry = ActorCrawlerRegistry()
