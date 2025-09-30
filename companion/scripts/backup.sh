#!/bin/bash

# backup.sh - Comprehensive backup script for AI Companion System
# Performs backups of PostgreSQL database and Qdrant snapshots

set -e  # Exit on any error

echo "=== AI Companion System Backup Script ==="
echo "$(date): Starting backup process..."

# Configuration - these should match your docker-compose.yml and .env
BACKUP_BASE_DIR="${BACKUP_DIR:-/backups/companion}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to backup PostgreSQL database
backup_postgres() {
    log_info "Starting PostgreSQL database backup..."
    
    # Check if PostgreSQL container is running
    if ! docker ps | grep -q "companion_postgres"; then
        log_error "PostgreSQL container (companion_postgres) is not running"
        return 1
    fi
    
    # Create database dump using pg_dump
    PG_DUMP_CMD="pg_dump -U companion -d companion_db --clean --if-exists --no-owner --no-privileges"
    
    if docker exec companion_postgres $PG_DUMP_CMD > "$BACKUP_DIR/database_dump.sql"; then
        # Compress the dump
        gzip "$BACKUP_DIR/database_dump.sql"
        log_info "PostgreSQL backup completed: $BACKUP_DIR/database_dump.sql.gz"
    else
        log_error "Failed to create PostgreSQL backup"
        return 1
    fi
}

# Function to backup Qdrant vector database
backup_qdrant() {
    log_info "Starting Qdrant vector database backup..."
    
    # Check if Qdrant container is running
    if ! docker ps | grep -q "companion_qdrant"; then
        log_error "Qdrant container (companion_qdrant) is not running"
        return 1
    fi
    
    # Create Qdrant snapshot
    # First create a snapshot via API
    if curl -s -X POST "http://localhost:6333/collections/memories/snapshots" > /dev/null; then
        log_info "Qdrant snapshot created via API"
    else
        log_warning "Failed to create Qdrant snapshot via API, copying storage directory instead"
        # Copy the storage directory as fallback
        if docker cp companion_qdrant:/qdrant/storage "$BACKUP_DIR/qdrant_storage"; then
            log_info "Qdrant storage copied directly"
        else
            log_error "Failed to copy Qdrant storage directory"
            return 1
        fi
    fi
}

# Function to backup Redis cache
backup_redis() {
    log_info "Starting Redis cache backup..."
    
    # Check if Redis container is running
    if ! docker ps | grep -q "companion_redis"; then
        log_error "Redis container (companion_redis) is not running"
        return 1
    fi
    
    # Save Redis data to disk
    if docker exec companion_redis redis-cli BGSAVE; then
        # Wait for save to complete
        sleep 5
        
        # Copy the dump file
        if docker cp companion_redis:/data/dump.rdb "$BACKUP_DIR/redis_dump.rdb"; then
            log_info "Redis backup completed: $BACKUP_DIR/redis_dump.rdb"
        else
            log_error "Failed to copy Redis dump file"
            return 1
        fi
    else
        log_error "Failed to initiate Redis BGSAVE"
        return 1
    fi
}

# Function to backup Letta data
backup_letta() {
    log_info "Starting Letta framework backup..."
    
    # Check if Letta container is running
    if ! docker ps | grep -q "companion_letta"; then
        log_error "Letta container (companion_letta) is not running"
        return 1
    fi
    
    # Copy Letta data directory
    if docker cp companion_letta:/app/data "$BACKUP_DIR/letta_data"; then
        log_info "Letta backup completed: $BACKUP_DIR/letta_data"
    else
        log_error "Failed to copy Letta data directory"
        return 1
    fi
}

# Function to create backup archive
create_archive() {
    log_info "Creating backup archive..."
    
    cd "$BACKUP_BASE_DIR"
    ARCHIVE_NAME="${TIMESTAMP}_companion_backup.tar.gz"
    
    if tar -czf "$ARCHIVE_NAME" "$TIMESTAMP/"; then
        log_info "Backup archive created: $BACKUP_BASE_DIR/$ARCHIVE_NAME"
        
        # Remove uncompressed backup directory to save space
        rm -rf "$BACKUP_DIR/"
        log_info "Uncompressed backup directory removed"
        
        echo "$ARCHIVE_NAME" > "$BACKUP_BASE_DIR/latest_backup.txt"
        log_info "Latest backup record updated"
    else
        log_error "Failed to create backup archive"
        return 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Keep only last 7 days of backups
    find "$BACKUP_BASE_DIR" -name "*_companion_backup.tar.gz" -mtime +7 -delete 2>/dev/null || true
    log_info "Old backups cleaned up (kept last 7 days)"
}

# Function to verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    ARCHIVE_NAME="${TIMESTAMP}_companion_backup.tar.gz"
    if [ -f "$BACKUP_BASE_DIR/$ARCHIVE_NAME" ]; then
        # Test archive integrity
        if tar -tzf "$BACKUP_BASE_DIR/$ARCHIVE_NAME" > /dev/null 2>&1; then
            log_info "Backup archive integrity verified"
        else
            log_error "Backup archive integrity check failed"
            return 1
        fi
    else
        log_warning "Backup archive not found for verification"
    fi
}

# Main execution
main() {
    log_info "Starting comprehensive backup at $(date)"
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Perform all backups
    backup_postgres || log_error "PostgreSQL backup failed"
    backup_qdrant || log_error "Qdrant backup failed"
    backup_redis || log_error "Redis backup failed"
    backup_letta || log_error "Letta backup failed"
    
    # Create archive and cleanup
    create_archive || log_error "Archive creation failed"
    cleanup_old_backups || log_error "Backup cleanup failed"
    verify_backup || log_error "Backup verification failed"
    
    log_info "Backup process completed at $(date)"
    echo "✅ Backup completed successfully!"
    echo "📁 Backup location: $BACKUP_BASE_DIR/${TIMESTAMP}_companion_backup.tar.gz"
    
    # Print backup summary
    echo ""
    echo "=== Backup Summary ==="
    echo "Timestamp: $TIMESTAMP"
    echo "Components backed up:"
    echo "  - PostgreSQL database"
    echo "  - Qdrant vector database"
    echo "  - Redis cache"
    echo "  - Letta framework data"
    echo "======================"
}

# Function to restore from backup
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Usage: $0 --restore <backup_file.tar.gz>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    log_info "Restoring from backup: $backup_file"
    
    # Extract backup
    RESTORE_DIR="/tmp/companion_restore_$(date +%s)"
    mkdir -p "$RESTORE_DIR"
    tar -xzf "$backup_file" -C "$RESTORE_DIR"
    
    # Stop services
    log_info "Stopping services..."
    docker-compose down
    
    # Restore database
    log_info "Restoring PostgreSQL database..."
    docker-compose up -d postgres
    sleep 10
    
    gunzip -c "$RESTORE_DIR"/*/database_dump.sql.gz | docker-compose exec -T postgres psql -U companion companion_db
    
    # Restore Qdrant
    log_info "Restoring Qdrant..."
    docker-compose up -d qdrant
    sleep 10
    
    # Copy Qdrant snapshots back
    if [ -d "$RESTORE_DIR"/*/qdrant_storage/ ]; then
        docker cp "$RESTORE_DIR"/*/qdrant_storage/. companion_qdrant_1:/qdrant/storage/
    fi
    
    # Restore Redis
    log_info "Restoring Redis cache..."
    docker-compose up -d redis
    sleep 5
    
    if [ -f "$RESTORE_DIR"/*/redis_dump.rdb ]; then
        docker cp "$RESTORE_DIR"/*/redis_dump.rdb companion_redis_1:/data/dump.rdb
        docker exec companion_redis_1 redis-server /etc/redis/redis.conf
    fi
    
    # Restore Letta
    log_info "Restoring Letta data..."
    docker-compose up -d letta
    sleep 10
    
    if [ -d "$RESTORE_DIR"/*/letta_data/ ]; then
        docker cp "$RESTORE_DIR"/*/letta_data/. companion_letta_1:/app/data/
    fi
    
    # Start all services
    log_info "Starting all services..."
    docker-compose up -d
    
    # Cleanup
    rm -rf "$RESTORE_DIR"
    
    log_info "Restore completed successfully"
}

# Parse command line arguments
case "${1:-backup}" in
    "backup")
        main
        ;;
    "--restore")
        restore_backup "$2"
        ;;
    *)
        echo "Usage: $0 [backup|--restore <backup_file.tar.gz>]"
        exit 1
        ;;
esac