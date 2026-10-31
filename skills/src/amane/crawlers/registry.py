from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Crawler


class CrawlerRegistry:
    def __init__(self):
        self._crawlers: dict[str, type[Crawler]] = {}

    def register(self, crawler_class: type[Crawler]) -> type[Crawler]:
        self._crawlers[str(crawler_class.profile().name)] = crawler_class
        return crawler_class

    def get(self, site: str) -> type[Crawler] | None:
        return self._crawlers.get(str(site))

    def sites(self):
        return (str(cls.profile().name) for cls in self._crawlers.values())


registry = CrawlerRegistry()
