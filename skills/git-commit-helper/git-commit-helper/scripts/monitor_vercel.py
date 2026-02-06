import subprocess
import json
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

def get_vercel_project_name():
    """Tries to get the Vercel project name from vercel.json."""
    vercel_json_path = os.path.join(os.getcwd(), 'vercel.json')
    if os.path.exists(vercel_json_path):
        try:
            with open(vercel_json_path, 'r') as f:
                vercel_config = json.load(f)
                # The "name" field in vercel.json usually corresponds to the project name
                # or a build config. For monorepos, "outputDirectory" might be used.
                # Assuming 'name' if available, otherwise 'outputDirectory' might give a clue
                # or we rely on the default vercel project linking.
                # For `apps/mouth`, its `vercel.json` is at the root.
                if 'name' in vercel_config:
                    return vercel_config['name']
                if 'outputDirectory' in vercel_config and 'apps/mouth' in vercel_config['outputDirectory']:
                    # This indicates it's likely the "mouth" app.
                    # Vercel CLI usually infers project from git repo name or local project link.
                    # Best to leave it to Vercel CLI itself if 'name' isn't explicitly set.
                    pass
        except json.JSONDecodeError:
            logger.warning(f"Could not parse {vercel_json_path}.")
    
    # Fallback to current directory name or let Vercel CLI infer
    # For now, we'll try to infer from vercel.json. If not, rely on 'vercel logs' to pick up linked project.
    return None # Let Vercel CLI try to infer

def monitor_vercel_deployment(project_name=None):
    logger.info("Starting Vercel deployment monitoring...")

    # Check if Vercel CLI is installed
    if not run_command("vercel --version", check=False):
        logger.warning("Vercel CLI not found. Please install it to monitor Vercel deployments (npm i -g vercel).")
        return False

    # Try to get the project name
    if not project_name:
        project_name = get_vercel_project_name()

    vercel_command = ["vercel", "logs", "--follow"]
    if project_name:
        logger.info(f"Attempting to monitor Vercel project: {project_name}")
        vercel_command.extend(["--project", project_name])
    else:
        logger.info("Attempting to monitor Vercel project (inferred from linked project or git repo).")
    
    logger.info("Streaming Vercel deployment logs (press Ctrl+C to stop)...")
    try:
        # Use Popen to stream output
        process = subprocess.Popen(vercel_command, stdout=sys.stdout, stderr=sys.stderr, text=True)
        process.wait()
    except KeyboardInterrupt:
        logger.info("
Stopped Vercel log streaming.")
    except Exception as e:
        logger.error(f"Error streaming Vercel logs: {e}")
        return False
    
    return True

if __name__ == "__main__":
    monitor_vercel_deployment()
