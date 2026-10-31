"""EventBus 进程内监听器."""

import pytest

from amane.events import Event, EventBus, EventType


@pytest.mark.asyncio
async def test_listener_receives_events_without_any_websocket_client() -> None:
    bus = EventBus()
    seen: list[Event] = []

    async def listener(event: Event) -> None:
        seen.append(event)

    bus.add_listener(listener)
    await bus.emit(EventType.TASK_COMPLETED, {"task_id": 1})

    assert [event.type for event in seen] == [EventType.TASK_COMPLETED]
    assert seen[0].data == {"task_id": 1}


@pytest.mark.asyncio
async def test_failing_listener_does_not_block_the_others() -> None:
    bus = EventBus()
    seen: list[str] = []

    async def broken(event: Event) -> None:
        raise RuntimeError("boom")

    async def healthy(event: Event) -> None:
        seen.append(str(event.type))

    bus.add_listener(broken)
    bus.add_listener(healthy)
    await bus.emit(EventType.TASK_FAILED, {"task_id": 2})

    assert seen == ["task.failed"]
