import subprocess
import os
import re
import logging

# Configure basic logging for the script itself
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_command(command):
    """Helper to run shell commands and return output or raise error."""
    result = subprocess.run(command, capture_output=True, text=True, shell=True, check=False)
    if result.returncode != 0:
        logger.error(f"Command failed: {command}
{result.stderr}")
        return None
    return result.stdout.strip()

def fix_print_statements():
    logger.info("Starting to fix print() statements in staged Python files...")

    # Get staged Python files
    # --diff-filter=ACM: Added, Copied, Modified files
    staged_files_output = run_command("git diff --cached --name-only --diff-filter=ACM")
    if staged_files_output is None:
        logger.error("Failed to get list of staged files.")
        return False

    staged_python_files = [
        f for f in staged_files_output.split('
') if f.endswith('.py') and os.path.exists(f)
    ]

    if not staged_python_files:
        logger.info("No staged Python files found to check for print() statements.")
        return True

    fixed_files_count = 0
    for filepath in staged_python_files:
        logger.info(f"Processing {filepath}...")
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            original_content = content
            
            # Check if logging is already imported and logger is defined
            has_logging_import = re.search(r'^\s*import logging', content, re.MULTILINE)
            has_logger_definition = re.search(r'logger\s*=\s*logging\.getLogger', content)

            # Find and replace print() statements
            # This regex is simple and might need refinement for complex cases
            # It targets 'print(' followed by anything up to ')'
            # This will replace all print() with logger.info()
            content = re.sub(r'print\((.*?)\)', r'logger.info(\1)', content)

            # Add logging import and logger definition if not present
            if not has_logging_import:
                # Find the last import statement or module docstring
                last_import_match = None
                for match in re.finditer(r'^\s*import[\w\s,.]+$|^\s*from[\w\s,.]+import[\w\s,.]+', original_content, re.MULTILINE):
                    last_import_match = match
                
                if last_import_match:
                    insert_point = last_import_match.end()
                    content = content[:insert_point] + '
import logging
' + content[insert_point:]
                else:
                    # If no imports, add at the top after docstring/shebang if present
                    first_line_newline = content.find('
')
                    if content.startswith('#!'): # shebang
                        insert_point = content.find('
', first_line_newline + 1) # after second newline
                    elif content.startswith('"""') or content.startswith("'''"): # docstring
                        insert_point = content.find('"""
') + 4 if content.find('"""
') != -1 else content.find("'''
") + 4
                        if insert_point == 3: # no docstring
                            insert_point = 0
                    else:
                        insert_point = 0
                    
                    content = content[:insert_point] + 'import logging
' + content[insert_point:]


            if not has_logger_definition:
                # Find a suitable place to insert logger definition, usually after imports
                insert_point = 0
                last_import_or_docstring_end = -1
                
                # Try to find the last import or docstring
                docstring_match = re.search(r'("""[^"]*"""|'''[^']*''')', content, re.DOTALL)
                if docstring_match:
                    last_import_or_docstring_end = docstring_match.end()
                
                last_import_match = None
                for match in re.finditer(r'^\s*(import|from)\s+[\w.]+', content, re.MULTILINE):
                    last_import_match = match
                
                if last_import_match:
                    last_import_or_docstring_end = max(last_import_or_docstring_end, last_import_match.end())
                
                if last_import_or_docstring_end != -1:
                    insert_point = content.find('
', last_import_or_docstring_end) + 1 # after the newline following the last import/docstring
                    if insert_point == 0: # If last import/docstring is on the last line
                        insert_point = len(content)
                
                # If no imports or docstrings, put at the very top (after shebang if any)
                if insert_point == 0 and content.startswith('#!'):
                    insert_point = content.find('
') + 1

                content = content[:insert_point] + '
logger = logging.getLogger(__name__)
' + content[insert_point:]


            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                
                # Re-stage the modified file
                run_command(f"git add {filepath}")
                logger.info(f"✅ Fixed and re-staged {filepath}")
                fixed_files_count += 1
            else:
                logger.info(f"No print() statements found or no changes needed in {filepath}.")

        except Exception as e:
            logger.error(f"❌ Failed to process {filepath}: {e}")
            # Do not re-raise, try to process other files
    
    logger.info(f"Finished fixing print() statements. Fixed {fixed_files_count} files.")
    return fixed_files_count > 0

if __name__ == "__main__":
    if fix_print_statements():
        logger.info("Some print() statements were fixed. Attempting to re-commit.")
    else:
        logger.info("No print() statements were fixed or an error occurred.")