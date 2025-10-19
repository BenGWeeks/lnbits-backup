import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import check_and_process_backups
from .views import backup_generic_router
from .views_api import backup_api_router

logger.debug(
    "Database Backup extension loaded. "
    "This extension provides automatic scheduled database backups."
)

backup_ext: APIRouter = APIRouter(prefix="/backup", tags=["Backup"])
backup_ext.include_router(backup_generic_router)
backup_ext.include_router(backup_api_router)

backup_static_files = [
    {
        "path": "/backup/static",
        "name": "backup_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def backup_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def backup_start():
    from lnbits.tasks import create_permanent_unique_task

    # Start the backup scheduler
    scheduler_task = create_permanent_unique_task(
        "ext_backup_scheduler", check_and_process_backups
    )
    scheduled_tasks.append(scheduler_task)
    logger.info("🚀 Started database backup scheduler")


__all__ = [
    "backup_ext",
    "backup_start",
    "backup_static_files",
    "backup_stop",
    "db",
]
