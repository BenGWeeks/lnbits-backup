# Database Backup Extension

Automatic scheduled database backups for LNbits with support for SQLite and PostgreSQL databases.

## Features

⏰ **Automated Schedules** - Set up hourly, daily, weekly, or monthly backups

💾 **Database Support** - Works with SQLite and PostgreSQL

🗜️ **Compression** - Optional gzip compression to save space

🧹 **Auto Cleanup** - Retention policy automatically removes old backups

📊 **Error Tracking** - Monitor backup success and failures

🚀 **Manual Backups** - Trigger backups on demand

## Quick Start

1. Click **ENABLE** to activate the extension
2. Click **OPEN** to access the backup management interface
3. Create a new backup schedule with your preferred frequency
4. Set the backup directory path (e.g., `./backups`)
5. Configure retention count (how many backups to keep)
6. Save and let the scheduler handle the rest!

## Backup Frequencies

- **Hourly** - Every hour
- **Daily** - Once per day at the scheduled time
- **Weekly** - Once per week
- **Monthly** - Once per month

## Requirements

- Write permissions to the backup directory
- For PostgreSQL: `pg_dump` command must be available

Created by Ben Weeks
