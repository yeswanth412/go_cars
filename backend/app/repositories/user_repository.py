"""User and Role Database Repository.

Encapsulates all direct database queries and transactional persistence
for User, Role, UserRole, and CustomerProfile entities.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.enums import RoleName
from app.models.user import User, Role, UserRole, CustomerProfile


class UserRepository:
    """Repository handling database operations for users and roles."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch user by primary key ID, eagerly loading their assigned roles."""
        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetch user by unique email, eagerly loading roles."""
        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == email.strip().lower())
        )
        return self.db.scalars(stmt).first()

    def get_by_phone(self, phone_number: str) -> Optional[User]:
        """Fetch user by unique phone number."""
        stmt = select(User).where(User.phone_number == phone_number.strip())
        return self.db.scalars(stmt).first()

    def get_role_by_name(self, name: str) -> Optional[Role]:
        """Fetch role record by unique role name."""
        stmt = select(Role).where(Role.name == name)
        return self.db.scalars(stmt).first()

    def ensure_default_roles(self) -> None:
        """Seed default roles (ADMIN, CUSTOMER, OWNER, DRIVER) if not present."""
        roles_data = [
            (1, RoleName.ADMIN.value, "Platform Administrator with full access"),
            (2, RoleName.CUSTOMER.value, "Standard customer renting self-drive and with-driver cars"),
            (3, RoleName.OWNER.value, "Car fleet owner listing vehicles on GoCars"),
            (4, RoleName.DRIVER.value, "Commercial driver providing driving services"),
        ]
        for role_id, name, desc in roles_data:
            existing = self.get_role_by_name(name)
            if not existing:
                new_role = Role(id=role_id, name=name, description=desc)
                self.db.add(new_role)
        self.db.flush()

    def create_user(
        self,
        full_name: str,
        email: str,
        phone_number: str,
        hashed_password: str,
        role_names: Optional[List[str]] = None,
    ) -> User:
        """Create user, assign roles, and initialize customer profile atomically.

        Args:
            full_name: User full name
            email: Lowercase normalized email
            phone_number: Contact phone
            hashed_password: Argon2 password hash
            role_names: List of initial roles (defaults to ['CUSTOMER'])

        Returns:
            The newly created User model instance.
        """
        if role_names is None:
            role_names = [RoleName.CUSTOMER.value]

        # Ensure lookup roles exist in DB
        self.ensure_default_roles()

        # 1. Create base user
        user = User(
            full_name=full_name,
            email=email.strip().lower(),
            phone_number=phone_number.strip(),
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        self.db.flush()  # Populates user.id

        # 2. Assign initial roles
        for r_name in role_names:
            role = self.get_role_by_name(r_name)
            if role:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                self.db.add(user_role)

        # 3. Create initial customer profile if CUSTOMER role is assigned
        if RoleName.CUSTOMER.value in role_names:
            customer_profile = CustomerProfile(user_id=user.id)
            self.db.add(customer_profile)

        self.db.flush()
        # Eagerly refresh user with roles
        return self.get_by_id(user.id) or user

    def add_role_to_user(self, user_id: UUID, role_name: str) -> bool:
        """Assign an additional role to an existing user if not already granted."""
        role = self.get_role_by_name(role_name)
        if not role:
            return False

        # Check if already assigned
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
        )
        existing_assignment = self.db.scalars(stmt).first()
        if existing_assignment:
            return True

        user_role = UserRole(user_id=user_id, role_id=role.id)
        self.db.add(user_role)
        self.db.flush()
        return True

    def remove_role_from_user(self, user_id: UUID, role_name: str) -> bool:
        """Revoke a role from a user. Returns True if removed, False if role wasn't assigned."""
        role = self.get_role_by_name(role_name)
        if not role:
            return False

        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
        )
        assignment = self.db.scalars(stmt).first()
        if not assignment:
            return False

        self.db.delete(assignment)
        self.db.flush()
        return True

    def count_active_admins(self) -> int:
        """Count total number of active users with the ADMIN role."""
        from sqlalchemy import func
        stmt = (
            select(func.count(User.id))
            .join(User.roles)
            .where(
                Role.name == RoleName.ADMIN.value,
                User.is_active.is_(True),
            )
        )
        return self.db.scalar(stmt) or 0

    def update_profile(
        self,
        user: User,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> User:
        """Update mutable profile fields for a user."""
        if full_name is not None:
            user.full_name = full_name
        if phone_number is not None:
            user.phone_number = phone_number
        self.db.flush()
        return user

    def update_status(self, user: User, is_active: bool) -> User:
        """Update account activation status."""
        user.is_active = is_active
        self.db.flush()
        return user

    def get_user_with_profiles(self, user_id: UUID) -> Optional[User]:
        """Fetch user by ID eagerly loading roles and all domain profiles."""
        stmt = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.customer_profile),
                selectinload(User.owner_profile),
                selectinload(User.driver_profile),
            )
            .where(User.id == user_id)
        )
        return self.db.scalars(stmt).first()

    def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        role_name: Optional[str] = None,
    ):
        """Paginated search and filter for users with eager-loaded relations."""
        from sqlalchemy import func, or_, distinct
        base_query = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.customer_profile),
                selectinload(User.owner_profile),
                selectinload(User.driver_profile),
            )
        )

        conditions = []
        if search:
            search_term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    User.full_name.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone_number.ilike(search_term),
                )
            )

        if is_active is not None:
            conditions.append(User.is_active == is_active)

        if role_name:
            conditions.append(User.roles.any(Role.name == role_name))

        if conditions:
            base_query = base_query.where(*conditions)

        # Count total matching users
        count_query = select(func.count(distinct(User.id)))
        if conditions:
            count_query = count_query.where(*conditions)
        if role_name:
            count_query = count_query.join(User.roles).where(Role.name == role_name)

        total = self.db.scalar(count_query) or 0

        # Pagination
        offset = (page - 1) * page_size
        stmt = base_query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())

        return items, total

