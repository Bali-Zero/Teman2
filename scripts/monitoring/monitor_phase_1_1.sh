#!/bin/bash
# Phase 1.1 Performance Monitoring Script
# Monitors parallel context loading speedup and TTFT improvement

APP_NAME="nuzantara-rag"

echo "📊 Phase 1.1 Performance Monitoring"
echo "App: $APP_NAME"
echo ""

# Extract metrics from logs
echo "📥 Fetching recent logs..."
flyctl logs -a "$APP_NAME" 2>&1 | grep -E "PARALLEL LOADING|Profile fetch|Memory fetch|speedup:" | tail -20

echo ""
echo "📊 To see detailed metrics, run:"
echo "   flyctl logs -a $APP_NAME | grep 'PARALLEL LOADING'"
