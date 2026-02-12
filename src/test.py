from httpx import get
from core.di.utils import get_beans_by_type, get_bean_by_type
from core.interface.controller.base_controller import BaseController

from core.observation.logger import get_logger


logger = get_logger(__name__)


def register_controllers():
    """
    Register all controllers to the FastAPI application.

    Args:
        fastapi_app (FastAPI): FastAPI application instance
    """
    all_controllers = get_beans_by_type(BaseController)
    logger.info(
        "Controller registration completed, %d controllers registered",
        len(all_controllers),
    )


if __name__ == "__main__":
    register_controllers()