#!/usr/bin/env python3
import os
import sys
import subprocess
import getpass

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 60)
    print("   Sports Prediction Platform - Deployment Assistant")
    print("=" * 60)
    print()

def ask_input(prompt, default=None, is_secret=False):
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    if is_secret:
        value = getpass.getpass(full_prompt)
    else:
        value = input(full_prompt)
    
    if not value and default:
        return default
    return value

def generate_env_file(config):
    print("\n[+] Generating .env file...")
    
    env_content = f"""# Database Configuration
POSTGRES_USER={config['db_user']}
POSTGRES_PASSWORD={config['db_pass']}
POSTGRES_DB={config['db_name']}

# API Keys
ODDS_API_KEY={config['odds_api_key']}

# Optional: Twitter (for news scraping if implemented)
TWITTER_BEARER_TOKEN=
TWITTER_API_KEY=
TWITTER_API_SECRET=

# Optional: Betfair (for future use)
BETFAIR_APP_KEY={config.get('betfair_key', '')}
BETFAIR_USERNAME={config.get('betfair_user', '')}
BETFAIR_PASSWORD={config.get('betfair_pass', '')}

# Environment
ENVIRONMENT=production
"""
    with open(".env", "w") as f:
        f.write(env_content)
    
    # Also create backend/.env just in case, though docker-compose passes them
    with open("backend/.env", "w") as f:
        f.write(env_content)
        
    print("    .env created successfully.")

def check_docker():
    """Returns True if docker is running, False otherwise."""
    try:
        subprocess.check_output("docker ps", shell=True, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def run_local_setup():
    print("\n[+] Starting Local Setup...")
    
    if subprocess.call("docker --version", shell=True, stdout=subprocess.DEVNULL) != 0:
        print("\n[-] Error: Docker is not installed.")
        print("    Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        return

    if not check_docker():
        print("\n[-] Error: Docker daemon is not running.")
        print("    Please start Docker Desktop and try again.")
        return

    print("    Building and starting containers (this may take a few minutes)...")
    result = subprocess.call("docker-compose up --build -d", shell=True)
    
    if result == 0:
        print("\n[✓] Setup complete! App should be running at http://localhost:3000")
    else:
        print("\n[-] Docker Compose failed to start the containers.")

def run_remote_deploy(config):
    print("\n[+] Starting Remote Deployment to Raspberry Pi...")
    
    host = ask_input("Pi IP Address or Hostname")
    user = ask_input("Pi Username", "pi")
    target_dir = ask_input("Target Directory on Pi", "~/sports-model")
    
    remote = f"{user}@{host}"
    
    # 1. Create directory
    print(f"\n    Creating directory {target_dir} on {remote}...")
    ret = subprocess.call(f"ssh {remote} 'mkdir -p {target_dir}'", shell=True)
    if ret != 0:
        print("[-] Failed to connect via SSH. Ensure keys are set up or password access is allowed.")
        return

    # 2. Sync files
    print("    Syncing files (this may take a minute)...")
    # Exclude heavy/unnecessary folders
    exclude_flags = (
        "--exclude 'backend/venv' "
        "--exclude 'backend/__pycache__' "
        "--exclude 'frontend/node_modules' "
        "--exclude 'frontend/dist' "
        "--exclude '.git' "
        "--exclude '.DS_Store' "
        "--exclude 'tmp' "
    )
    
    rsync_cmd = f"rsync -avz --progress {exclude_flags} . {remote}:{target_dir}"
    ret = subprocess.call(rsync_cmd, shell=True)
    
    if ret != 0:
        print("[-] File transfer failed.")
        return

    # 3. Instructions
    print("\n[✓] Files transferred successfully!")
    print("\nTo finish setup, run the following commands on your Pi:")
    print("-" * 40)
    print(f"ssh {remote}")
    print(f"cd {target_dir}")
    print("# Verify .env exists and has your keys")
    print("docker-compose up --build -d")
    print("-" * 40)
    
    if ask_input("Do you want me to try running the docker command remotely now? (y/n)", "n").lower() == 'y':
        print("    Attempting to start containers remotely...")
        subprocess.call(f"ssh {remote} 'cd {target_dir} && docker-compose up --build -d'", shell=True)

def main():
    clear_screen()
    print_header()
    
    print("This script will help you configure and deploy the Sports Prediction Platform.\n")
    
    # 1. Configuration
    config = {}
    print("--- Configuration ---")
    config['odds_api_key'] = ask_input("Enter your Odds API Key (required)", is_secret=True)
    if not config['odds_api_key']:
        print("[-] Odds API Key is required to function.")
        return

    print("\n(Optional) Database Credentials [defaults are fine for Docker]")
    config['db_user'] = ask_input("Postgres User", "sports")
    config['db_pass'] = ask_input("Postgres Password", "sports_password")
    config['db_name'] = ask_input("Database Name", "sports_prediction")
    
    # 2. Generate Files
    generate_env_file(config)
    
    # 3. Choose Mode
    print("\n--- Deployment Mode ---")
    print("1. Run Locally (on this computer)")
    print("2. Deploy to Raspberry Pi (remote)")
    
    choice = ask_input("Select an option", "1")
    
    if choice == "1":
        run_local_setup()
    elif choice == "2":
        run_remote_deploy(config)
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
