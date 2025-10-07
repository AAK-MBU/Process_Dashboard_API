"""
Docker-compatible API key table migration script.

This script creates the api_key table and optionally creates a default API key.
Designed to run inside Docker containers.
"""

import os
import sys
from pathlib import Path

sys.path.append("/app")

from sqlmodel import Session, SQLModel

from app.db.database import engine
from app.models import ApiKey


def create_api_key_table():
    """Create the api_key table."""
    print("Creating api_key table...")

    try:
        # Create the table
        SQLModel.metadata.create_all(engine, tables=[ApiKey.__table__])
        print("api_key table created successfully!")
        return True
    except Exception as e:
        print(f"Failed to create api_key table: {e}")
        return False


def create_default_api_key():
    """Create a default API key for testing."""
    print("Creating default API key...")

    try:
        with Session(engine) as session:
            # Check if any API keys exist
            from sqlmodel import select

            statement = select(ApiKey)
            existing_keys = session.exec(statement).all()

            if existing_keys:
                print("API keys already exist, skipping default key creation")
                return True

            # Create default API key
            key = ApiKey.generate_key()
            key_hash = ApiKey.hash_key(key)

            api_key = ApiKey(
                name="Default API Key",
                description="Default API key for initial Docker setup",
                key_hash=key_hash,
                key_prefix=key[:8],
                is_active=True,
            )

            session.add(api_key)
            session.commit()
            session.refresh(api_key)

            print("Default API key created!")
            print(f"API Key: {key}")
            print(f"Key ID: {api_key.id}")
            print("")

            # Optionally write to a file for Docker logs
            key_file = Path("/tmp/api_key.txt")
            with open(key_file, "w") as f:
                f.write(f"API_KEY={key}\n")
                f.write(f"KEY_ID={api_key.id}\n")
            print(f"API key also saved to: {key_file}")

            return True

    except Exception as e:
        print(f"Failed to create default API key: {e}")
        return False


def main():
    """Run the migration."""
    print("Running API Key table migration in Docker...")
    print("")

    try:
        with Session(engine):
            pass
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

    if not create_api_key_table():
        return False

    skip_default = os.environ.get("SKIP_DEFAULT_API_KEY", "").lower() in ["true", "1", "yes"]
    if not skip_default:
        if not create_default_api_key():
            return False
    else:
        print("Skipping default API key creation (SKIP_DEFAULT_API_KEY=true)")

    print("")
    print("Migration completed successfully!")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
