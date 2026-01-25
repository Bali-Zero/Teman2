#!/bin/bash
# debug_lint.sh
echo "Current directory: $(pwd)"
echo "Listing node_modules/.bin/next:"
ls -l node_modules/.bin/next
echo "Executing root next binary..."
../../node_modules/.bin/next lint .
