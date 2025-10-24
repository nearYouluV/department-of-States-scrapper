#!/bin/bash

# Simple monitoring script to check scraper health
# Can be run as a cron job on the host system

CONTAINER_NAME="scraper_app"
LOG_FILE="/var/log/scraper_monitor.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if container is running
if ! docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Container $CONTAINER_NAME is not running!"
    
    # Try to restart the container
    log "Attempting to restart container..."
    if docker restart "$CONTAINER_NAME"; then
        log "Container restarted successfully"
    else
        log "CRITICAL: Failed to restart container!"
        # You could add notification logic here (email, Slack, etc.)
    fi
    exit 1
fi

# Check container health
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null)

if [ "$HEALTH_STATUS" = "unhealthy" ]; then
    log "WARNING: Container $CONTAINER_NAME is unhealthy"
    
    # Get recent logs
    log "Recent container logs:"
    docker logs --tail 20 "$CONTAINER_NAME" 2>&1 | while read -r line; do
        log "  $line"
    done
    
    # Restart unhealthy container
    log "Restarting unhealthy container..."
    if docker restart "$CONTAINER_NAME"; then
        log "Container restarted due to health check failure"
    else
        log "CRITICAL: Failed to restart unhealthy container!"
    fi
    exit 1
elif [ "$HEALTH_STATUS" = "healthy" ]; then
    log "Container $CONTAINER_NAME is healthy"
else
    log "Container $CONTAINER_NAME health status: $HEALTH_STATUS"
fi

# Check log activity (if logs are mounted)
LOG_DIR="/mnt/postgres_data/scraper_logs"
if [ -d "$LOG_DIR" ]; then
    # Check if any log was modified in the last 2 hours
    RECENT_LOGS=$(find "$LOG_DIR" -name "*.log" -newermt "2 hours ago" | wc -l)
    if [ "$RECENT_LOGS" -eq 0 ]; then
        log "WARNING: No recent log activity in $LOG_DIR"
    else
        log "Found $RECENT_LOGS recent log files"
    fi
fi

log "Monitoring check completed successfully"
