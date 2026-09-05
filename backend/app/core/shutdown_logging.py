"""Keep Uvicorn shutdown cancellations out of application error tracebacks.

Cancellation still propagates to Uvicorn so it can close the connection and
clean up the request. Only the log presentation changes during shutdown.
"""

import asyncio
import logging


class ShutdownCancellationFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.shutting_down = False
        self.reported_cancellation = False

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().strip()
        if message.startswith("Started server process"):
            self.shutting_down = False
            self.reported_cancellation = False
        elif message == "Shutting down":
            self.shutting_down = True

        exc = record.exc_info[1] if record.exc_info else None
        if message != "Exception in ASGI application" or not isinstance(exc, asyncio.CancelledError):
            return True

        # Python 3.10 may cancel pending tasks while unwinding KeyboardInterrupt,
        # even when the normal shutdown log wasn't emitted.
        context = exc.__context__
        seen = set()
        interrupted = False
        while context is not None and id(context) not in seen:
            seen.add(id(context))
            if isinstance(context, KeyboardInterrupt):
                interrupted = True
                break
            context = context.__context__

        if not self.shutting_down and not interrupted:
            return True
        if self.reported_cancellation:
            return False

        self.reported_cancellation = True
        record.levelno = logging.INFO
        record.levelname = "INFO"
        record.msg = "Request aktif dibatalkan karena backend sedang berhenti."
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def install_shutdown_logging() -> None:
    logger = logging.getLogger("uvicorn.error")
    if not any(isinstance(item, ShutdownCancellationFilter) for item in logger.filters):
        logger.addFilter(ShutdownCancellationFilter())
