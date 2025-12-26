#!/usr/bin/env python3
"""
Supabase Setup & Configuration Helper
Helps configure and test Supabase connection
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
import json

def log_debug(hypothesis_id: str, location: str, message: str, data: dict):
    """Write debug log entry"""
    log_entry = {
        "sessionId": "debug-session",
        "runId": "supabase-migration",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
    }
    with open('/Users/np1991/Desktop/country /.cursor/debug.log', 'a') as f:
        f.write(json.dumps(log_entry) + '\n')


async def check_env_file():
    """Check if .env file exists and has Supabase config"""
    print("1. Checking .env file...")
    log_debug("H1", "setup_supabase:check_env", "Checking environment file", {})
    
    if not os.path.exists('.env'):
        log_debug("H1", "setup_supabase:check_env", ".env file not found", {"exists": False})
        print("   ✗ .env file NOT found")
        return False
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    has_supabase_url = 'SUPABASE_URL=' in env_content and 'supabase.co' in env_content
    has_database_url = 'DATABASE_URL=' in env_content
    is_postgres = 'postgresql' in env_content or 'postgres' in env_content
    
    log_debug("H1", "setup_supabase:check_env", ".env file checked", {
        "exists": True,
        "has_supabase_url": has_supabase_url,
        "has_database_url": has_database_url,
        "is_postgres": is_postgres
    })
    
    print(f"   ✓ .env file exists")
    print(f"   {'✓' if has_supabase_url else '✗'} SUPABASE_URL configured")
    print(f"   {'✓' if has_database_url else '✗'} DATABASE_URL configured")
    print(f"   {'✓' if is_postgres else '✗'} Using PostgreSQL")
    
    return has_supabase_url and is_postgres


async def test_database_connection():
    """Test database connection"""
    print("\n2. Testing database connection...")
    
    try:
        from config import settings
        from database import AsyncSessionLocal
        from sqlalchemy import text
        
        log_debug("H1,H4", "setup_supabase:test_connection", "Testing database", {
            "database_url_masked": settings.database_url.split('@')[1] if '@' in settings.database_url else "local"
        })
        
        async with AsyncSessionLocal() as db:
            # Test connection
            await db.execute(text("SELECT 1"))
            
            # Get database version
            result = await db.execute(text("SELECT version()"))
            version = result.scalar()
            
            is_postgres = 'PostgreSQL' in version
            
            log_debug("H1,H4", "setup_supabase:test_connection", "Connection successful", {
                "is_postgres": is_postgres,
                "version": version[:50]
            })
            
            print(f"   ✓ Database connection successful")
            print(f"   Type: {'PostgreSQL (Supabase)' if is_postgres else 'Unknown Database'}")
            
            if not is_postgres:
                print(f"   ✗ WARNING: Not using PostgreSQL/Supabase!")
                log_debug("H1", "setup_supabase:test_connection", "Not using Supabase", {})
                return False
            
            return True
            
    except Exception as e:
        log_debug("H1,H4,H5", "setup_supabase:test_connection", "Connection failed", {
            "error": str(e),
            "error_type": type(e).__name__
        })
        print(f"   ✗ Connection failed: {e}")
        return False


async def check_tables():
    """Check if all required tables exist"""
    print("\n3. Checking database tables...")
    
    try:
        from database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # Get list of tables
            result = await db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            required_tables = [
                'sources', 'items', 'stories', 'story_items',
                'trends', 'alerts', 'competitors', 'competitor_hits',
                'briefs', 'jobs', 'awario_alerts', 'awario_mentions',
                'awario_insights', 'social_profiles', 'social_profile_metrics',
                'social_posts'
            ]
            
            missing_tables = [t for t in required_tables if t not in tables]
            
            log_debug("H2", "setup_supabase:check_tables", "Tables checked", {
                "total_tables": len(tables),
                "required_tables": len(required_tables),
                "missing_tables": missing_tables,
                "found_tables": tables
            })
            
            print(f"   ✓ Found {len(tables)} tables")
            
            if missing_tables:
                print(f"   ✗ Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                print(f"   ✓ All {len(required_tables)} required tables exist")
                return True
                
    except Exception as e:
        log_debug("H2", "setup_supabase:check_tables", "Table check failed", {
            "error": str(e),
            "error_type": type(e).__name__
        })
        print(f"   ✗ Failed to check tables: {e}")
        return False


async def check_data():
    """Check if data exists in key tables"""
    print("\n4. Checking data in tables...")
    
    try:
        from database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            key_tables = ['sources', 'items', 'stories', 'trends']
            counts = {}
            
            for table in key_tables:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                counts[table] = count
                print(f"   {table}: {count} rows")
            
            log_debug("H3", "setup_supabase:check_data", "Data counts", counts)
            
            has_data = any(count > 0 for count in counts.values())
            
            if has_data:
                print(f"   ✓ Data exists in database")
            else:
                print(f"   ✗ No data found - migration may be needed")
            
            return has_data
            
    except Exception as e:
        log_debug("H3", "setup_supabase:check_data", "Data check failed", {
            "error": str(e),
            "error_type": type(e).__name__
        })
        print(f"   ✗ Failed to check data: {e}")
        return False


async def main():
    print("=" * 60)
    print("Supabase Setup & Configuration Checker")
    print("=" * 60)
    
    log_debug("H1,H2,H3,H4,H5", "setup_supabase:main", "Starting Supabase setup check", {})
    
    # Check .env configuration
    env_ok = await check_env_file()
    
    if not env_ok:
        print("\n" + "=" * 60)
        print("CONFIGURATION NEEDED")
        print("=" * 60)
        print("\nYour Supabase is not configured. Follow these steps:\n")
        print("1. Go to: https://supabase.com/dashboard/project/mtzlucfhiijlilmvrkyf")
        print("2. Get your credentials:")
        print("   - Project Settings > API > service_role key")
        print("   - Project Settings > Database > Connection string")
        print("\n3. Update your .env file with:")
        print("   DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@...")
        print("   SUPABASE_URL=https://mtzlucfhiijlilmvrkyf.supabase.co")
        print("   SUPABASE_SERVICE_KEY=your-service-role-key")
        print("\n4. Run this script again to verify")
        
        log_debug("H1", "setup_supabase:main", "Configuration incomplete", {"env_ok": False})
        return False
    
    # Test connection
    conn_ok = await test_database_connection()
    
    if not conn_ok:
        print("\n" + "=" * 60)
        print("CONNECTION FAILED")
        print("=" * 60)
        print("\nCheck:")
        print("1. DATABASE_URL format is correct")
        print("2. Password is correct")
        print("3. Network can reach Supabase")
        print("4. IP is allowlisted in Supabase dashboard")
        
        log_debug("H4,H5", "setup_supabase:main", "Connection failed", {"conn_ok": False})
        return False
    
    # Check tables
    tables_ok = await check_tables()
    
    if not tables_ok:
        print("\n" + "=" * 60)
        print("SCHEMA INCOMPLETE")
        print("=" * 60)
        print("\nRun schema creation:")
        print("   python -c 'import asyncio; from database import create_tables; asyncio.run(create_tables())'")
        
        log_debug("H2", "setup_supabase:main", "Tables incomplete", {"tables_ok": False})
        return False
    
    # Check data
    data_ok = await check_data()
    
    if not data_ok:
        print("\n" + "=" * 60)
        print("DATA MIGRATION NEEDED")
        print("=" * 60)
        print("\nImport data from migration files:")
        print("   psql 'your-connection-string' < migration_data/import.sql")
        
        log_debug("H3", "setup_supabase:main", "No data found", {"data_ok": False})
        return False
    
    # All checks passed
    print("\n" + "=" * 60)
    print("✓ SUPABASE FULLY CONFIGURED AND OPERATIONAL")
    print("=" * 60)
    
    log_debug("H1,H2,H3,H4,H5", "setup_supabase:main", "All checks passed", {
        "env_ok": True,
        "conn_ok": True,
        "tables_ok": True,
        "data_ok": True
    })
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

