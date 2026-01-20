"""Example demonstrating multiple TaskManagers running concurrently.

This example shows how multiple managers can each handle their own set of tasks,
all intermixed in the same event loop.
"""

import asyncio
import time
from concurrency import TaskManager


async def fetch_data(source: str, item_id: int, delay: float = 0.5) -> dict:
    """Simulate fetching data from a source with a delay."""
    await asyncio.sleep(delay)
    return {
        "source": source,
        "item_id": item_id,
        "timestamp": time.time(),
    }


async def process_data(data_type: str, item_id: int, delay: float = 0.3) -> dict:
    """Simulate processing data with a delay."""
    await asyncio.sleep(delay)
    return {
        "type": data_type,
        "item_id": item_id,
        "processed": True,
        "timestamp": time.time(),
    }


async def main():
    """Demonstrate multiple managers running concurrently."""
    print("Starting multiple TaskManagers concurrently...\n")

    # Create multiple managers with different concurrency limits and purposes
    fetch_manager = TaskManager(max_concurrent=5)
    process_manager = TaskManager(max_concurrent=10)
    validate_manager = TaskManager(max_concurrent=3)

    # Add fetch tasks to the first manager
    print("Adding 20 fetch tasks to fetch_manager (max_concurrent=5)")
    for i in range(20):
        fetch_manager.add_task(fetch_data("database", i, delay=0.2))

    # Add process tasks to the second manager
    print("Adding 15 process tasks to process_manager (max_concurrent=10)")
    for i in range(15):
        process_manager.add_task(process_data("analytics", i, delay=0.3))

    # Add validation tasks to the third manager
    print("Adding 10 validation tasks to validate_manager (max_concurrent=3)")
    for i in range(10):
        validate_manager.add_task(fetch_data("cache", i, delay=0.15))

    print("\nRunning all three managers concurrently in the same event loop...")
    start_time = time.time()

    # Run all managers concurrently - tasks from all managers will be intermixed
    fetch_results, process_results, validate_results = await asyncio.gather(
        fetch_manager.run_async(),
        process_manager.run_async(),
        validate_manager.run_async()
    )

    end_time = time.time()
    elapsed = end_time - start_time

    print(f"\nAll tasks completed in {elapsed:.2f} seconds")

    # Display results summary
    print(f"\nResults Summary:")
    print(f"  Fetch Manager: {sum(1 for r in fetch_results if r.success)}/{len(fetch_results)} successful")
    print(f"  Process Manager: {sum(1 for r in process_results if r.success)}/{len(process_results)} successful")
    print(f"  Validate Manager: {sum(1 for r in validate_results if r.success)}/{len(validate_results)} successful")

    # Show some sample results
    print(f"\nSample fetch results:")
    for i, result in enumerate(fetch_results[:3]):
        if result.success:
            print(f"  {i}: {result.value}")

    print(f"\nSample process results:")
    for i, result in enumerate(process_results[:3]):
        if result.success:
            print(f"  {i}: {result.value}")

    # Calculate theoretical vs actual time
    # If run sequentially:
    theoretical_sequential = (20 * 0.2) + (15 * 0.3) + (10 * 0.15)
    print(f"\nPerformance comparison:")
    print(f"  Sequential execution would take: ~{theoretical_sequential:.2f}s")
    print(f"  Concurrent execution took: {elapsed:.2f}s")
    print(f"  Speedup: {theoretical_sequential/elapsed:.2f}x")


async def demonstrate_isolation():
    """Demonstrate that each manager maintains its own concurrency limit."""
    print("\n" + "="*70)
    print("Demonstrating Manager Isolation")
    print("="*70 + "\n")

    async def long_task(name: str, duration: float):
        """A task that takes a specified amount of time."""
        print(f"  [{name}] Starting at {time.time():.2f}")
        await asyncio.sleep(duration)
        print(f"  [{name}] Completed at {time.time():.2f}")
        return name

    # Manager 1: Only allows 2 concurrent tasks
    manager1 = TaskManager(max_concurrent=2)
    print("Manager 1 (max_concurrent=2): Adding 4 tasks")
    for i in range(4):
        manager1.add_task(long_task(f"M1-Task{i+1}", 1.0))

    # Manager 2: Allows 4 concurrent tasks
    manager2 = TaskManager(max_concurrent=4)
    print("Manager 2 (max_concurrent=4): Adding 4 tasks")
    for i in range(4):
        manager2.add_task(long_task(f"M2-Task{i+1}", 1.0))

    print("\nStarting both managers concurrently...")
    print("Note: M1 tasks will run in batches of 2, M2 tasks all at once\n")

    start = time.time()
    results1, results2 = await asyncio.gather(
        manager1.run_async(),
        manager2.run_async()
    )
    duration = time.time() - start

    print(f"\nBoth managers completed in {duration:.2f}s")
    print(f"Manager 1 tasks: {[r.value for r in results1 if r.success]}")
    print(f"Manager 2 tasks: {[r.value for r in results2 if r.success]}")


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())

    # Run the isolation demonstration
    asyncio.run(demonstrate_isolation())
