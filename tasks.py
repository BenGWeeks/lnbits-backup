import asyncio
import gzip
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]
from loguru import logger

from .crud import (
    create_backup_history,
    deactivate_backup_schedule,
    get_all_active_schedules,
    update_next_backup_date,
    update_schedule_error,
    update_schedule_success,
)
from .models import BackupSchedule


async def execute_database_backup(schedule: BackupSchedule) -> tuple[bool, str, int]:
    """
    Execute database backup for a schedule.
    Returns (success, file_path, file_size) tuple.
    """
    try:
        # Import settings to determine database type
        from lnbits.settings import settings

        # Generate timestamped filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"lnbits_backup_{timestamp}"

        # Create backup directory if it doesn't exist
        backup_dir = Path(schedule.backup_path)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Determine database type from settings
        db_url = settings.lnbits_database_url or ""

        if "postgres" in db_url.lower():
            # PostgreSQL backup using pg_dump
            logger.info("📦 Performing PostgreSQL backup...")
            backup_file = backup_dir / f"{backup_filename}.sql"

            # Parse connection string for pg_dump
            # Format: postgresql://user:password@host:port/dbname
            try:
                # Use pg_dump command
                result = subprocess.run(
                    ["pg_dump", "--no-owner", "--no-acl", "-f", str(backup_file), db_url],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                logger.info(f"✅ PostgreSQL backup created: {backup_file}")

            except subprocess.CalledProcessError as e:
                error_msg = f"pg_dump failed: {e.stderr}"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            except FileNotFoundError:
                error_msg = "pg_dump not found. Please install PostgreSQL client tools."
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

        else:
            # SQLite backup using file copy with WAL checkpoint
            logger.info("📦 Performing SQLite backup...")

            # Find the database file
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
            elif db_url.startswith("sqlite://"):
                db_path = db_url.replace("sqlite://", "")
            else:
                # Default location
                db_path = "data/database.sqlite3"

            source_db = Path(db_path)
            if not source_db.exists():
                raise Exception(f"Database file not found: {source_db}")

            backup_file = backup_dir / f"{backup_filename}.sqlite3"

            # Use SQLite VACUUM INTO for safe backup (requires SQLite 3.27+)
            try:
                import sqlite3

                conn = sqlite3.connect(str(source_db))
                conn.execute("VACUUM")  # Optimize first
                conn.execute(f"VACUUM INTO '{backup_file}'")
                conn.close()
                logger.info(f"✅ SQLite backup created: {backup_file}")

            except Exception as e:
                logger.warning(f"⚠️ VACUUM INTO failed: {e}, trying file copy...")
                # Fallback to file copy
                shutil.copy2(source_db, backup_file)
                logger.info(f"✅ SQLite backup created (file copy): {backup_file}")

        # Compress if enabled
        if schedule.compress:
            logger.info("🗜️ Compressing backup...")
            compressed_file = Path(str(backup_file) + ".gz")

            with open(backup_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove uncompressed file
            backup_file.unlink()
            backup_file = compressed_file
            logger.info(f"✅ Compressed backup: {backup_file}")

        # Get file size
        file_size = backup_file.stat().st_size

        # Clean up old backups (retention policy)
        await cleanup_old_backups(schedule, backup_dir)

        logger.info(
            f"✅ Backup successful: {backup_file} ({file_size / 1024 / 1024:.2f} MB)"
        )
        return True, str(backup_file), file_size

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error executing backup for schedule {schedule.name}: {error_msg}")
        return False, "", 0


async def cleanup_old_backups(schedule: BackupSchedule, backup_dir: Path) -> None:
    """Remove old backups based on retention policy"""
    try:
        # Get all backup files (both .sql/.sqlite3 and .gz versions)
        extensions = [".sql", ".sql.gz", ".sqlite3", ".sqlite3.gz"]
        all_backups = []

        for ext in extensions:
            all_backups.extend(backup_dir.glob(f"lnbits_backup_*{ext}"))

        # Sort by modification time (newest first)
        all_backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Keep only retention_count backups, delete the rest
        if len(all_backups) > schedule.retention_count:
            backups_to_delete = all_backups[schedule.retention_count :]
            for old_backup in backups_to_delete:
                logger.info(f"🗑️ Removing old backup: {old_backup}")
                old_backup.unlink()

            logger.info(
                f"✅ Cleaned up {len(backups_to_delete)} old backup(s), "
                f"keeping {schedule.retention_count}"
            )

    except Exception as e:
        logger.error(f"❌ Error cleaning up old backups: {e}")


def ensure_timezone_aware(dt):
    """Helper to ensure datetime is timezone aware"""
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def check_and_process_backups():  # noqa: C901
    """
    Background task to check and process scheduled backups.
    Runs every 60 seconds (1 minute minimum frequency).
    """
    # Keep track of already deactivated schedules
    deactivated_ids = set()

    while True:
        try:
            logger.info("🔄 Checking backup schedules...")

            # Get all active schedules
            schedules = await get_all_active_schedules()
            logger.info(f"📊 Found {len(schedules)} active backup schedule(s)")
            current_time = datetime.now(timezone.utc)

            # Process each schedule
            for schedule in schedules:
                try:
                    logger.debug(
                        f"🔍 Checking schedule: {schedule.name} (ID: {schedule.id[:8]}...)"
                    )

                    # Skip if already deactivated
                    if schedule.id in deactivated_ids:
                        logger.debug(
                            f"⏩ Skipping already-deactivated schedule: {schedule.name}"
                        )
                        continue

                    # Check if start_datetime hasn't been reached yet
                    if (
                        hasattr(schedule, "start_datetime")
                        and schedule.start_datetime
                    ):
                        start_datetime = ensure_timezone_aware(schedule.start_datetime)
                        if current_time < start_datetime:
                            logger.info(
                                f"⏳ Schedule {schedule.name} hasn't started yet "
                                f"(starts at {start_datetime})"
                            )
                            continue

                    # Check if end_datetime has passed
                    if hasattr(schedule, "end_datetime") and schedule.end_datetime:
                        end_datetime = ensure_timezone_aware(schedule.end_datetime)
                        if current_time > end_datetime:
                            logger.info(f"⏰ Schedule {schedule.name} has expired")
                            await deactivate_backup_schedule(schedule.id)
                            deactivated_ids.add(schedule.id)
                            continue

                    # Check if backup is due
                    next_backup_date = ensure_timezone_aware(schedule.next_backup_date)

                    logger.debug(
                        f"⏰ {schedule.name}: next_backup={next_backup_date}, "
                        f"current={current_time}, "
                        f"due={current_time >= next_backup_date}"
                    )

                    if current_time >= next_backup_date:
                        logger.info(f"💾 Processing backup for schedule: {schedule.name}")

                        try:
                            # Execute database backup
                            success, file_path, file_size = await execute_database_backup(
                                schedule
                            )

                            # Record in history
                            if success:
                                await create_backup_history(
                                    schedule_id=schedule.id,
                                    status="success",
                                    file_path=file_path,
                                    file_size=file_size,
                                )
                                await update_schedule_success(
                                    schedule.id,
                                    int(datetime.now(timezone.utc).timestamp()),
                                    file_path,
                                    file_size,
                                )
                                logger.info(
                                    f"✅ Backup successful for schedule: {schedule.name}"
                                )
                            else:
                                await create_backup_history(
                                    schedule_id=schedule.id,
                                    status="error",
                                    error_message="Backup execution failed",
                                )
                                await update_schedule_error(
                                    schedule.id,
                                    "Backup execution failed",
                                    int(datetime.now(timezone.utc).timestamp()),
                                )
                                logger.error(
                                    f"❌ Backup failed for schedule: {schedule.name}"
                                )

                            # Update next backup date based on frequency
                            if schedule.frequency_type == "hourly":
                                schedule.next_backup_date = current_time + timedelta(
                                    hours=1
                                )
                            elif schedule.frequency_type == "daily":
                                schedule.next_backup_date = current_time + timedelta(
                                    days=1
                                )
                            elif schedule.frequency_type == "weekly":
                                schedule.next_backup_date = current_time + timedelta(
                                    weeks=1
                                )
                            elif schedule.frequency_type == "monthly":
                                schedule.next_backup_date = (
                                    current_time + relativedelta(months=1)
                                )

                            # Update the next backup date in database
                            await update_next_backup_date(
                                schedule.id, schedule.next_backup_date
                            )

                            if success:
                                logger.info(
                                    f"✅ Next backup scheduled for: "
                                    f"{schedule.next_backup_date}"
                                )
                            else:
                                logger.error(
                                    f"❌ Backup failed. Next attempt scheduled for: "
                                    f"{schedule.next_backup_date}"
                                )

                        except Exception as e:
                            logger.error(
                                f"❌ Error processing backup {schedule.name}: {e!s}"
                            )
                            await create_backup_history(
                                schedule_id=schedule.id,
                                status="error",
                                error_message=str(e),
                            )

                except Exception as e:
                    logger.error(
                        f"❌ Error handling schedule "
                        f"{getattr(schedule, 'name', 'unknown')}: {e!s}"
                    )
                    import traceback

                    logger.error(f"Traceback: {traceback.format_exc()}")

        except Exception as e:
            logger.error(f"❌ Error in backup scheduler: {e!s}")

        # Clean up deactivated list periodically
        if len(deactivated_ids) > 100:
            deactivated_ids = set(list(deactivated_ids)[-100:])

        # Check every 60 seconds
        await asyncio.sleep(60)
