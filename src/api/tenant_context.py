"""
Tenant Context Dependency for FastAPI.

Provides dependency injection for multi-retailer tenant scoping via the `X-Retailer-ID` header
for local development and testing.

SECURITY NOTICE:
This header-based tenant context is strictly for local development and testing tenant identification.
It is NOT production authentication or authorization. Callers must implement robust OAuth/JWT
authentication in production environments. The extracted retail_id must never be used directly
to construct filesystem paths or database names.
"""

from fastapi import Header, HTTPException, status
from typing import Optional
from src.models.canonical_schemas import validate_retail_id, RETAIL_ID_REGEX


def get_current_retailer_id(
    x_retailer_id: Optional[str] = Header(None, alias="X-Retailer-ID")
) -> str:
    """
    FastAPI dependency that extracts and validates the `X-Retailer-ID` header.
    Raises 400 Bad Request if missing or invalid.
    """
    if not x_retailer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Retailer-ID' header for tenant-scoped request.",
        )
    
    try:
        validate_retail_id(x_retailer_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid 'X-Retailer-ID' header format: {str(e)}",
        )
    
    return x_retailer_id
