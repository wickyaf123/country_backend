#!/usr/bin/env python3
"""
Quick Supabase Setup - Non-Interactive Version
Prompts for credentials and updates .env automatically
"""

import os
import sys
from datetime import datetime
import getpass

def backup_env():
    """Backup existing .env file"""
    if os.path.exists('.env'):
        backup_name = f'.env.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        with open('.env', 'r') as f:
            content = f.read()
        with open(backup_name, 'w') as f:
            f.write(content)
        print(f"✓ Backed up .env to {backup_name}")
        return True
    return False

def read_env():
    """Read existing .env file"""
    if not os.path.exists('.env'):
        if os.path.exists('env.example'):
            with open('env.example', 'r') as f:
                return f.read()
        return ""
    
    with open('.env', 'r') as f:
        return f.read()

def update_env_var(content, key, value):
    """Update or add an environment variable"""
    lines = content.split('\n')
    updated = False
    new_lines = []
    
    for line in lines:
        if line.startswith(f'{key}='):
            new_lines.append(f'{key}={value}')
            updated = True
        else:
            new_lines.append(line)
    
    if not updated:
        new_lines.append(f'{key}={value}')
    
    return '\n'.join(new_lines)

def main():
    print("=" * 60)
    print("Supabase Quick Setup")
    print("=" * 60)
    print()
    print("This will update your .env file with Supabase credentials.")
    print("Get your credentials from:")
    print("https://supabase.com/dashboard/project/mtzlucfhiijlilmvrkyf/settings/api")
    print()
    
    # Get credentials
    print("Enter your Supabase DATABASE PASSWORD:")
    print("(from Settings > Database > Connection string)")
    db_password = getpass.getpass("Password: ")
    
    if not db_password:
        print("✗ Password cannot be empty")
        sys.exit(1)
    
    print()
    print("Enter your Supabase SERVICE_ROLE KEY:")
    print("(from Settings > API > service_role key)")
    service_key = getpass.getpass("Service Key: ")
    
    if not service_key:
        print("✗ Service key cannot be empty")
        sys.exit(1)
    
    print()
    print("Updating .env file...")
    
    # Backup existing .env
    backup_env()
    
    # Read current .env
    env_content = read_env()
    
    # Project details
    PROJECT_REF = "mtzlucfhiijlilmvrkyf"
    REGION = "aws-0-us-west-1"
    
    # Update DATABASE_URL
    database_url = f"postgresql+asyncpg://postgres.{PROJECT_REF}:{db_password}@{REGION}.pooler.supabase.com:6543/postgres"
    env_content = update_env_var(env_content, "DATABASE_URL", database_url)
    
    # Update SUPABASE_URL
    supabase_url = f"https://{PROJECT_REF}.supabase.co"
    env_content = update_env_var(env_content, "SUPABASE_URL", supabase_url)
    
    # Update SUPABASE_SERVICE_KEY
    env_content = update_env_var(env_content, "SUPABASE_SERVICE_KEY", service_key)
    
    # Write updated .env
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✓ .env file updated!")
    print()
    print("=" * 60)
    print("Testing connection...")
    print("=" * 60)
    print()
    
    # Test the connection
    import asyncio
    import subprocess
    result = subprocess.run([sys.executable, 'setup_supabase.py'], capture_output=False)
    
    if result.returncode == 0:
        print()
        print("=" * 60)
        print("✓ SUPABASE SUCCESSFULLY CONFIGURED!")
        print("=" * 60)
        print()
        print("You can now:")
        print("1. Start the backend: python main.py")
        print("2. All data will be stored in Supabase PostgreSQL")
        print("3. Continue with Stories/Items NLP processing fixes")
        return 0
    else:
        print()
        print("=" * 60)
        print("⚠ Configuration incomplete")
        print("=" * 60)
        print()
        print("Check the errors above.")
        print("Your credentials were saved, but connection test failed.")
        print()
        print("Common issues:")
        print("1. Wrong password - verify in Supabase dashboard")
        print("2. IP not allowlisted - add to Supabase > Database settings")
        print("3. Wrong region - verify your project region")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

