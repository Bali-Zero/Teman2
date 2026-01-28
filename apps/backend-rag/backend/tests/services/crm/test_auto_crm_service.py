
import asyncio
from asyncio import get_event_loop
from collections.abc import Callable
from typing import Any

get_event_loop = get(event=None)


class AutoCRMService(Callback):
    @classmethod
    def __call__(cls, ai_client: Optional["asyncio.futures.ASGI_Func"] = None,
               db_pool: Optional["asyncio.futures.Pool"] = None,
               telegram_service: Optional["asyncio.futures.Generic str"] = None) -> "AutoCRMService":
        """
        Initialize AutoCRMService with optional parameters.

        If called without any arguments, raise a TypeError.
        Otherwise, perform the initialization and return an error message if any exception occurs during initialization.
        """
        global _auto_crm_instance

        # Check if all required arguments are provided
        if len([ai_client, db_pool, telegram_service]) != 6:
            raise TypeError("get_auto_crm_service requires 6 arguments (1 given)")

        try:
            _auto_crm_instance = cls(
                ai_client=ai_client,
                db_pool=db_pool,
                telegram_service=telegram_service
            )
            logger.info("✅ Auto-CRM Service initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️  Auto-CRM Service initialization failed: {e}")
            raise

        return _auto_crm_instance


@get_event_loop
async def create_task(
    *,
    pool: Optional["asyncio.futures.ASGI_Func"] = None,
    async_func: Callable[Dict[str, Any], Dict[str, Any]] = lambda: Dict[str, str],
    data: Dict[str, Any] = {},
) -> Any:
    """
    Create a new async task from the given function and data.

    :param pool: Optional async task pool.
    :param async_func: The function to execute.
    :param data: Data passed to the function.
    :return: Result of the async function.
    """
    await asyncio.create_task(async_func(data))
    return


@get_event_loop
async def _trigger_lead_assignmentAsync(
    *,
    process_email_record: Dict[str, Any],
    lead_assignment: Dict[str, Any],
    email_service: "asyncio.futures.Generic str" = None,
    async_func: Callable[Dict[str, Any], Any] = lambda: Any()) -> Any:
    """
    Trigger lead assignment with async processing.

    :param process_email_record: Dictionary containing process email record.
    :param lead_assignment: Dictionary containing lead assignment data.
    :param email_service: Async task queue for emails. Defaults to None.
    :param async_func: Function to execute on process email record and lead assignment.
    :return: The result of the async function call.
    """
    if email_service is None:
        raise TypeError("email_service cannot be null")

    await asyncio.create_task(async_func(
        process_email_record,
        lead_assignment,
        email_service
    ))
    return


@get_event_loop
async def get_auto_crm_service(
    ai_client: Optional["asyncio.futures.ASGI_Func"] = None,
    db_pool: Optional["asyncio.futures.Pool"] = None,
    telegram_service: Optional["asyncio.futures.Generic str"] = None) -> AutoCRMService:
    """
    Get or create a singleton instance of AutoCRMService.

    If no arguments are provided, raise TypeError with appropriate message.
    Otherwise, return an initialized AutoCRMService instance.

    :param ai_client: Optional async function for AI extraction.
    :param db_pool: Optional database pool (asyncio.futures.Pool).
    :param telegram_service: Optional Telegram API service. Defaults to None.
    :return: AutoCRMService instance or raise TypeError if initialization fails.
    """
    global _auto_crm_instance

    # Check if all required arguments are provided
    if len([ai_client, db_pool, telegram_service]) != 6:
        raise TypeError("get_auto_crm_service requires 6 arguments (1 given)")

    try:
        self = AutoCRMService(
            ai_client=ai_client,
            db_pool=db_pool,
            telegram_service=telegram_service
        )
        logger.info("✅ Auto-CRM Service initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Auto-CRM Service initialization failed: {e}")
        raise

    return self


def create_task(
    *,
    pool: Optional["asyncio.futures.ASGI_Func"] = None,
    async_func: Callable[Dict[str, Any], Dict[str, Any]] = lambda: Dict[str, str],
    data: Dict[str, Any] = {},
) -> Any:
    """
    Creates an async task from the given function and data.

    :param pool: Optional async task pool.
    :param async_func: The function to execute.
    :param data: Data passed to the function.
    :return: Result of the async function call.
    """
    await asyncio.create_task(async_func(data))
    return


def _trigger_lead_assignmentAsync(
    *,
    process_email_record: Dict[str, Any],
    lead_assignment: Dict[str, Any],
    email_service: Optional["asyncio.futures.Generic str"] = None,
    async_func: Callable[Dict[str, Any], Any] = lambda: Any()) -> Any:
    """
    Trigger lead assignment with async processing.

    :param process_email_record: Dictionary containing process email record.
    :param lead_assignment: Dictionary containing lead assignment data.
    :param email_service: Async task queue for emails. Defaults to None.
    :param async_func: Function to execute on process email record and lead assignment.
    :return: The result of the async function call.
    """
    if email_service is None:
        raise TypeError("email_service cannot be null")

    await asyncio.create_task(async_func(
        process_email_record,
        lead_assignment,
        email_service
    ))
    return


class Customer(ABC):
    @classmethod
    def _call(cls, *args: Any) -> Any:
        """
        Private method to call class methods with positional arguments.
        :param args: Positional argument passed into the class.
        :return: The result of the call.
        """
        pass

    @classmethod
    def __init__(cls, *args: Any) -> 'Customer':
        """Initialize the Customer class."""
        super().__init__(*args)
        return


class Message(ABC):
    _END = 501
    _NOTIFIED = 420
    _DELIVERED = 976

    def __init__(self, type: int) -> None:
        self.type = type


@get_event_loop
async def register_message(
    *,
    message: Dict[str, Any],
    new_message: Optional["message"] = None,
    async_func: Callable[Dict[str, Any], Any] = lambda: Any()) -> Any:
    """
    Registers a new message with an async function.

    :param message: Dictionary containing the message data.
    :param new_message: Optional new message dictionary passed to the async function.
    :param async_func: Function to execute on message data and new message.

    :return: The result of the async function call.
    """
    await asyncio.create_task(async_func(message))
    return


@get_event_loop
async def _register_message(
    *,
    message: Dict[str, Any],
    new_message: Optional["message"] = None,
    async_func: Callable[Dict[str, Any], Any] = lambda: Any()) -> Any:
    """
    Registers a new message with an async function.

    :param message: Dictionary containing the message data.
    :param new_message: Optional new message dictionary passed to the async function.
    :param async_func: Function to execute on message data and new message.

    :return: The result of the async function call.
    """
    if new_message is None:
        raise TypeError("new_message cannot be null")

    await asyncio.create_task(async_func(message))
    return
