"""Test script to verify webhook service connections"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def test_database_connection():
    """Test database connection"""
    print("Testing database connection...")
    try:
        from database import get_db, Person
        db = get_db()
        count = db.query(Person).count()
        db.close()
        print(f"✓ Database connected successfully ({count} persons in database)")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {str(e)}")
        return False


def test_rabbitmq_connection():
    """Test RabbitMQ connection"""
    print("\nTesting RabbitMQ connection...")
    try:
        from celery_client import celery_app
        # Try to connect
        conn = celery_app.connection()
        conn.connect()
        conn.close()
        print("✓ RabbitMQ connected successfully")
        return True
    except Exception as e:
        print(f"✗ RabbitMQ connection failed: {str(e)}")
        return False


def test_environment_variables():
    """Test required environment variables"""
    print("\nChecking environment variables...")
    required_vars = [
        'DATABASE_URL',
        'CELERY_BROKER_URL',
        'TOKEN_ENCRYPTION_KEY'
    ]

    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'PASSWORD' in var or 'KEY' in var or 'SECRET' in var:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"✓ {var} = {display_value}")
        else:
            print(f"✗ {var} is not set")
            all_present = False

    return all_present


def main():
    """Run all tests"""
    print("=" * 60)
    print("Gmail Webhook Service - Connection Test")
    print("=" * 60)

    env_ok = test_environment_variables()
    db_ok = test_database_connection()
    rabbitmq_ok = test_rabbitmq_connection()

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Environment Variables: {'✓ PASS' if env_ok else '✗ FAIL'}")
    print(f"Database Connection:   {'✓ PASS' if db_ok else '✗ FAIL'}")
    print(f"RabbitMQ Connection:   {'✓ PASS' if rabbitmq_ok else '✗ FAIL'}")

    if env_ok and db_ok and rabbitmq_ok:
        print("\n✓ All tests passed! Service is ready to run.")
        print("\nStart the service with:")
        print("  python main.py")
        return 0
    else:
        print("\n✗ Some tests failed. Fix issues before running service.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
