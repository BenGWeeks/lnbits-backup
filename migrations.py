# Database migrations for backup extension
# If you create a new release, remember the migration file is like a blockchain - never edit, only add!

from typing import Any


async def m001_initial(db: Any) -> None:
    """
    Initial backup schedules table with scheduling and error tracking.
    Supports hourly/daily/weekly/monthly backups.
    """
    await db.execute(
        """
        CREATE TABLE backup_schedules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            frequency_type TEXT NOT NULL,
            start_datetime TIMESTAMP NOT NULL,
            next_backup_date TIMESTAMP NOT NULL,
            retention_count INTEGER DEFAULT 7,
            active BOOLEAN DEFAULT TRUE,
            end_datetime TIMESTAMP,
            compress BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT,
            last_error_time TIMESTAMP,
            last_success_time TIMESTAMP,
            last_backup_path TEXT,
            last_backup_size INTEGER
        );
    """
    )


async def m002_backup_history(db: Any) -> None:
    """
    Backup history table to track all backup executions.
    """
    await db.execute(
        """
        CREATE TABLE backup_history (
            id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            error_message TEXT,
            FOREIGN KEY (schedule_id) REFERENCES backup_schedules(id) ON DELETE CASCADE
        );
    """
    )

    # Create index for faster queries
    await db.execute(
        """
        CREATE INDEX idx_backup_history_schedule
        ON backup_history(schedule_id, timestamp DESC);
    """
    )
