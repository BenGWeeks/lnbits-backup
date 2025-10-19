from datetime import datetime
from typing import Optional, Union

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash

from .models import BackupHistory, BackupSchedule, CreateBackupScheduleData

db = Database("ext_backup")


async def create_backup_schedule(data: CreateBackupScheduleData) -> BackupSchedule:
    """Create a new backup schedule"""
    data.id = urlsafe_short_hash()

    # Convert datetime objects to timestamps (integers) for database
    start_ts: Union[datetime, int] = data.start_datetime
    if isinstance(start_ts, datetime):
        start_ts = int(start_ts.timestamp())

    next_ts: Union[datetime, int] = data.next_backup_date
    if isinstance(next_ts, datetime):
        next_ts = int(next_ts.timestamp())

    end_ts: Optional[Union[datetime, int]] = data.end_datetime
    if end_ts and isinstance(end_ts, datetime):
        end_ts = int(end_ts.timestamp())

    created_ts: Optional[Union[datetime, int]] = data.created_at
    if created_ts and isinstance(created_ts, datetime):
        created_ts = int(created_ts.timestamp())

    # Build SQL based on whether end_datetime is NULL
    if end_ts is None:
        sql = """
        INSERT INTO backup_schedules
        (id, name, wallet, backup_path, frequency_type, start_datetime,
         next_backup_date, retention_count, active, end_datetime, compress, created_at)
        VALUES (:id, :name, :wallet, :backup_path, :frequency_type, (:start_datetime),
         (:next_backup_date), :retention_count, :active, NULL, :compress, (:created_at))
        """
    else:
        sql = """
        INSERT INTO backup_schedules
        (id, name, wallet, backup_path, frequency_type, start_datetime,
         next_backup_date, retention_count, active, end_datetime, compress, created_at)
        VALUES (:id, :name, :wallet, :backup_path, :frequency_type, (:start_datetime),
         (:next_backup_date), :retention_count, :active, (:end_datetime), :compress, (:created_at))
        """

    await db.execute(
        sql,
        {
            "id": data.id,
            "name": data.name,
            "wallet": data.wallet,
            "backup_path": data.backup_path,
            "frequency_type": data.frequency_type,
            "start_datetime": start_ts,
            "next_backup_date": next_ts,
            "retention_count": data.retention_count,
            "active": data.active,
            "end_datetime": end_ts,
            "compress": data.compress,
            "created_at": created_ts or int(datetime.now().timestamp()),
        },
    )
    return BackupSchedule(**data.dict())


async def get_backup_schedule(schedule_id: str) -> Optional[BackupSchedule]:
    """Get a backup schedule by ID"""
    return await db.fetchone(
        "SELECT * FROM backup_schedules WHERE id = :id",
        {"id": schedule_id},
        BackupSchedule,
    )


async def get_backup_schedules(wallet_ids: Union[str, list[str]]) -> list[BackupSchedule]:
    """Get all backup schedules for given wallet(s)"""
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    # Build parameterized query for IN clause to prevent SQL injection
    placeholders = ",".join([f":wallet_{i}" for i in range(len(wallet_ids))])
    params = {f"wallet_{i}": wallet_id for i, wallet_id in enumerate(wallet_ids)}

    return await db.fetchall(
        f"SELECT * FROM backup_schedules WHERE wallet IN ({placeholders}) ORDER BY created_at DESC",
        params,
        BackupSchedule,
    )


async def update_backup_schedule(data: CreateBackupScheduleData) -> BackupSchedule:
    """Update an existing backup schedule"""
    start_ts: Union[datetime, int] = data.start_datetime
    if isinstance(start_ts, datetime):
        start_ts = int(start_ts.timestamp())

    next_ts: Union[datetime, int] = data.next_backup_date
    if isinstance(next_ts, datetime):
        next_ts = int(next_ts.timestamp())

    end_ts: Optional[Union[datetime, int]] = data.end_datetime
    if end_ts and isinstance(end_ts, datetime):
        end_ts = int(end_ts.timestamp())

    # Build SQL based on whether end_datetime is NULL
    if end_ts is None:
        sql = """
        UPDATE backup_schedules
        SET name = :name, wallet = :wallet, backup_path = :backup_path,
            frequency_type = :frequency_type, start_datetime = (:start_datetime),
            next_backup_date = (:next_backup_date), retention_count = :retention_count,
            active = :active, end_datetime = NULL, compress = :compress
        WHERE id = :id
        """
    else:
        sql = """
        UPDATE backup_schedules
        SET name = :name, wallet = :wallet, backup_path = :backup_path,
            frequency_type = :frequency_type, start_datetime = (:start_datetime),
            next_backup_date = (:next_backup_date), retention_count = :retention_count,
            active = :active, end_datetime = (:end_datetime), compress = :compress
        WHERE id = :id
        """

    await db.execute(
        sql,
        {
            "name": data.name,
            "wallet": data.wallet,
            "backup_path": data.backup_path,
            "frequency_type": data.frequency_type,
            "start_datetime": start_ts,
            "next_backup_date": next_ts,
            "retention_count": data.retention_count,
            "active": data.active,
            "end_datetime": end_ts,
            "compress": data.compress,
            "id": data.id,
        },
    )
    return BackupSchedule(**data.dict())


async def delete_backup_schedule(schedule_id: str) -> None:
    """Delete a backup schedule (and its history via CASCADE)"""
    await db.execute("DELETE FROM backup_schedules WHERE id = :id", {"id": schedule_id})


async def update_next_backup_date(schedule_id: str, next_backup_date) -> None:
    """Update only the next backup date for a schedule"""
    if isinstance(next_backup_date, datetime):
        next_backup_ts = int(next_backup_date.timestamp())
    else:
        next_backup_ts = next_backup_date

    await db.execute(
        """
        UPDATE backup_schedules
        SET next_backup_date = :next_backup_date
        WHERE id = :id
        """,
        {"id": schedule_id, "next_backup_date": next_backup_ts},
    )


async def deactivate_backup_schedule(schedule_id: str) -> None:
    """Deactivate a backup schedule"""
    await db.execute(
        """
        UPDATE backup_schedules
        SET active = false
        WHERE id = :id
        """,
        {"id": schedule_id},
    )


async def get_all_active_schedules() -> list[BackupSchedule]:
    """Get all active backup schedules for processing"""
    return await db.fetchall(
        "SELECT * FROM backup_schedules WHERE active = true ORDER BY next_backup_date",
        model=BackupSchedule,
    )


async def update_schedule_error(
    schedule_id: str, error_message: str, error_time: int
) -> None:
    """Store error information for a backup schedule"""
    await db.execute(
        """
        UPDATE backup_schedules
        SET last_error = :error_message,
            last_error_time = :error_time
        WHERE id = :schedule_id
        """,
        {
            "error_message": error_message,
            "error_time": error_time,
            "schedule_id": schedule_id,
        },
    )


async def update_schedule_success(
    schedule_id: str, success_time: int, backup_path: str, backup_size: int
) -> None:
    """Clear error and store success information for a backup schedule"""
    await db.execute(
        """
        UPDATE backup_schedules
        SET last_error = NULL,
            last_error_time = NULL,
            last_success_time = :success_time,
            last_backup_path = :backup_path,
            last_backup_size = :backup_size
        WHERE id = :schedule_id
        """,
        {
            "success_time": success_time,
            "backup_path": backup_path,
            "backup_size": backup_size,
            "schedule_id": schedule_id,
        },
    )


async def create_backup_history(
    schedule_id: str,
    status: str,
    file_path: Optional[str] = None,
    file_size: Optional[int] = None,
    error_message: Optional[str] = None,
) -> BackupHistory:
    """Create a backup history record"""
    history_id = urlsafe_short_hash()
    timestamp = int(datetime.now().timestamp())

    await db.execute(
        """
        INSERT INTO backup_history
        (id, schedule_id, timestamp, status, file_path, file_size, error_message)
        VALUES (:id, :schedule_id, :timestamp, :status, :file_path, :file_size, :error_message)
        """,
        {
            "id": history_id,
            "schedule_id": schedule_id,
            "timestamp": timestamp,
            "status": status,
            "file_path": file_path,
            "file_size": file_size,
            "error_message": error_message,
        },
    )

    return await db.fetchone(
        "SELECT * FROM backup_history WHERE id = :id",
        {"id": history_id},
        BackupHistory,
    )


async def get_backup_history(
    schedule_id: Optional[str] = None, limit: int = 50
) -> list[BackupHistory]:
    """Get backup history, optionally filtered by schedule_id"""
    if schedule_id:
        return await db.fetchall(
            "SELECT * FROM backup_history WHERE schedule_id = :schedule_id "
            "ORDER BY timestamp DESC LIMIT :limit",
            {"schedule_id": schedule_id, "limit": limit},
            BackupHistory,
        )
    else:
        return await db.fetchall(
            "SELECT * FROM backup_history ORDER BY timestamp DESC LIMIT :limit",
            {"limit": limit},
            BackupHistory,
        )
