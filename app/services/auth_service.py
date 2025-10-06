"""Business logic for authentication and API key management."""

from datetime import datetime

from sqlmodel import Session, select

from app.core.exceptions import AuthenticationError, ResourceNotFoundError
from app.models import ApiKey, ApiKeyCreate, ApiKeyWithSecret
from app.utils.datetime_utils import ensure_utc_aware, utc_now


class AuthService:
    """Service for managing API keys and authentication."""

    def __init__(self, db: Session):
        self.db = db

    def create_api_key(self, api_key_data: ApiKeyCreate) -> ApiKeyWithSecret:
        """
        Create a new API key.

        The generated key is only returned once and should be stored securely.

        Args:
            api_key_data: API key creation data

        Returns:
            ApiKeyWithSecret containing the generated key (only shown once)
        """
        # Generate the actual key
        key = ApiKey.generate_key()
        key_hash = ApiKey.hash_key(key)
        key_prefix = key[:8]

        # Create the database record
        api_key = ApiKey(
            **api_key_data.model_dump(),
            key_hash=key_hash,
            key_prefix=key_prefix,
        )

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        # Return with the actual key (only time it's shown)
        return ApiKeyWithSecret(**api_key.model_dump(), key=key)

    def verify_api_key(self, key: str) -> ApiKey:
        """
        Verify an API key and update usage statistics.

        Args:
            key: The API key to verify

        Returns:
            ApiKey object if valid

        Raises:
            AuthenticationError: If key is invalid or expired
        """
        key_hash = ApiKey.hash_key(key)

        statement = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        api_key = self.db.exec(statement).first()

        if not api_key:
            raise AuthenticationError("Invalid API key")

        # Check expiration
        if api_key.expires_at:
            expires_at = ensure_utc_aware(api_key.expires_at)
            if expires_at < utc_now():
                raise AuthenticationError("API key has expired")

        # Update usage statistics
        api_key.last_used_at = utc_now()
        api_key.usage_count += 1
        self.db.add(api_key)
        self.db.commit()

        return api_key

    def get_api_key(self, api_key_id: int) -> ApiKey:
        """
        Get an API key by ID.

        Args:
            api_key_id: ID of the API key

        Returns:
            ApiKey object

        Raises:
            ResourceNotFoundError: If API key doesn't exist
        """
        api_key = self.db.get(ApiKey, api_key_id)
        if not api_key:
            raise ResourceNotFoundError("API key", api_key_id)
        return api_key

    def list_api_keys(
        self, include_inactive: bool = False, skip: int = 0, limit: int = 100
    ) -> list[ApiKey]:
        """
        List all API keys.

        Args:
            include_inactive: Whether to include inactive keys
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ApiKey objects
        """
        statement = select(ApiKey)

        if not include_inactive:
            statement = statement.where(ApiKey.is_active == True)

        statement = statement.offset(skip).limit(limit)
        api_keys = self.db.exec(statement).all()
        return list(api_keys)

    def toggle_api_key(self, api_key_id: int) -> ApiKey:
        """
        Toggle the active status of an API key.

        Args:
            api_key_id: ID of the API key to toggle

        Returns:
            Updated ApiKey object

        Raises:
            ResourceNotFoundError: If API key doesn't exist
        """
        api_key = self.get_api_key(api_key_id)
        api_key.is_active = not api_key.is_active

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def delete_api_key(self, api_key_id: int) -> None:
        """
        Delete an API key permanently.

        Args:
            api_key_id: ID of the API key to delete

        Raises:
            ResourceNotFoundError: If API key doesn't exist
        """
        api_key = self.get_api_key(api_key_id)
        self.db.delete(api_key)
        self.db.commit()

    def update_api_key(
        self, api_key_id: int, name: str | None = None, description: str | None = None
    ) -> ApiKey:
        """
        Update API key metadata.

        Args:
            api_key_id: ID of the API key to update
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated ApiKey object

        Raises:
            ResourceNotFoundError: If API key doesn't exist
        """
        api_key = self.get_api_key(api_key_id)

        if name is not None:
            api_key.name = name
        if description is not None:
            api_key.description = description

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def get_usage_stats(self, api_key_id: int) -> dict:
        """
        Get usage statistics for an API key.

        Args:
            api_key_id: ID of the API key

        Returns:
            Dictionary with usage statistics

        Raises:
            ResourceNotFoundError: If API key doesn't exist
        """
        api_key = self.get_api_key(api_key_id)

        return {
            "key_id": api_key.id,
            "name": api_key.name,
            "role": api_key.role,
            "total_usage_count": api_key.usage_count,
            "last_used_at": api_key.last_used_at,
            "created_at": api_key.created_at,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at,
            "days_until_expiration": self._calculate_days_until_expiration(api_key.expires_at),
        }

    def _calculate_days_until_expiration(self, expires_at: datetime | None) -> int | None:
        """Calculate days until API key expiration."""
        if not expires_at:
            return None

        expires_at = ensure_utc_aware(expires_at)
        now = utc_now()
        if expires_at < now:
            return 0  # Already expired

        delta = expires_at - now
        return delta.days

    def revoke_expired_keys(self) -> int:
        """
        Automatically revoke all expired API keys.

        Returns:
            Number of keys revoked
        """
        now = utc_now()
        statement = select(ApiKey).where(ApiKey.is_active == True, ApiKey.expires_at < now)

        expired_keys = self.db.exec(statement).all()
        count = 0

        for key in expired_keys:
            key.is_active = False
            self.db.add(key)
            count += 1

        if count > 0:
            self.db.commit()

        return count
