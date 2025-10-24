#!/bin/bash

# Function to check if Python process is running
check_python_process() {
    if pgrep -f "python.*scraper" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to check external API
check_external_api() {
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities' \
        -H 'Content-Type: application/json' \
        -H 'Origin: https://apps.dos.ny.gov' \
        --data-raw '{"searchValue":"test","searchByTypeIndicator":"EntityName","searchExpressionIndicator":"Contains","entityStatusIndicator":"AllStatuses","entityTypeIndicator":["Corporation"],"listPaginationInfo":{"listStartRecord":1,"listEndRecord":1}}' \
        --max-time 10)
    
    if [ "$http_code" = "200" ]; then
        return 0
    else
        echo "API returned HTTP code: $http_code"
        return 1
    fi
}

# Function to check if logs are being written (process is active)
check_log_activity() {
    local log_dir="/app/logs"
    local current_time=$(date +%s)
    
    # Check if any log file was modified in the last 30 minutes (1800 seconds)
    if [ -d "$log_dir" ]; then
        local latest_log=$(find "$log_dir" -type f -name "*.log" -newermt "30 minutes ago" | head -1)
        if [ -n "$latest_log" ]; then
            return 0
        fi
    fi
    
    # If no recent log activity, check if it's a new day and process should restart
    local last_run_file="/tmp/last_scraper_run"
    local current_date=$(date +%Y-%m-%d)
    
    if [ -f "$last_run_file" ]; then
        local last_run_date=$(cat "$last_run_file")
        if [ "$current_date" != "$last_run_date" ]; then
            echo "New day detected, scraper should restart"
            return 1
        fi
    fi
    
    # If process just started, give it some time
    if [ -f "/tmp/container_start_time" ]; then
        local start_time=$(cat "/tmp/container_start_time")
        local elapsed=$((current_time - start_time))
        if [ $elapsed -lt 300 ]; then  # Less than 5 minutes since start
            return 0
        fi
    fi
    
    return 1
}

# Check database connectivity
check_database() {
    if command -v pg_isready > /dev/null; then
        pg_isready -h db -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -t 5
        return $?
    fi
    return 0  # Skip if pg_isready not available
}

echo "Starting healthcheck..."

# Record container start time if not exists
if [ ! -f "/tmp/container_start_time" ]; then
    date +%s > "/tmp/container_start_time"
fi

# Check database first
if ! check_database; then
    echo "Database health check failed"
    exit 1
fi

# Check external API
if ! check_external_api; then
    echo "External API health check failed"
    exit 1
fi

# Check if Python process is running
if check_python_process; then
    echo "Python process is running"
    # Check if process is active (writing logs)
    if check_log_activity; then
        echo "Process appears to be active (recent log activity)"
        exit 0
    else
        echo "Process appears to be stuck (no recent log activity)"
        exit 1
    fi
else
    echo "Python process is not running"
    # For daily scraper, this might be normal if it completed
    # Check if it's a new day and should restart
    current_date=$(date +%Y-%m-%d)
    last_run_file="/tmp/last_scraper_run"
    
    if [ -f "$last_run_file" ]; then
        last_run_date=$(cat "$last_run_file")
        if [ "$current_date" != "$last_run_date" ]; then
            echo "New day - scraper should restart"
            exit 1
        else
            echo "Scraper completed for today"
            exit 0
        fi
    else
        echo "No previous run record - allowing startup"
        exit 0
    fi
fi