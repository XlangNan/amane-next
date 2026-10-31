from datetime import datetime
from typing import Unpack

from sqlmodel import select

from ..models import RoutineType, Schedule
from ..repo_types import ScheduleUpdates
from .base import RepositoryMixinBase


class SchedulesRepoMixin(RepositoryMixinBase):
    async def list_schedules(self) -> list[Schedule]:
        async with self._session() as session:
            stmt = select(Schedule)
            result = await session.exec(stmt)
            return list(result.all())

    async def get_schedule(self, schedule_id: int) -> Schedule | None:
        async with self._session() as session:
            return await session.get(Schedule, schedule_id)

    async def create_schedule(
        self,
        cron: str,
        task_type: RoutineType,
        name: str | None = None,
        payload: dict[str, object] | None = None,
        enabled: bool = True,
        next_run: datetime | None = None,
    ) -> Schedule:
        async with self._session() as session:
            schedule = Schedule(
                name=name,
                cron=cron,
                task_type=task_type,
                payload=payload or {},
                enabled=enabled,
                next_run=next_run,
            )
            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)
            return schedule

    async def update_schedule(self, schedule_id: int, **updates: Unpack[ScheduleUpdates]) -> Schedule | None:
        async with self._session() as session:
            schedule = await session.get(Schedule, schedule_id)
            if schedule is None:
                return None
            # 显式赋值, 禁止 setattr; 字段集由 ScheduleUpdates 与 Schedule 静态对齐.
            if "name" in updates:
                schedule.name = updates["name"]
            if "cron" in updates:
                schedule.cron = updates["cron"]
            if "task_type" in updates:
                schedule.task_type = updates["task_type"]
            if "payload" in updates:
                schedule.payload = updates["payload"]
            if "enabled" in updates:
                schedule.enabled = updates["enabled"]
            if "last_run" in updates:
                schedule.last_run = updates["last_run"]
            if "next_run" in updates:
                schedule.next_run = updates["next_run"]
            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)
            return schedule

    async def delete_schedule(self, schedule_id: int) -> bool:
        async with self._session() as session:
            schedule = await session.get(Schedule, schedule_id)
            if schedule is None:
                return False
            await session.delete(schedule)
            await session.commit()
            return True
