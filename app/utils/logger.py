import datetime
import logging
import sys

SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


class SimpleFormatter(logging.Formatter):
    """Custom formatter that adds timestamp and level name to log messages."""
    
    def format(self, record):
        """
        Format the log record with timestamp and level name.
        
        Args:
            record: Log record to format
            
        Returns:
            str: Formatted log message
        """
        timestamp = datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S")
        record.levelname = f"[{timestamp}] - [{record.levelname}]: "
        return super().format(record)


class CustomLogger(logging.Logger):
    """Custom logger class that adds a success log level."""
    
    def success(self, msg, *args, **kwargs):
        """
        Log a message with SUCCESS level.
        
        Args:
            msg: Message to log
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        self.isEnabledFor(SUCCESS_LEVEL) and self._log(SUCCESS_LEVEL, msg, args, **kwargs)


logging.setLoggerClass(CustomLogger)
logger = logging.getLogger("gifts_buyer")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(SimpleFormatter('%(levelname)s %(message)s'))
logger.addHandler(handler)


class LoggerInterface:
    """Interface for logging messages with different severity levels."""

    @staticmethod
    def info(message: str) -> None:
        """
        Log an info message.
        
        Args:
            message (str): Message to log
        """
        print("\r", end="")
        logger.info(message)

    @staticmethod
    def warn(message: str) -> None:
        """
        Log a warning message.
        
        Args:
            message (str): Message to log
        """
        print("\r", end="")
        logger.warning(message)

    @staticmethod
    def error(message: str) -> None:
        """
        Log an error message.
        
        Args:
            message (str): Message to log
        """
        print("\r", end="")
        logger.error(message)

    @staticmethod
    def success(message: str) -> None:
        """
        Log a success message.
        
        Args:
            message (str): Message to log
        """
        print("\r", end="")
        logger.success(message) if isinstance(logger, CustomLogger) else logger.info(f"[SUCCESS] {message}")

    @staticmethod
    def log_same_line(message: str, level: str = "INFO") -> None:
        """
        Log a message on the same line, overwriting the previous message.
        
        Args:
            message (str): Message to log
            level (str, optional): Log level. Defaults to "INFO"
        """
        timestamp = datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S")
        print(f"\r[{timestamp}] - [{level.upper()}]: {message}", end="", flush=True)


info = LoggerInterface.info
warn = LoggerInterface.warn
error = LoggerInterface.error
success = LoggerInterface.success
log_same_line = LoggerInterface.log_same_line
