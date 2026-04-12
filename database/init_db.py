import subprocess
import sys
import os

def run_script(script_name):
    print(f"--- Running {script_name} ---")
    try:
        # Get the absolute path of the script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(base_dir, script_name)
        
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
            print(f" {script_name} finished successfully.\n")
        else:
            print(f" {script_name} failed with error:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f" Error running {script_name}: {e}")
        return False
    return True

if __name__ == "__main__":
    scripts = [
        "bike_table_create.py",
        "weather_table_create.py",
        "user_table_create.py"
    ]
    
    print(" Starting Database Initialization...\n")
    for script in scripts:
        if not run_script(script):
            print(" Initialization stopped due to error.")
            sys.exit(1)
            
    print(" All database tables have been initialized successfully!")
