"""
Security service for logging user security events
"""

from sqlalchemy.orm import Session
from fastapi import Request
from app.models.user import SecurityEvent, SecurityEventType
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for IP from forwarded headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    forwarded = request.headers.get("X-Forwarded")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback to client address
    if request.client and request.client.host:
        return request.client.host

    return "unknown"

def get_device_info(request: Request) -> str:
    """Extract device information from user agent"""
    user_agent = request.headers.get("User-Agent", "")

    # Simple device detection based on user agent
    user_agent_lower = user_agent.lower()

    if "mobile" in user_agent_lower or "android" in user_agent_lower or "iphone" in user_agent_lower:
        return "mobile"
    elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
        return "tablet"
    elif "windows" in user_agent_lower or "macintosh" in user_agent_lower or "linux" in user_agent_lower:
        return "desktop"
    else:
        return "unknown"

def log_security_event(
    db: Session,
    user_id: int,
    event_type: SecurityEventType,
    request: Request,
    additional_metadata: dict = None
) -> SecurityEvent:
    """
    Log a security event for a user

    Args:
        db: Database session
        user_id: User ID
        event_type: Type of security event
        request: FastAPI request object
        additional_metadata: Additional metadata to store

    Returns:
        Created SecurityEvent instance
    """
    try:
        # Extract information from request
        ip_address = get_client_ip(request)
        device_info = get_device_info(request)
        user_agent = request.headers.get("User-Agent", "")

        # Prepare metadata
        metadata = {
            "endpoint": str(request.url),
            "method": request.method,
        }

        if additional_metadata:
            metadata.update(additional_metadata)

        # Create security event
        event_value = event_type.value if isinstance(event_type, SecurityEventType) else str(event_type)

        security_event = SecurityEvent(
            user_id=user_id,
            event_type=event_value,
            ip_address=ip_address,
            device_info=device_info,
            user_agent=user_agent,
            event_metadata=metadata,
            created_at=datetime.utcnow()
        )

        db.add(security_event)
        db.commit()
        db.refresh(security_event)

        logger.info(f"Security event logged: {event_value} for user {user_id} from IP {ip_address}")

        return security_event

    except Exception as e:
        logger.error(f"Failed to log security event: {e}")
        db.rollback()
        # Don't raise exception to avoid breaking the main flow
        return None

def log_login_event(db: Session, user_id: int, request: Request, success: bool = True) -> SecurityEvent:
    """Log a login event"""
    event_type = SecurityEventType.LOGIN if success else SecurityEventType.FAILED_LOGIN
    metadata = {"success": success}
    return log_security_event(db, user_id, event_type, request, metadata)

def log_logout_event(db: Session, user_id: int, request: Request) -> SecurityEvent:
    """Log a logout event"""
    return log_security_event(db, user_id, SecurityEventType.LOGOUT, request)

def log_password_change_event(db: Session, user_id: int, request: Request) -> SecurityEvent:
    """Log a password change event"""
    return log_security_event(db, user_id, SecurityEventType.PASSWORD_CHANGE, request)
