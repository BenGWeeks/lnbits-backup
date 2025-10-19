from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from lnbits.core.models import Wallet
from lnbits.decorators import require_admin_key, require_invoice_key
from loguru import logger
from starlette.exceptions import HTTPException

from .crud import (
    create_backup_schedule,
    delete_backup_schedule,
    get_all_active_schedules,
    get_backup_history,
    get_backup_schedule,
    get_backup_schedules,
    update_backup_schedule,
)
from .models import CreateBackupScheduleData
from .tasks import execute_database_backup

backup_api_router = APIRouter()


def get_wallet_id(wallet) -> str:
    """Helper to get wallet ID from either Wallet or WalletTypeInfo object."""
    if hasattr(wallet, "id"):
        return wallet.id
    elif hasattr(wallet, "wallet") and hasattr(wallet.wallet, "id"):
        return wallet.wallet.id
    else:
        raise ValueError("Cannot extract wallet ID from provided object")


def parse_datetime_string(date_str: Optional[str]) -> Optional[datetime]:
    """Helper to parse datetime strings from various formats."""
    if not date_str or date_str.strip() == "":
        return None

    # Handle ISO format with timezone
    if "+" in date_str or date_str.endswith("Z"):
        try:
            normalized = date_str.replace("+00:00", "+0000").replace("-00:00", "-0000")
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+0000"

            try:
                dt = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S.%f%z")
                return dt
            except ValueError:
                dt = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S%z")
                return dt
        except ValueError:
            pass

    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Try parsing as timestamp
    try:
        timestamp = float(date_str)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, TypeError):
        pass

    logger.warning(f"Could not parse datetime string: {date_str}")
    return None


def validate_backup_path(backup_path: str) -> None:
    """
    Validate that the backup path is usable.
    Raises HTTPException if validation fails.
    """
    if not backup_path or not backup_path.strip():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Backup path cannot be empty",
        )

    try:
        path = Path(backup_path)

        # If path exists, verify it's a directory and writable
        if path.exists():
            if not path.is_dir():
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Backup path exists but is not a directory: {backup_path}",
                )

            # Test write permissions by attempting to create a temp file
            test_file = path / ".lnbits_backup_write_test"
            try:
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError) as e:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"No write permission for backup path: {backup_path}",
                )
        else:
            # Path doesn't exist - try to create it to verify permissions
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created backup directory: {path}")
            except (PermissionError, OSError) as e:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Cannot create backup directory (permission denied): {backup_path}",
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid backup path: {backup_path} ({str(e)})",
        )


@backup_api_router.get("/api/v1/wallet-info", status_code=HTTPStatus.OK)
async def api_wallet_info(
    wallet: Wallet = Depends(require_invoice_key),
):
    """Get basic wallet info for the current user."""
    wallet_id = get_wallet_id(wallet)

    return {
        "id": wallet_id,
        "name": (
            getattr(wallet, "name", "Wallet")
            if hasattr(wallet, "name")
            else (
                getattr(wallet.wallet, "name", "Wallet")
                if hasattr(wallet, "wallet")
                else "Wallet"
            )
        ),
        "adminkey": (
            getattr(wallet, "adminkey", "")
            if hasattr(wallet, "adminkey")
            else (
                getattr(wallet.wallet, "adminkey", "")
                if hasattr(wallet, "wallet")
                else ""
            )
        ),
    }


@backup_api_router.get("/api/v1/schedules", status_code=HTTPStatus.OK)
async def api_get_schedules(
    all_wallets: bool = Query(False),
    wallet: Wallet = Depends(require_invoice_key),
):
    """Get all backup schedules for the current wallet."""
    wallet_id = get_wallet_id(wallet)
    schedules = await get_backup_schedules(wallet_id)
    return schedules


@backup_api_router.get("/api/v1/schedules/{schedule_id}", status_code=HTTPStatus.OK)
async def api_get_schedule(
    schedule_id: str,
    wallet: Wallet = Depends(require_invoice_key),
):
    """Get a specific backup schedule."""
    schedule = await get_backup_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Backup schedule not found",
        )

    wallet_id = get_wallet_id(wallet)
    if schedule.wallet != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to access this schedule",
        )

    return schedule


@backup_api_router.post("/api/v1/schedules", status_code=HTTPStatus.CREATED)
async def api_create_schedule(
    data: CreateBackupScheduleData,
    wallet: Wallet = Depends(require_admin_key),
):
    """Create a new backup schedule."""
    wallet_id = get_wallet_id(wallet)

    # Set wallet to current user's wallet
    data.wallet = wallet_id

    # Ensure datetimes are timezone-aware (convert naive datetimes to UTC)
    if data.start_datetime.tzinfo is None:
        data.start_datetime = data.start_datetime.replace(tzinfo=timezone.utc)
    if data.next_backup_date.tzinfo is None:
        data.next_backup_date = data.next_backup_date.replace(tzinfo=timezone.utc)
    if data.end_datetime and data.end_datetime.tzinfo is None:
        data.end_datetime = data.end_datetime.replace(tzinfo=timezone.utc)

    # Validate frequency
    valid_frequencies = ["hourly", "daily", "weekly", "monthly"]
    if data.frequency_type not in valid_frequencies:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}",
        )

    # Validate backup path is writable
    validate_backup_path(data.backup_path)

    schedule = await create_backup_schedule(data)
    logger.info(f"✅ Created backup schedule: {schedule.name} (ID: {schedule.id})")
    return schedule


@backup_api_router.put("/api/v1/schedules/{schedule_id}", status_code=HTTPStatus.OK)
async def api_update_schedule(
    schedule_id: str,
    data: CreateBackupScheduleData,
    wallet: Wallet = Depends(require_admin_key),
):
    """Update a backup schedule."""
    # Get existing schedule
    schedule = await get_backup_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Backup schedule not found",
        )

    wallet_id = get_wallet_id(wallet)
    if schedule.wallet != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to update this schedule",
        )

    # Set the ID to update the correct record
    data.id = schedule_id
    data.wallet = wallet_id

    # Ensure datetimes are timezone-aware (convert naive datetimes to UTC)
    if data.start_datetime.tzinfo is None:
        data.start_datetime = data.start_datetime.replace(tzinfo=timezone.utc)
    if data.next_backup_date.tzinfo is None:
        data.next_backup_date = data.next_backup_date.replace(tzinfo=timezone.utc)
    if data.end_datetime and data.end_datetime.tzinfo is None:
        data.end_datetime = data.end_datetime.replace(tzinfo=timezone.utc)

    # Validate backup path is writable
    validate_backup_path(data.backup_path)

    updated_schedule = await update_backup_schedule(data)
    logger.info(f"✅ Updated backup schedule: {updated_schedule.name}")
    return updated_schedule


@backup_api_router.delete("/api/v1/schedules/{schedule_id}", status_code=HTTPStatus.OK)
async def api_delete_schedule(
    schedule_id: str,
    wallet: Wallet = Depends(require_admin_key),
):
    """Delete a backup schedule."""
    schedule = await get_backup_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Backup schedule not found",
        )

    wallet_id = get_wallet_id(wallet)
    if schedule.wallet != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this schedule",
        )

    await delete_backup_schedule(schedule_id)
    logger.info(f"✅ Deleted backup schedule: {schedule.name} (ID: {schedule_id})")
    return {"success": True}


@backup_api_router.post("/api/v1/backup/manual", status_code=HTTPStatus.OK)
async def api_manual_backup(
    schedule_id: str = Query(..., description="Schedule ID to execute backup for"),
    wallet: Wallet = Depends(require_admin_key),
):
    """Trigger a manual backup for a schedule."""
    schedule = await get_backup_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Backup schedule not found",
        )

    wallet_id = get_wallet_id(wallet)
    if schedule.wallet != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to execute this backup",
        )

    logger.info(f"🚀 Manual backup triggered for: {schedule.name}")
    success, file_path, file_size = await execute_database_backup(schedule)

    if success:
        return {
            "success": True,
            "file_path": file_path,
            "file_size": file_size,
            "message": f"Backup completed successfully: {file_path}",
        }
    else:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Backup execution failed",
        )


@backup_api_router.get("/api/v1/history", status_code=HTTPStatus.OK)
async def api_get_history(
    schedule_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    wallet: Wallet = Depends(require_invoice_key),
):
    """Get backup history, optionally filtered by schedule_id."""
    if schedule_id:
        # Verify user has access to this schedule
        schedule = await get_backup_schedule(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Backup schedule not found",
            )

        wallet_id = get_wallet_id(wallet)
        if schedule.wallet != wallet_id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Not authorized to access this schedule's history",
            )

    history = await get_backup_history(schedule_id=schedule_id, limit=limit)
    return history
