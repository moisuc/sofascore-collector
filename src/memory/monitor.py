"""Memory monitoring with metrics collection."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable
import psutil

from src.config import settings

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """
    Monitor system and process memory usage.

    Responsibilities:
    - Check memory usage every N seconds
    - Write metrics to JSON file
    - Trigger callback when memory threshold exceeded
    - Track memory usage trends

    Usage:
        monitor = MemoryMonitor(
            check_interval=30.0,
            threshold_mb=4096,
            on_high_memory=coordinator._handle_high_memory
        )
        await monitor.start()
        # ... later ...
        await monitor.stop()
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        threshold_mb: int = 4096,
        on_high_memory: Callable[[], Awaitable[None]] | None = None
    ):
        """
        Initialize memory monitor.

        Args:
            check_interval: Seconds between memory checks
            threshold_mb: Memory threshold in MB (triggers callback)
            on_high_memory: Async callback when threshold exceeded
        """
        self.check_interval = check_interval
        self.threshold_mb = threshold_mb
        self.on_high_memory = on_high_memory

        # State tracking
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_high_memory_trigger: datetime | None = None
        self._debounce_seconds = 60  # Don't retrigger within 60s

        # Metrics
        self.metrics_file = Path(settings.memory_metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"MemoryMonitor initialized (threshold: {threshold_mb} MB, "
            f"interval: {check_interval}s)"
        )

    async def start(self) -> None:
        """Start memory monitoring."""
        if self._running:
            logger.warning("Memory monitoring already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Memory monitoring started")

    async def stop(self) -> None:
        """Stop memory monitoring."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Memory monitor task cancelled")

        logger.info("Memory monitoring stopped")

    def get_current_usage(self) -> dict:
        """
        Get current memory usage snapshot.

        Returns:
            Dictionary with memory statistics:
            - system_total_mb: Total system RAM
            - system_used_mb: Used system RAM
            - system_available_mb: Available system RAM
            - system_percent: System memory usage percentage
            - process_mb: Current process memory usage
            - threshold_exceeded: Whether threshold is exceeded
        """
        # System memory
        vm = psutil.virtual_memory()
        system_total_mb = vm.total / (1024 * 1024)
        system_used_mb = vm.used / (1024 * 1024)
        system_available_mb = vm.available / (1024 * 1024)
        system_percent = vm.percent

        # Process memory
        process = psutil.Process()
        process_mb = process.memory_info().rss / (1024 * 1024)

        # Check threshold
        threshold_exceeded = system_used_mb >= self.threshold_mb or system_percent >= 90.0

        return {
            "system_total_mb": round(system_total_mb, 2),
            "system_used_mb": round(system_used_mb, 2),
            "system_available_mb": round(system_available_mb, 2),
            "system_percent": round(system_percent, 2),
            "process_mb": round(process_mb, 2),
            "threshold_exceeded": threshold_exceeded,
        }

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Get memory stats
                usage = self.get_current_usage()

                # Write to metrics file
                await self._write_metrics(usage)

                # Check threshold and trigger callback
                if usage["threshold_exceeded"]:
                    await self._check_and_trigger_callback()

                # Log status
                logger.debug(
                    f"Memory: {usage['system_percent']}% "
                    f"({usage['system_used_mb']:.0f}/{usage['system_total_mb']:.0f} MB), "
                    f"Process: {usage['process_mb']:.0f} MB"
                )

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Memory monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in memory monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def _check_and_trigger_callback(self) -> None:
        """Check if callback should be triggered (with debouncing)."""
        if not self.on_high_memory:
            return

        now = datetime.now()

        # Debounce: don't retrigger within debounce window
        if self._last_high_memory_trigger:
            elapsed = (now - self._last_high_memory_trigger).total_seconds()
            if elapsed < self._debounce_seconds:
                logger.debug(
                    f"High memory callback debounced "
                    f"(last trigger: {elapsed:.0f}s ago)"
                )
                return

        # Trigger callback
        logger.warning("Memory threshold exceeded, triggering callback")
        self._last_high_memory_trigger = now

        try:
            await self.on_high_memory()
        except Exception as e:
            logger.error(f"Error in high memory callback: {e}", exc_info=True)

    async def _write_metrics(self, usage: dict) -> None:
        """
        Write memory metrics to JSON file.

        Appends metrics in JSON Lines format (one JSON object per line).

        Args:
            usage: Memory usage dictionary from get_current_usage()
        """
        try:
            metric = {
                "timestamp": datetime.now().isoformat(),
                **usage
            }

            # Append to file (JSON Lines format)
            with open(self.metrics_file, "a") as f:
                json.dump(metric, f)
                f.write("\n")

            logger.debug(f"Wrote metric to {self.metrics_file}")

        except Exception as e:
            logger.error(f"Error writing metrics to file: {e}", exc_info=True)
