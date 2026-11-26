from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint
)

from sqlalchemy.orm import relationship

from database import Base


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(
        String(120),
        nullable=False
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    role = Column(
        String(30),
        nullable=False,
        default="student"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class LostReport(Base):

    __tablename__ = "lost_reports"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    title = Column(
        String(160),
        nullable=False
    )

    category = Column(
        String(80),
        nullable=False
    )

    brand = Column(String(100))

    model = Column(String(100))

    color = Column(String(80))

    lost_date = Column(String(30))

    lost_time = Column(String(30))

    location = Column(String(160))

    description = Column(Text)

    image_url = Column(Text)

    status = Column(
        String(50),
        default="SEARCHING",
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class FoundReport(Base):

    __tablename__ = "found_reports"

    id = Column(Integer, primary_key=True, index=True)

    finder_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    title = Column(
        String(160),
        nullable=False
    )

    category = Column(
        String(80),
        nullable=False
    )

    brand = Column(String(100))

    model = Column(String(100))

    color = Column(String(80))

    found_date = Column(String(30))

    found_time = Column(String(30))

    location = Column(String(160))

    description = Column(Text)

    image_url = Column(Text)

    status = Column(
        String(50),
        default="PROTECTED",
        nullable=False
    )

    privacy_until = Column(DateTime)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class Item(Base):

    __tablename__ = "items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    found_report_id = Column(
        Integer,
        ForeignKey("found_reports.id"),
        unique=True,
        nullable=False
    )

    item_code = Column(
        String(60),
        unique=True,
        nullable=False,
        index=True
    )

    storage_location = Column(
        String(160)
    )

    physical_status = Column(
        String(40),
        default="STORED"
    )


class Evidence(Base):

    __tablename__ = "evidence"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        nullable=False
    )

    evidence_type = Column(
        String(60),
        nullable=False
    )

    secret_value = Column(
        Text,
        nullable=False
    )

    base_weight = Column(
        Float,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )


class Match(Base):

    __tablename__ = "matches"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    lost_report_id = Column(
        Integer,
        ForeignKey("lost_reports.id"),
        nullable=False
    )

    found_report_id = Column(
        Integer,
        ForeignKey("found_reports.id"),
        nullable=False
    )

    score = Column(
        Float,
        nullable=False
    )

    status = Column(
        String(40),
        default="SUGGESTED"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "lost_report_id",
            "found_report_id",
            name="unique_lost_found_match"
        ),
    )


class Claim(Base):

    __tablename__ = "claims"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_code = Column(
        String(60),
        unique=True,
        nullable=False,
        index=True
    )

    claimant_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    lost_report_id = Column(
        Integer,
        ForeignKey("lost_reports.id"),
        nullable=False
    )

    found_report_id = Column(
        Integer,
        ForeignKey("found_reports.id"),
        nullable=False
    )

    status = Column(
        String(50),
        default="VERIFICATION_PENDING"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class VerificationResult(Base):

    __tablename__ = "verification_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False
    )

    evidence_id = Column(
        Integer,
        ForeignKey("evidence.id"),
        nullable=False
    )

    similarity = Column(
        Float,
        nullable=False
    )

    contribution = Column(
        Float,
        nullable=False
    )

    level = Column(
        String(30),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class PrivateMessage(Base):

    __tablename__ = "private_messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False
    )

    sender_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    message = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class Notification(Base):

    __tablename__ = "notifications"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(
        String(160),
        nullable=False
    )

    message = Column(
        Text,
        nullable=False
    )

    notification_type = Column(
        String(50),
        default="INFO"
    )

    is_read = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class Watch(Base):

    __tablename__ = "lost_watch"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    lost_report_id = Column(
        Integer,
        ForeignKey("lost_reports.id"),
        unique=True,
        nullable=False
    )

    active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    action = Column(
        String(100),
        nullable=False
    )

    entity_type = Column(
        String(60),
        nullable=False
    )

    entity_id = Column(Integer)

    details = Column(Text)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class VerificationAttempt(Base):
    __tablename__ = "verification_attempts"

    id = Column(Integer, primary_key=True, index=True)

    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False,
        index=True
    )

    score = Column(Float, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    code_hash = Column(String(255), nullable=False)

    expires_at = Column(DateTime, nullable=False)

    attempts = Column(Integer, default=0)

    used = Column(Boolean, default=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
