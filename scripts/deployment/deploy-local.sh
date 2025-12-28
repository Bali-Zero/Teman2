#!/bin/bash
# Local deployment script for testing before production deployment
# Uses Docker Compose to simulate production environment

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Nuzantara Local Deployment${NC}"
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file not found${NC}"
    read -p "Copy from .env.example? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
        echo -e "${YELLOW}⚠ Please edit .env with your actual values before continuing${NC}"
        exit 0
    else
        echo -e "${RED}❌ Cannot continue without .env file${NC}"
        exit 1
    fi
fi

# Menu
echo ""
echo "Select deployment option:"
echo "1) Start all services"
echo "2) Start services in background"
echo "3) Stop all services"
echo "4) Rebuild and start"
echo "5) View logs"
echo "6) Check service health"
echo "7) Clean up (remove containers and volumes)"
echo "8) Exit"
echo ""
read -p "Enter choice [1-8]: " choice

case $choice in
    1)
        echo -e "${YELLOW}Starting all services...${NC}"
        docker-compose up
        ;;
    2)
        echo -e "${YELLOW}Starting services in background...${NC}"
        docker-compose up -d
        echo ""
        echo -e "${GREEN}✓ Services started${NC}"
        echo ""
        echo "Service URLs:"
        echo "  Backend RAG:  http://localhost:8080"
        echo "  Qdrant:       http://localhost:6333/dashboard"
        echo "  PostgreSQL:   localhost:5432"
        echo "  Redis:        localhost:6379"
        echo "  Prometheus:   http://localhost:9090"
        echo "  Grafana:      http://localhost:3001"
        echo "  Jaeger:       http://localhost:16686"
        echo ""
        echo "View logs: docker-compose logs -f"
        ;;
    3)
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker-compose down
        echo -e "${GREEN}✓ Services stopped${NC}"
        ;;
    4)
        echo -e "${YELLOW}Rebuilding and starting services...${NC}"
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        echo -e "${GREEN}✓ Services rebuilt and started${NC}"
        ;;
    5)
        echo -e "${YELLOW}Viewing logs (Ctrl+C to exit)...${NC}"
        docker-compose logs -f
        ;;
    6)
        echo -e "${YELLOW}Checking service health...${NC}"
        echo ""
        
        # Check backend
        echo -n "Backend RAG: "
        if curl -f -s http://localhost:8080/health > /dev/null; then
            echo -e "${GREEN}✓ Healthy${NC}"
            curl -s http://localhost:8080/health | jq .
        else
            echo -e "${RED}✗ Not responding${NC}"
        fi
        
        echo ""
        echo -n "Qdrant: "
        if curl -f -s http://localhost:6333 > /dev/null; then
            echo -e "${GREEN}✓ Healthy${NC}"
        else
            echo -e "${RED}✗ Not responding${NC}"
        fi
        
        echo ""
        echo -n "PostgreSQL: "
        if docker-compose exec -T db pg_isready > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
        else
            echo -e "${RED}✗ Not responding${NC}"
        fi
        
        echo ""
        echo -n "Redis: "
        if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
        else
            echo -e "${RED}✗ Not responding${NC}"
        fi
        ;;
    7)
        echo -e "${RED}⚠ WARNING: This will remove all containers and volumes${NC}"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Cleaning up...${NC}"
            docker-compose down -v
            echo -e "${GREEN}✓ Cleanup complete${NC}"
        fi
        ;;
    8)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
