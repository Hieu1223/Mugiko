"""DTOs for the Firebase provider."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FirebaseUserInfo:
    """Firebase user info from verified token."""
    uid: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str]
    picture: Optional[str]