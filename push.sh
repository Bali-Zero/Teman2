#!/bin/bash
cd /Users/nuzantara/Desktop/nuzantara
git push origin main > /tmp/push_result.txt 2>&1
echo "EXIT:$?" >> /tmp/push_result.txt
