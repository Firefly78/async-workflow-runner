import asyncio
import json
import logging
import uuid
from asyncio import Event
from dataclasses import dataclass
from enum import Enum, auto
from time import time
from typing import Any, Callable, Coroutine, Optional, Union

from .run_wrappers import run_async

logger = logging.getLogger(__name__)


class TaskState(Enum):
    ACTIVE = auto()
    CANCELLING = auto()
    CANCELLED = auto()
    COMPLETED = auto()
    COMPLETED_WITH_ERROR = auto()


@dataclass
class WorkflowStatus:
    name: str
    identifier: str
    task: Optional[asyncio.Task]
    state: TaskState
    cancel_event: Event
    started_at: float
    additional_info: Optional[str] = None  # Error message, etc.


class WorkflowRunner:

    def __init__(
        self,
        workflows: dict[str, Callable],
        ok_to_start_cb: Callable[[str, list[str]], Coroutine[Any, Any, bool]],
    ):
        self.running_tasks: dict[str, WorkflowStatus] = {}
        self.all_workflows = workflows.copy()
        self._ok_to_start_wf = ok_to_start_cb
        self.on_wf_done = Event()

    async def cancel_workflow(self, identifier: str) -> None:
        try:
            task = self.running_tasks[identifier]
        except KeyError:
            raise ValueError("Invalid identifier")
        logger.info(f"Cancelling: 'Processing {task.name}'")
        task.state = TaskState.CANCELLING
        task.cancel_event.set()

    async def get_running_workflows(self) -> list[WorkflowStatus]:
        return list(self.running_tasks.values())

    async def get_workflow_status(self, identifier: str) -> str:
        if identifier not in self.running_tasks:
            raise ValueError("Invalid identifier")
        wf = self.running_tasks[identifier]

        if wf.state == TaskState.CANCELLING:
            return "CANCELLING"

        if wf.state == TaskState.CANCELLED:
            return "CANCELLED"

        if wf.state == TaskState.COMPLETED:
            return "COMPLETED"

        if wf.state == TaskState.COMPLETED_WITH_ERROR:
            nfo = wf.additional_info if wf.additional_info else "Unknown error"
            return f"COMPLETED_WITH_ERROR : {nfo}"

        return "ACTIVE"

    async def start_workflow(
        self,
        name: str,
        arguments_json: Union[str, dict],
    ) -> str:

        # Patch arguments_json
        if isinstance(arguments_json, str):
            arguments_json = parse_json_dict(arguments_json)

        # Check if ok to start
        if not await self._ok_to_start_wf(
            name, [x.name for x in self.running_tasks.values()]
        ):
            raise Exception("Not ok to start")

        # Start the workflow
        try:
            logger.info(f"Starting: 'Processing {name}'")

            task_uuid = str(uuid.uuid4())
            cancel_event = Event()

            status_obj = WorkflowStatus(
                state=TaskState.ACTIVE,
                task=None,
                name=name,
                identifier=task_uuid,
                cancel_event=cancel_event,
                started_at=time(),
            )
            self.running_tasks[task_uuid] = status_obj

            def on_exit(error: Optional[str] = None):
                if error is not None and not isinstance(error, str):
                    error = str(error)  # Square hole

                # Report status
                if error:
                    status_obj.state = TaskState.COMPLETED_WITH_ERROR
                    status_obj.additional_info = error
                elif cancel_event.is_set():
                    status_obj.state = TaskState.CANCELLED
                else:
                    status_obj.state = TaskState.COMPLETED

                # Clean up among tasks (remove old tasks)
                # Remove tasks > 24 hours old and not active
                t = time()
                to_be_removed = dict(
                    filter(
                        lambda x: t - x[1].started_at > 3600 * 24
                        and x[1].state != TaskState.ACTIVE,
                        self.running_tasks.items(),
                    )
                )
                for k in to_be_removed:
                    del self.running_tasks[k]  # Remove old tasks

            status_obj.task = asyncio.create_task(
                run_async(
                    self.all_workflows[name],
                    cancel_event=cancel_event,
                    on_exit=on_exit,
                    **arguments_json,
                )
            )

            return task_uuid

        except Exception:
            logger.warning(f"Failed starting: 'Processing {name}'")
            raise


def parse_json_dict(json_string: str) -> dict:
    try:
        json_string = json_string.strip()
        json_string = json_string if json_string else "{}"
        D = json.loads(json_string)  # Validate JSON
        if not isinstance(D, dict):
            raise ValueError("Invalid JSON, expected a dictionary")
        return D
    except Exception as e:
        logger.exception(e)
        raise ValueError("Invalid JSON")
