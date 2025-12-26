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


async def check_env_file():
    """Check if .env file exists and has Supabase config"""
    print("1. Checking .env file...")
    
    if not os.path.exists('.env'):
        print("   ✗ .env file NOT found")
        return False
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    has_supabase_url = 'SUPABASE_URL=' in env_content and 'supabase.co' in env_content
    has_database_url = 'DATABASE_URL=' in env_content
    is_postgres = 'postgresql' in env_content or 'postgres' in env_content
    
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
        
        async with AsyncSessionLocal() as db:
            # Test connection
            await db.execute(text("SELECT 1"))
            
            # Get database version
            result = await db.execute(text("SELECT version()"))
            version = result.scalar()
            
            is_postgres = 'PostgreSQL' in version
            
            print(f"   ✓ Database connection successful")
            print(f"   Type: {'PostgreSQL (Supabase)' if is_postgres else 'Unknown Database'}")
            
            if not is_postgres:
                print(f"   ✗ WARNING: Not using PostgreSQL/Supabase!")
                return False
            
            return True
            
    except Exception as e:
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
            
            print(f"   ✓ Found {len(tables)} tables")
            
            if missing_tables:
                print(f"   ✗ Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                print(f"   ✓ All {len(required_tables)} required tables exist")
                return True
                
    except Exception as e:
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
            
            has_data = any(count > 0 for count in counts.values())
            
            if has_data:
                print(f"   ✓ Data exists in database")
            else:
                print(f"   ✗ No data found - migration may be needed")
            
            return has_data
            
    except Exception as e:
        print(f"   ✗ Failed to check data: {e}")
        return False


async def main():
    print("=" * 60)
    print("Supabase Setup & Configuration Checker")
    print("=" * 60)
    
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
        
        return False
    
    # Check tables
    tables_ok = await check_tables()
    
    if not tables_ok:
        print("\n" + "=" * 60)
        print("SCHEMA INCOMPLETE")
        print("=" * 60)
        print("\nRun schema creation:")
        print("   python -c 'import asyncio; from database import create_tables; asyncio.run(create_tables())'")
        
        return False
    
    # Check data
    data_ok = await check_data()
    
    if not data_ok:
        print("\n" + "=" * 60)
        print("DATA MIGRATION NEEDED")
        print("=" * 60)
        print("\nImport data from migration files:")
        print("   psql 'your-connection-string' < migration_data/import.sql")
        
        return False
    
    # All checks passed
    print("\n" + "=" * 60)
    print("✓ SUPABASE FULLY CONFIGURED AND OPERATIONAL")
    print("=" * 60)
    
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

