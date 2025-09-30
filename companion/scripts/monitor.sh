#!/bin/bash

# monitor.sh - Health monitoring script for AI Companion System
# Checks the status of all services and reports system health

set -e

echo "=== AI Companion System Health Monitor ==="
echo "$(date): Starting health check..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Configuration
GATEWAY_PORT="${GATEWAY_PORT:-8000}"
GATEWAY_HOST="${GATEWAY_HOST:-localhost}"
LETTA_PORT="${LETTA_PORT:-8283}"
LETTA_HOST="${LETTA_HOST:-localhost}"

# Global counters
SERVICE_COUNT=0
HEALTHY_SERVICES=0

# Function to check Docker containers
check_docker_containers() {
    log_info "Checking Docker containers..."
    
    # List of expected containers
    containers=(
        "companion_postgres"
        "companion_qdrant"
        "companion_redis"
        "companion_letta"
        "companion_embedding_service"
        "companion_gateway"
        "companion_discord_bot"
        "companion_caddy"
    )
    
    for container in "${containers[@]}"; do
        ((SERVICE_COUNT++))
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            log_info "✅ Container ${container} is running"
            ((HEALTHY_SERVICES++))
        else
            log_error "❌ Container ${container} is not running"
        fi
    done
}

# Function to check service health endpoints
check_service_health_endpoints() {
    log_info "Checking service health endpoints..."
    
    # Gateway API health check
    ((SERVICE_COUNT++))
    if curl -s -f "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" > /dev/null; then
        log_info "✅ Gateway API is healthy"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ Gateway API is unhealthy"
    fi
    
    # Letta service health check
    ((SERVICE_COUNT++))
    if curl -s -f "http://${LETTA_HOST}:${LETTA_PORT}/v1/config" > /dev/null; then
        log_info "✅ Letta service is healthy"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ Letta service is unhealthy"
    fi
    
    # Embedding service health check
    ((SERVICE_COUNT++))
    if curl -s -f "http://${GATEWAY_HOST}:${EMBEDDING_SERVICE_PORT:-8002}/health" > /dev/null; then
        log_info "✅ Embedding service is healthy"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ Embedding service is unhealthy"
    fi
}

# Function to check database connectivity
check_database_connectivity() {
    log_info "Checking database connectivity..."
    
    # PostgreSQL health check
    ((SERVICE_COUNT++))
    if docker exec companion_postgres pg_isready -U companion -d companion_db > /dev/null 2>&1; then
        log_info "✅ PostgreSQL database is accessible"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ PostgreSQL database is not accessible"
    fi
    
    # Redis health check
    ((SERVICE_COUNT++))
    if docker exec companion_redis redis-cli ping > /dev/null 2>&1; then
        log_info "✅ Redis cache is accessible"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ Redis cache is not accessible"
    fi
    
    # Qdrant health check
    ((SERVICE_COUNT++))
    if curl -s -f "http://localhost:6333/health" > /dev/null; then
        log_info "✅ Qdrant vector database is accessible"
        ((HEALTHY_SERVICES++))
    else
        log_error "❌ Qdrant vector database is not accessible"
    fi
}

# Function to check resource usage
check_resource_usage() {
    log_info "Checking system resource usage..."
    
    # CPU usage
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    log_debug "CPU usage: ${cpu_usage}%"
    
    # Memory usage
    memory_usage=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
    log_debug "Memory usage: ${memory_usage}%"
    
    # Disk usage
    disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    log_debug "Disk usage: ${disk_usage}%"
    
    # Resource usage alerts
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        log_warning "High CPU usage: ${cpu_usage}%"
    fi
    
    if (( $(echo "$memory_usage > 80" | bc -l) )); then
        log_warning "High memory usage: ${memory_usage}%"
    fi
    
    if [ "$disk_usage" -gt 80 ]; then
        log_warning "High disk usage: ${disk_usage}%"
    fi
}

# Function to check recent logs for errors
check_recent_logs() {
    log_info "Checking recent logs for errors..."
    
    # Check for recent errors in gateway logs
    error_count=$(docker logs companion_gateway --since 1h 2>&1 | grep -c "ERROR\|CRITICAL\|FATAL" || true)
    if [ "$error_count" -gt 0 ]; then
        log_warning "Found ${error_count} errors in gateway logs in the last hour"
        # Show recent errors (last 5)
        docker logs companion_gateway --since 1h 2>&1 | grep "ERROR\|CRITICAL\|FATAL" | tail -5
    else
        log_info "✅ No errors found in gateway logs"
    fi
    
    # Check for recent errors in other services
    services=("companion_letta" "companion_embedding_service" "companion_discord_bot")
    for service in "${services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
            error_count=$(docker logs "$service" --since 1h 2>&1 | grep -c "ERROR\|CRITICAL\|FATAL" || true)
            if [ "$error_count" -gt 0 ]; then
                log_warning "Found ${error_count} errors in ${service} logs in the last hour"
            fi
        fi
    done
}

# Function to check user activity
check_user_activity() {
    log_info "Checking user activity..."
    
    # Check if users are active (this would require database queries)
    # For now, we'll make a placeholder check
    if curl -s -f "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" > /dev/null; then
        # Try to get recent user stats (placeholder)
        user_stats=$(curl -s "http://${GATEWAY_HOST}:${GATEWAY_PORT}/api/admin/stats" 2>/dev/null || echo "{}")
        if [ "$user_stats" != "{}" ]; then
            log_info "✅ User activity monitoring available"
        else
            log_debug "User activity monitoring endpoint not available in development mode"
        fi
    fi
}

# Function to check security incidents
check_security_incidents() {
    log_info "Checking security incidents..."
    
    # This would check for recent security incidents
    # For now, we'll make a placeholder check
    log_debug "Security incident checking not implemented in this script"
}

# Function to generate health report
generate_health_report() {
    log_info "Generating health report..."
    
    echo ""
    echo "=== System Health Report ==="
    echo "Timestamp: $(date)"
    echo "Services checked: $SERVICE_COUNT"
    echo "Healthy services: $HEALTHY_SERVICES"
    echo "Service health: $(( HEALTHY_SERVICES * 100 / SERVICE_COUNT ))%"
    
    if [ "$HEALTHY_SERVICES" -eq "$SERVICE_COUNT" ]; then
        echo -e "${GREEN}✅ All services are healthy${NC}"
        return 0
    elif [ "$HEALTHY_SERVICES" -ge $(( SERVICE_COUNT * 3 / 4 )) ]; then
        echo -e "${YELLOW}⚠️  Most services are healthy, some issues detected${NC}"
        return 1
    else
        echo -e "${RED}❌ Critical issues detected, system is unhealthy${NC}"
        return 2
    fi
}

# Function to send alerts (placeholder)
send_alerts() {
    local health_status=$1
    
    case $health_status in
        0)
            # All healthy - no alert needed
            ;;
        1)
            # Warning - minor issues
            log_warning "System health warnings - monitoring recommended"
            ;;
        2)
            # Critical - send alert
            log_error "Critical system health issues detected!"
            # In a real implementation, this would send emails, Slack notifications, etc.
            # send_slack_notification "CRITICAL: AI Companion System health issues detected"
            # send_email_alert "System Administrator" "Critical AI Companion System Issues"
            ;;
    esac
}

# Main function
main() {
    log_info "Starting comprehensive health check at $(date)"
    
    # Run all checks
    check_docker_containers
    check_service_health_endpoints
    check_database_connectivity
    check_resource_usage
    check_recent_logs
    check_user_activity
    check_security_incidents
    
    # Generate report
    health_status=$(generate_health_report)
    
    # Send alerts if needed
    send_alerts $health_status
    
    log_info "Health check completed at $(date)"
    
    return $health_status
}

# Function to run continuous monitoring
continuous_monitor() {
    local interval=${1:-60}  # Default 60 seconds
    
    log_info "Starting continuous monitoring (every ${interval} seconds)..."
    
    while true; do
        echo ""
        echo "=== Continuous Monitor Run ($(date)) ==="
        main
        sleep $interval
    done
}

# Parse command line arguments
case "${1:-single}" in
    "single")
        main
        exit $?
        ;;
    "continuous")
        continuous_monitor "${2:-60}"
        ;;
    *)
        echo "Usage: $0 [single|continuous [interval_seconds]]"
        echo "  single: Run one-time health check (default)"
        echo "  continuous: Run continuous monitoring with specified interval (default 60 seconds)"
        exit 1
        ;;
esac