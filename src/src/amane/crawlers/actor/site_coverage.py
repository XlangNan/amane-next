"""读各爬虫 ``profile().genders``, 不另维护名单."""

from __future__ import annotations

from ...enums import ActorGender, SiteName
from .registry import actor_registry


def site_allows_actor_gender(site: SiteName, gender: ActorGender) -> bool:
    """unknown 仅允许同时覆盖 female 与 male 的站, 避免误请求女-only 站."""
    cls = actor_registry.get(site)
    if cls is None:
        return False
    supported = cls.profile().genders
    if not supported:
        return False
    if gender == ActorGender.UNKNOWN:
        return ActorGender.FEMALE in supported and ActorGender.MALE in supported
    return gender in supported


def filter_sites_for_gender(sites: list[SiteName], gender: ActorGender) -> tuple[list[SiteName], list[SiteName]]:
    allowed: list[SiteName] = []
    skipped: list[SiteName] = []
    for site in sites:
        if site_allows_actor_gender(site, gender):
            allowed.append(site)
        else:
            skipped.append(site)
    return allowed, skipped
