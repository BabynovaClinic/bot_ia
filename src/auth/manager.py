import json

from enum import Enum
from pathlib import Path
from logging import Logger
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

from src.config.settings import Settings, get_settings
from src.log.system_logger import Logger, get_system_logger


class UserRole(Enum):
    """
    Available user roles
    """
    ADMIN = "admin"
    MEDIC = "medic"
    USER = "user"
    GUEST = "guest"
    BANNED = "banned"


class Permission(Enum):
    """
    Permissions available in the system
    """
    ADMIN_COMMANDS = "admin_commands"
    FILE_SEARCH = "file_search"
    USE_ECHO = "use_echo"
    USE_LLM = "use_llm"
    USE_RAG = "use_rag"
    USE_SGC = "use_sgc"
    USE_REF = "use_ref"


ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        Permission.ADMIN_COMMANDS,
        Permission.FILE_SEARCH,
        Permission.USE_ECHO,
        Permission.USE_LLM,
        Permission.USE_RAG,
        Permission.USE_SGC,
        Permission.USE_REF,
    },
    UserRole.MEDIC: {
        Permission.FILE_SEARCH,
        Permission.USE_ECHO,
        Permission.USE_LLM,
        Permission.USE_RAG,
        Permission.USE_SGC,
        Permission.USE_REF,
    },
    UserRole.USER: {
        Permission.FILE_SEARCH,
        Permission.USE_ECHO,
        Permission.USE_LLM,
        Permission.USE_RAG,
        Permission.USE_SGC,
    },
    UserRole.GUEST: {
        Permission.USE_ECHO
    },
    UserRole.BANNED: set()
}


class AuthenticatedUser:
    """
    Represents an authenticated user within the system.
    """

    def __init__(self, user_id: str, name: str, email: str, role: UserRole, permissions: Set[Permission]):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.role = role
        self.permissions = permissions
        self.last_activity = datetime.now()

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def update_activity(self) -> None:
        self.last_activity = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role.value,
            "permissions": [p.value for p in self.permissions],
            "last_activity": self.last_activity.isoformat(),
        }


class AuthManager:
    """
    Authentication and authorization manager for MSBot.
    """

    def __init__(self, config_file: str = None):
        """
        Authentication and authorization manager for MSBot.

        Args:
            config_file (str): The path to the configuration file (fallback).
        """
        self.settings: Settings = get_settings()
        self.system_logger: Logger = get_system_logger(__name__)

        # 🚀 Preferir el secreto en Render si existe
        secret_path = Path("/etc/secrets/user_data.json")
        if secret_path.exists():
            self.config_file: Path = secret_path
        else:
            # fallback en desarrollo local
            self.config_file: Path = Path(config_file or "./data/user_data.json")

        self.authenticated_users: Dict[str, AuthenticatedUser] = {}
        self.authorized_users: Dict[str, Dict] = {}
        self.role_permissions: Dict[UserRole, Dict] = ROLE_PERMISSIONS
        self._load_config()

        self.system_logger.info("Authentication manager initialized")

    def _load_config(self) -> None:
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.authorized_users = config_data.get("authorized_users", {})
                    self.system_logger.info(f"Loaded {len(self.authorized_users)} authorized users")
            else:
                self._create_default_config()
        except Exception as e:
            self.system_logger.error(f"Error loading auth config: {e}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """
        Creates a default configuration file with a system admin.
        """
        default_admin_id = self.settings.default_admin_user_id
        default_admin_name = self.settings.default_admin_name
        default_admin_email = self.settings.default_admin_email

        if default_admin_id:
            self.authorized_users = {
                default_admin_id: {
                    "name": default_admin_name,
                    "email": default_admin_email,
                    "role": UserRole.ADMIN.value,
                    "added_date": datetime.now().isoformat(),
                    "added_by": "system"
                }
            }
        else:
            self.authorized_users = {}

        # 🚫 OJO: no sobreescribimos el secreto en Render
        if "secrets" not in str(self.config_file):
            self._save_config()

        self.system_logger.info("Created default auth configuration")

    def _save_config(self) -> None:
        """
        Saves the current user configuration to a file.
        """
        try:
            config_data = {
                "authorized_users": self.authorized_users,
                "last_updated": datetime.now().isoformat()
            }

            # 🚫 Nunca escribir sobre el secreto en Render
            if "secrets" not in str(self.config_file):
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.system_logger.info("Auth configuration saved")
        except Exception as e:
            self.system_logger.error(f"Error saving auth config: {e}")

    def authenticate_user(self, user_id: str, user_name: str = None, user_email: str = None) -> Optional[AuthenticatedUser]:
        if user_id not in self.authorized_users:
            self.system_logger.warning(f"Unauthorized access attempt by user {user_id} ({user_name})")
            return None

        user_config = self.authorized_users[user_id]
        role = UserRole(user_config["role"])

        if role == UserRole.BANNED:
            self.system_logger.warning(f"Banned user attempted access: {user_id}")
            return None

        permissions = self.role_permissions.get(role, set())

        auth_user = AuthenticatedUser(
            user_id=user_id,
            name=user_name or user_config.get("name", ""),
            email=user_email or user_config.get("email", ""),
            role=role,
            permissions=permissions
        )

        self.authenticated_users[user_id] = auth_user
        auth_user.update_activity()

        return auth_user

    def get_authenticated_user(self, user_id: str) -> Optional[AuthenticatedUser]:
        return self.authenticated_users.get(user_id)

    def is_user_authorized(self, user_id: str, permission: Permission) -> bool:
        auth_user = self.get_authenticated_user(user_id)
        if not auth_user:
            return False
        if not auth_user.has_permission(permission):
            return False
        auth_user.update_activity()
        return True

    def add_authorized_user(self, user_id: str, name: str, email: str, role: UserRole, added_by: str = "admin") -> bool:
        try:
            self.authorized_users[user_id] = {
                "name": name,
                "email": email,
                "role": role.value,
                "added_date": datetime.now().isoformat(),
                "added_by": added_by
            }

            self._save_config()
            self.system_logger.info(f"Added authorized user: {user_id} ({name}) as {role.value} by {added_by}")
            return True
        except Exception as e:
            self.system_logger.error(f"Error adding user {user_id}: {e}")
            return False

    def remove_authorized_user(self, user_id: str, removed_by: str = "admin") -> bool:
        try:
            if user_id in self.authorized_users:
                user_name = self.authorized_users[user_id].get("name", "Unknown")
                del self.authorized_users[user_id]

                if user_id in self.authenticated_users:
                    del self.authenticated_users[user_id]

                self._save_config()
                self.system_logger.info(f"Removed user: {user_id} ({user_name}) by {removed_by}")
                return True
            else:
                self.system_logger.warning(f"Attempted to remove non-existent user: {user_id}")
                return False
        except Exception as e:
            self.system_logger.error(f"Error removing user {user_id}: {e}")
            return False

    def update_user_role(self, user_id: str, new_role: UserRole, updated_by: str = "admin") -> bool:
        try:
            if user_id not in self.authorized_users:
                self.system_logger.error(f"Cannot update role: user {user_id} not found")
                return False

            old_role = self.authorized_users[user_id]["role"]
            self.authorized_users[user_id]["role"] = new_role.value
            self.authorized_users[user_id]["last_updated"] = datetime.now().isoformat()
            self.authorized_users[user_id]["updated_by"] = updated_by

            if user_id in self.authenticated_users:
                auth_user = self.authenticated_users[user_id]
                auth_user.role = new_role
                auth_user.permissions = self.role_permissions.get(new_role, set())

            self._save_config()
            self.system_logger.info(f"Updated user {user_id} role from {old_role} to {new_role.value}")
            return True
        except Exception as e:
            self.system_logger.error(f"Error updating user role {user_id}: {e}")
            return False

    def cleanup_inactive_sessions(self, timeout_hours: int = 24) -> int:
        cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
        inactive_users = []

        for user_id, auth_user in list(self.authenticated_users.items()):
            if auth_user.last_activity < cutoff_time:
                inactive_users.append(user_id)

        for user_id in inactive_users:
            del self.authenticated_users[user_id]
            self.system_logger.info(f"Cleaned up inactive session for user {user_id}")

        return len(inactive_users)

    def export_users(self) -> Dict:
        return {
            "authorized_users": self.authorized_users,
            "export_date": datetime.now().isoformat(),
            "total_users": len(self.authorized_users)
        }

    def import_users(self, user_data: Dict, imported_by: str = "admin") -> bool:
        try:
            if "authorized_users" in user_data:
                self.authorized_users.update(user_data["authorized_users"])
                self._save_config()
                self.system_logger.info(f"Imported {len(user_data['authorized_users'])} users by {imported_by}")
                return True
            return False
        except Exception as e:
            self.system_logger.error(f"Error importing users: {e}")
            return False
