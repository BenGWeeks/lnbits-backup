# LNbits Database Backup Extension

Automatic scheduled database backups for LNbits with support for SQLite and PostgreSQL databases.

## Features

- **Automated Scheduled Backups**: Schedule backups to run hourly, daily, weekly, or monthly
- **Database Support**: Works with both SQLite and PostgreSQL databases
- **Compression**: Optional gzip compression for backup files
- **Retention Policy**: Automatically clean up old backups, keeping only the last N backups
- **Error Tracking**: Track backup failures and success status
- **Manual Backups**: Trigger backups manually on demand
- **Quasar UI**: Modern, responsive web interface

## Installation

1. Create a symbolic link from your LNbits development directory:
   ```bash
   ln -s /mnt/raid1/GitHub/lnbits-backup/lnbits/extensions/backup /path/to/lnbits-dev/lnbits/extensions/backup
   ```

2. Restart LNbits to load the extension

3. Enable the extension from the LNbits extensions page

## Usage

### Creating a Backup Schedule

1. Navigate to the Backup extension page
2. Click "New Backup Schedule"
3. Fill in the details:
   - **Schedule Name**: A descriptive name for the schedule
   - **Backup Directory Path**: Where to save backups (e.g., `./backups` or `/var/backups/lnbits`)
   - **Frequency**: Choose hourly, daily, weekly, or monthly
   - **Start Date & Time**: When to start the backup schedule
   - **End Date & Time** (optional): When to stop the schedule
   - **Retention Count**: Number of backups to keep (older ones will be deleted)
   - **Compress Backups**: Enable gzip compression
   - **Active**: Enable/disable the schedule

### Manual Backups

Click the backup icon (📦) next to any schedule to trigger an immediate backup.

## Backup File Naming

Backups are named with timestamps:
- SQLite: `lnbits_backup_YYYYMMDD_HHMMSS.sqlite3` (or `.sqlite3.gz` if compressed)
- PostgreSQL: `lnbits_backup_YYYYMMDD_HHMMSS.sql` (or `.sql.gz` if compressed)

## Technical Details

### Database Schema

**backup_schedules**
- `id`: Unique identifier
- `name`: Schedule name
- `wallet`: Admin wallet for permissions
- `backup_path`: Backup directory path
- `frequency_type`: hourly, daily, weekly, monthly
- `start_datetime`: When to start the schedule
- `next_backup_date`: Next scheduled backup time
- `retention_count`: Number of backups to keep
- `active`: Schedule enabled/disabled
- `end_datetime`: Optional end date
- `compress`: Enable compression
- `last_error`, `last_error_time`: Error tracking
- `last_success_time`, `last_backup_path`, `last_backup_size`: Success tracking

**backup_history**
- `id`: Unique identifier
- `schedule_id`: Reference to schedule
- `timestamp`: Backup execution time
- `status`: success or error
- `file_path`: Path to backup file
- `file_size`: Size in bytes
- `error_message`: Error details if failed

### Backup Methods

**SQLite**: Uses `VACUUM INTO` for safe, consistent backups while the database is running.

**PostgreSQL**: Uses `pg_dump` command-line tool (requires PostgreSQL client tools installed).

### Scheduler

The extension runs a background task that checks every 60 seconds for due backups. When a backup is due, it:
1. Executes the database backup
2. Compresses if enabled
3. Cleans up old backups based on retention policy
4. Updates the next backup date
5. Records success/failure in history

## API Endpoints

All endpoints require authentication with wallet admin key.

### Schedules

- `GET /backup/api/v1/schedules` - List all schedules
- `GET /backup/api/v1/schedules/{id}` - Get specific schedule
- `POST /backup/api/v1/schedules` - Create new schedule
- `PUT /backup/api/v1/schedules/{id}` - Update schedule
- `DELETE /backup/api/v1/schedules/{id}` - Delete schedule

### Backups

- `POST /backup/api/v1/backup/manual?schedule_id={id}` - Trigger manual backup
- `GET /backup/api/v1/history?schedule_id={id}&limit=50` - Get backup history

## File Structure

```
backup/
├── __init__.py           # Extension registration and startup
├── config.json           # Extension metadata
├── models.py             # Pydantic data models
├── migrations.py         # Database schema
├── crud.py               # Database operations
├── tasks.py              # Scheduler and backup execution
├── views.py              # Web UI routes
├── views_api.py          # REST API endpoints
├── templates/
│   └── backup/
│       └── index.html    # Main UI template
└── static/
    └── js/
        └── backup.js     # Vue.js + Quasar frontend
```

## Requirements

- LNbits 1.0.0+
- For PostgreSQL backups: `pg_dump` command must be available in PATH
- Write permissions to the backup directory

## Development

Based on the [allowance extension](https://github.com/bengweeks/allowance) framework.

### Key Dependencies

- FastAPI for API routes
- Pydantic for data validation
- SQLAlchemy for database operations
- Vue.js 3 + Quasar 2 for frontend
- loguru for logging
- python-dateutil for date calculations

## License

MIT

## Author

Ben Weeks
