import subprocess
import os
import sys
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, check=True):
    """Helper to run shell commands and return output or raise error."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, check=check)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command}
{e.stderr}")
        return None
    except FileNotFoundError:
        logger.error(f"Command not found. Is '{command.split()[0]}' installed and in PATH?")
        return None

def monitor_flyio_deployment(app_name=None):
    logger.info("Starting Fly.io deployment monitoring...")

    # Check if flyctl CLI is installed
    if not run_command("flyctl version", check=False):
        logger.warning("Fly.io CLI (flyctl) not found. Please install it to monitor Fly.io deployments (https://fly.io/docs/hands-on/install-flyctl/).")
        return False

    # Try to get the app name from an argument or default
    if not app_name:
        # Fallback to common project naming convention or user's project info
        # The agent cannot infer the exact app name without specific fly.toml or user input.
        # For now, we'll suggest a likely name or ask the user.
        logger.warning("Fly.io app name not provided. Attempting to use 'nuzantara-backend-rag' as a default.")
        app_name = "nuzantara-backend-rag" # This is an assumption based on typical naming.

    fly_command = ["flyctl", "logs", "-a", app_name, "--follow"]
    
    logger.info(f"Streaming Fly.io deployment logs for app: {app_name} (press Ctrl+C to stop)...")
    try:
        # Use Popen to stream output
        process = subprocess.Popen(fly_command, stdout=sys.stdout, stderr=sys.stderr, text=True)
        process.wait()
    except KeyboardInterrupt:
        logger.info("
Stopped Fly.io log streaming.")
    except Exception as e:
        logger.error(f"Error streaming Fly.io logs: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Example usage: python monitor_flyio.py my-fly-app
    if len(sys.argv) > 1:
        monitor_flyio_deployment(sys.argv[1])
    else:
        monitor_flyio_deployment()
