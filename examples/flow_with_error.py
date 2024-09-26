import asyncio

from aworkflow import WorkflowRunner


async def my_flow(*args, **kwargs):
    print("Starting my_flow")
    await asyncio.sleep(2)
    print("Ending my_flow")
    raise ValueError("Ooops")


# Always ok to start a new workflow, if there is no other running
async def ok_to_start(name: str, running: list[str]) -> bool:
    if len(running) > 0:
        raise ValueError("Another task is already running")
    return True  # Ok to start


async def main():
    # Create a runner with a single workflow
    runner = WorkflowRunner({"my_flow": my_flow}, ok_to_start_cb=ok_to_start)

    # Start a workflow
    identifier = await runner.start_task("my_flow", "{}")
    while True:
        # Check the status of the workflow
        await asyncio.sleep(0.5)
        C = await runner.get_task_status(identifier)

        # If the workflow is completed, print the status and break the loop
        if C != "ACTIVE":
            print(f"Workflow ended with status: {C}")
            break


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
