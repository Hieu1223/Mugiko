"""Firebase Admin provider for token verification."""
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from typing import Optional

from mugiko.common.config.config import settings
from mugiko.modules.core.user_management.provider.dtos import FirebaseUserInfo


class FirebaseProvider:
    """Firebase Admin SDK provider."""
    
    _initialized = False
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize Firebase Admin SDK."""
        if cls._initialized:
            return
        
        if not settings.firebase_project_id:
            raise ValueError("Firebase project ID not configured")
        
        if settings.firebase_credentials_path:
            cred = credentials.Certificate(settings.firebase_credentials_path)
        else:
            # Use default credentials (for Cloud Run, etc.)
            cred = credentials.ApplicationDefault()
        
        firebase_admin.initialize_app(cred, {
            'projectId': settings.firebase_project_id,
        })
        cls._initialized = True
    
    @classmethod
    def verify_id_token(cls, id_token: str) -> Optional[FirebaseUserInfo]:
        """Verify a Firebase ID token."""
        try:
            cls.initialize()
            decoded_token = firebase_auth.verify_id_token(id_token)
            return FirebaseUserInfo(
                uid=decoded_token.get('uid', ''),
                email=decoded_token.get('email'),
                email_verified=decoded_token.get('email_verified', False),
                name=decoded_token.get('name'),
                picture=decoded_token.get('picture'),
            )
        except Exception:
            return None