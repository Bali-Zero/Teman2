#!/bin/bash
cd /Users/nuzantara/Desktop/nuzantara
git push origin main > /Users/nuzantara/Desktop/nuzantara/push_result.txt 2>&1
echo "PUSH_EXIT:$?" >> /Users/nuzantara/Desktop/nuzantara/push_result.txt
