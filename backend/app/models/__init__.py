"""SQLAlchemy Models Package.

Exports all 13 core MVP domain models and their associated domain enums:
1. User
2. Role
3. UserRole
4. CustomerProfile
5. OwnerProfile
6. DriverProfile
7. Car
8. CarImage
9. CarDocument
10. CarBlackoutPeriod
11. Booking
12. Payment
13. Review
"""

from app.models.enums import (
    RoleName,
    FuelType,
    TransmissionType,
    CarStatus,
    DriverVerificationStatus,
    DriverDutyStatus,
    DocumentType,
    DocumentVerificationStatus,
    BlackoutReason,
    BookingType,
    RentalType,
    BookingStatus,
    PaymentMethod,
    PaymentGateway,
    PaymentStatus,
)
from app.models.user import (
    User,
    Role,
    UserRole,
    CustomerProfile,
    OwnerProfile,
    DriverProfile,
)
from app.models.car import (
    Car,
    CarImage,
    CarDocument,
    CarBlackoutPeriod,
)
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.review import Review

__all__ = [
    # Enums
    "RoleName",
    "FuelType",
    "TransmissionType",
    "CarStatus",
    "DriverVerificationStatus",
    "DriverDutyStatus",
    "DocumentType",
    "DocumentVerificationStatus",
    "BlackoutReason",
    "BookingType",
    "RentalType",
    "BookingStatus",
    "PaymentMethod",
    "PaymentGateway",
    "PaymentStatus",
    # Models
    "User",
    "Role",
    "UserRole",
    "CustomerProfile",
    "OwnerProfile",
    "DriverProfile",
    "Car",
    "CarImage",
    "CarDocument",
    "CarBlackoutPeriod",
    "Booking",
    "Payment",
    "Review",
]
