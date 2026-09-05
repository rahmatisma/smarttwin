import asyncio
import logging
import unittest

from app.core.shutdown_logging import ShutdownCancellationFilter, install_shutdown_logging


def record(message="Exception in ASGI application\n", exc=None):
    return logging.LogRecord(
        "uvicorn.error", logging.ERROR, __file__, 1, message, (),
        (type(exc), exc, exc.__traceback__) if exc is not None else None,
    )


class ShutdownLoggingTests(unittest.TestCase):
    def test_shutdown_cancellations_emit_one_info_without_traceback(self):
        handler = ShutdownCancellationFilter()
        handler.filter(record("Shutting down"))
        first = record(exc=asyncio.CancelledError())
        self.assertTrue(handler.filter(first))
        self.assertEqual(first.levelno, logging.INFO)
        self.assertIsNone(first.exc_info)
        self.assertFalse(handler.filter(record(exc=asyncio.CancelledError())))

    def test_keyboard_interrupt_context_is_recognized(self):
        exc = asyncio.CancelledError()
        exc.__context__ = KeyboardInterrupt()
        entry = record(exc=exc)
        self.assertTrue(ShutdownCancellationFilter().filter(entry))
        self.assertEqual(entry.levelno, logging.INFO)

    def test_running_server_cancellation_keeps_traceback(self):
        entry = record(exc=asyncio.CancelledError())
        self.assertTrue(ShutdownCancellationFilter().filter(entry))
        self.assertEqual(entry.levelno, logging.ERROR)
        self.assertIsNotNone(entry.exc_info)

    def test_real_errors_during_shutdown_are_preserved(self):
        handler = ShutdownCancellationFilter()
        handler.filter(record("Shutting down"))
        for exc in (RuntimeError("database failed"), OSError("disk failed")):
            entry = record(exc=exc)
            self.assertTrue(handler.filter(entry))
            self.assertEqual(entry.levelno, logging.ERROR)
            self.assertIs(entry.exc_info[1], exc)

    def test_server_restart_resets_shutdown_state(self):
        handler = ShutdownCancellationFilter()
        handler.filter(record("Shutting down"))
        handler.filter(record(exc=asyncio.CancelledError()))
        handler.filter(record("Started server process [123]"))
        entry = record(exc=asyncio.CancelledError())
        self.assertTrue(handler.filter(entry))
        self.assertEqual(entry.levelno, logging.ERROR)

    def test_install_is_idempotent(self):
        logger = logging.getLogger("uvicorn.error")
        original = logger.filters[:]
        try:
            logger.filters = []
            install_shutdown_logging()
            install_shutdown_logging()
            self.assertEqual(len(logger.filters), 1)
        finally:
            logger.filters = original


if __name__ == "__main__":
    unittest.main()
