# Data models for database backup extension

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateBackupScheduleData(BaseModel):
    id: Optional[str] = ""
    name: str
    wallet: Optional[str]  # Admin wallet for permissions
    backup_path: str  # Where to save backups
    frequency_type: str  # hourly, daily, weekly, monthly
    start_datetime: datetime
    next_backup_date: datetime
    retention_count: int = 7  # Keep last N backups
    active: bool = True
    end_datetime: Optional[datetime] = None
    compress: bool = True  # Compress backups (gzip)
    created_at: Optional[datetime] = None  # Auto-set by database


class BackupSchedule(BaseModel):
    id: str
    name: str
    wallet: Optional[str] = None
    backup_path: str
    frequency_type: str
    start_datetime: datetime
    next_backup_date: datetime
    retention_count: int = 7
    active: bool = True
    end_datetime: Optional[datetime] = None
    compress: bool = True
    created_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_backup_path: Optional[str] = None  # Path to last successful backup
    last_backup_size: Optional[int] = None  # Size in bytes


class BackupHistory(BaseModel):
    id: str
    schedule_id: str
    timestamp: datetime
    status: str  # success, error
    file_path: Optional[str] = None
    file_size: Optional[int] = None  # Size in bytes
    error_message: Optional[str] = None
