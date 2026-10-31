"""异步任务执行器测试 (原 TaskEngine 测试)"""

from typing import TYPE_CHECKING

import pytest
from helpers import AsyncTaskRunner

from amane.db.models import TaskStatus, TaskType
from amane.handlers.protocol import TaskHandler, TaskResult

if TYPE_CHECKING:
    from amane.db.repository import Repository


class FakeHandler(TaskHandler):
    """记录调用的处理器"""

    payload_type = dict

    def __init__(self):
        super().__init__(payload_t=dict, result_t=dict)
        self.calls: list[dict] = []

    async def handle(self, payload: dict):
        self.calls.append(payload)
        return TaskResult(success=True, result={"handled": True})


class FailingHandler(TaskHandler):
    """始终失败的处理器"""

    def __init__(self):
        super().__init__(payload_t=dict, result_t=dict)

    async def handle(self, payload: dict):
        return TaskResult(success=False, error="Intentional failure")


@pytest.fixture
def runner(repo):
    """创建异步任务执行器"""
    return AsyncTaskRunner(repo)


class TestAsyncTaskRunner:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_process_one_calls_handler(self, repo: Repository, runner: AsyncTaskRunner):
        handler = FakeHandler()
        runner.register_handler(TaskType.SCRAPE, handler)

        await repo.create_task(task_type=TaskType.SCRAPE, payload={"file": "x.mp4"})
        processed = await runner.process_one()

        assert processed is True
        assert len(handler.calls) == 1
        assert handler.calls[0] == {"file": "x.mp4"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_process_one_returns_false_when_empty(self, runner: AsyncTaskRunner):
        assert await runner.process_one() is False

    @pytest.mark.asyncio(loop_scope="function")
    async def test_failed_task_increments_retries(self, repo: Repository, runner: AsyncTaskRunner):
        handler = FailingHandler()
        runner.register_handler(TaskType.SCRAPE, handler)

        task = await repo.create_task(task_type=TaskType.SCRAPE, payload={})
        await runner.process_one()

        assert task.id is not None
        updated = await repo.get_task(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.FAILED
        assert updated.retries == 1
        assert updated.error == "Intentional failure"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_completed_task_stores_result(self, repo: Repository, runner: AsyncTaskRunner):
        handler = FakeHandler()
        runner.register_handler(TaskType.SCRAPE, handler)

        task = await repo.create_task(task_type=TaskType.SCRAPE, payload={"x": 1})
        await runner.process_one()

        assert task.id is not None
        updated = await repo.get_task(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.DONE
        assert updated.result == {"handled": True}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_unregistered_handler_fails_task(self, repo: Repository, runner: AsyncTaskRunner):
        task = await repo.create_task(task_type=TaskType.SCRAPE, payload={})
        await runner.process_one()

        assert task.id is not None
        updated = await repo.get_task(task.id)
        assert updated is not None
        assert updated.status == TaskStatus.FAILED
        assert updated.error is not None
        assert "No handler" in updated.error
