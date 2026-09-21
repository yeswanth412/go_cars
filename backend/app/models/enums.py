"""GoCars Domain Enums.

Defines all bounded domain choices used across models:
roles, fuel types, booking states, payment statuses, etc.
"""

from enum import Enum


class RoleName(str, Enum):
    """System roles supported in GoCars."""
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"
    OWNER = "OWNER"
    DRIVER = "DRIVER"


class FuelType(str, Enum):
    """Vehicle fuel options."""
    PETROL = "PETROL"
    DIESEL = "DIESEL"
    ELECTRIC = "ELECTRIC"
    HYBRID = "HYBRID"
    CNG = "CNG"


class TransmissionType(str, Enum):
    """Vehicle transmission options."""
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


class CarStatus(str, Enum):
    """Car listing and availability states."""
    PENDING_APPROVAL = "PENDING_APPROVAL"
    AVAILABLE = "AVAILABLE"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"


class DriverVerificationStatus(str, Enum):
    """Driver onboarding verification states."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class DriverDutyStatus(str, Enum):
    """Driver active duty availability."""
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    ON_TRIP = "ON_TRIP"


class DocumentType(str, Enum):
    """Vehicle legal compliance documents."""
    RC_BOOK = "RC_BOOK"
    INSURANCE = "INSURANCE"
    POLLUTION_CERTIFICATE = "POLLUTION_CERTIFICATE"
    FITNESS_CERTIFICATE = "FITNESS_CERTIFICATE"


class DocumentVerificationStatus(str, Enum):
    """Document approval lifecycle."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class BlackoutReason(str, Enum):
    """Reasons for car unavailability blocks."""
    MAINTENANCE = "MAINTENANCE"
    OWNER_USE = "OWNER_USE"
    LEGAL_INSPECTION = "LEGAL_INSPECTION"
    OTHER = "OTHER"


class BookingType(str, Enum):
    """Type of car booking."""
    SELF_DRIVE = "SELF_DRIVE"
    WITH_DRIVER = "WITH_DRIVER"


class RentalType(str, Enum):
    """Rental duration charging tier."""
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class BookingStatus(str, Enum):
    """Lifecycle states of a booking transaction."""
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PaymentMethod(str, Enum):
    """Payment channels."""
    MOCK_UPI = "MOCK_UPI"
    MOCK_CARD = "MOCK_CARD"
    MOCK_NETBANKING = "MOCK_NETBANKING"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    UPI = "UPI"
    NET_BANKING = "NET_BANKING"


class PaymentGateway(str, Enum):
    """Payment processor / gateway identifier."""
    MOCK = "MOCK"
    RAZORPAY = "RAZORPAY"
    STRIPE = "STRIPE"


class PaymentStatus(str, Enum):
    """Payment transaction states."""
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
