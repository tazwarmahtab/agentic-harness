#!/bin/bash
# AOS Daily Backup Script
# Runs via cron at 02:00

set -euo pipefail

BACKUP_DIR="/backup/aos/$(date +%Y-%m-%d)"
AOS_ROOT="/Users/tazwarmahtab/orca/agentic-harness"
NETSO_HQ="/Users/tazwarmahtab/Documents/10-Projects/Netso_HQ"

mkdir -p "$BACKUP_DIR"

echo "Starting AOS backup to $BACKUP_DIR"

# Database files
cp "$AOS_ROOT/aos_memory.db" "$BACKUP_DIR/" 2>/dev/null || echo "aos_memory.db not found"
cp "$AOS_ROOT/approvals.db" "$BACKUP_DIR/" 2>/dev/null || echo "approvals.db not found"
cp "$AOS_ROOT/usage.db" "$BACKUP_DIR/" 2>/dev/null || echo "usage.db not found"

# Venture artifacts
mkdir -p "$BACKUP_DIR/artifacts"
cp -r "$NETSO_HQ/ai_system/System" "$BACKUP_DIR/artifacts/" 2>/dev/null || echo "System artifacts not found"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_DIR" .
echo "Backup created: $BACKUP_DIR.tar.gz"

# Upload to S3/GCS (configure as needed)
# aws s3 cp "$BACKUP_DIR.tar.gz" s3://your-bucket/aos-backups/
# gsutil cp "$BACKUP_DIR.tar.gz" gs://your-bucket/aos-backups/

# Cleanup old backups (keep 30 days)
find /backup/aos -name "*.tar.gz" -mtime +30 -delete

echo "Backup complete"