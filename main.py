from datetime import datetime, timedelta
import os

from dotenv import load_dotenv

from fastapi import (
    Depends,
    FastAPI,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import BackgroundTasks
import secrets
from model import PasswordReset, VerificationAttempt
from schemas import ForgotRequest, ResetRequest, ChangePassword
from emailer import send_email, send_email_async

from sqlalchemy.orm import Session

from database import (
    Base,
    engine,
    get_db
)

from model import (
    User,
    LostReport,
    FoundReport,
    Item,
    Evidence,
    Match,
    Claim,
    VerificationResult,
    PrivateMessage,
    Notification,
    Watch,
    AuditLog
)

from schemas import (
    RegisterRequest,
    LoginRequest,
    LostCreate,
    FoundCreate,
    ClaimCreate,
    MessageCreate,
    EvidenceCreate,
    VerifyRequest,
    AdminItemCreate,
    ClaimDecision
)

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin
)

from matching import calculate_match

from verification import (
    generate_question,
    verify_ownership
)


load_dotenv()


app = FastAPI(
    title="Intelligent College Lost & Found Portal",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        x.strip()
        for x in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",")
        if x.strip()
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "60"))
MAX_VERIFY_ATTEMPTS = 3


@app.on_event("startup")
def startup():

    Base.metadata.create_all(
        bind=engine
    )


# ------------------------------------------------
# HELPERS
# ------------------------------------------------

def notify(
    db,
    user_id,
    title,
    message,
    notification_type="INFO"
):

    _target = db.get(User, user_id)
    if _target and _target.email:
        send_email_async(_target.email, f"CampusFind: {title}", message)

    db.add(
        Notification(

            user_id=user_id,

            title=title,

            message=message,

            notification_type=
                notification_type

        )
    )


def audit(
    db,
    user_id,
    action,
    entity_type,
    entity_id=None,
    details=None
):

    db.add(
        AuditLog(

            user_id=user_id,

            action=action,

            entity_type=entity_type,

            entity_id=entity_id,

            details=details

        )
    )


def safe_lost(report):

    return {

        "id": report.id,

        "title": report.title,

        "category": report.category,

        "brand": report.brand,

        "model": report.model,

        "color": report.color,

        "lost_date": report.lost_date,

        "lost_time": report.lost_time,

        "location": report.location,

        "description": report.description,

        "image_url": report.image_url,

        "status": report.status,

        "created_at": report.created_at

    }


def safe_found(report):

    # Important:
    # Full found details are NOT exposed.

    return {

        "id": report.id,

        "category": report.category,

        "color": report.color,

        "found_date": report.found_date,

        "location": report.location,

        "status": report.status,

        "created_at": report.created_at

    }


# ------------------------------------------------
# HEALTH
# ------------------------------------------------

def own_found(report, db):
    item = (
        db.query(Item)
        .filter(Item.found_report_id == report.id)
        .first()
    )
    data = safe_found(report)
    data.update({
        "title": report.title,
        "image_url": report.image_url,
        "approved": bool(item),
        "item_id": item.id if item else None,
        "item_code": item.item_code if item else None
    })
    return data


@app.get("/health")
def health():

    return {

        "status": "ok",

        "message":
            "Lost & Found backend is running"

    }


# ------------------------------------------------
# REGISTER
# ------------------------------------------------

@app.post("/auth/register")
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):

    email = str(
        data.email
    ).lower().strip()

    existing = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    admin_emails = {

        x.strip().lower()

        for x in os.getenv(
            "ADMIN_EMAILS",
            ""
        ).split(",")

        if x.strip()

    }

    role = (
        "admin"
        if email in admin_emails
        else "student"
    )

    user = User(

        full_name=data.full_name.strip(),

        email=email,

        password_hash=
            hash_password(data.password),

        role=role

    )

    db.add(user)

    db.commit()

    db.refresh(user)

    token = create_access_token(
        user.id,
        user.role
    )

    return {

        "access_token": token,

        "token_type": "bearer",

        "user": {

            "id": user.id,

            "full_name":
                user.full_name,

            "email":
                user.email,

            "role":
                user.role

        }

    }


# ------------------------------------------------
# LOGIN
# ------------------------------------------------

@app.post("/auth/forgot")
def forgot_password(
    data: ForgotRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    email = str(data.email).lower().strip()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user:
        code = f"{secrets.randbelow(1000000):06d}"

        db.query(PasswordReset).filter(
            PasswordReset.user_id == user.id,
            PasswordReset.used == False
        ).update({"used": True})

        db.add(
            PasswordReset(
                user_id=user.id,
                code_hash=hash_password(code),
                expires_at=(
                    datetime.utcnow()
                    + timedelta(minutes=10)
                )
            )
        )

        db.commit()

        background.add_task(
            send_email,
            user.email,
            "Your CampusFind reset code",
            f"Your password reset code is {code}. "
            "It expires in 10 minutes. "
            "If you did not ask for it, ignore this email."
        )

    # same answer whether or not the email exists
    return {
        "message":
            "If that email is registered, a reset code has been sent."
    }


@app.post("/auth/reset")
def reset_password(
    data: ResetRequest,
    db: Session = Depends(get_db)
):
    email = str(data.email).lower().strip()

    bad = HTTPException(
        status_code=400,
        detail="Wrong or expired code"
    )

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise bad

    record = (
        db.query(PasswordReset)
        .filter(
            PasswordReset.user_id == user.id,
            PasswordReset.used == False
        )
        .order_by(PasswordReset.id.desc())
        .first()
    )

    if not record or record.expires_at < datetime.utcnow():
        raise bad

    if not verify_password(data.code.strip(), record.code_hash):
        record.attempts = (record.attempts or 0) + 1
        if record.attempts >= 5:
            record.used = True
        db.commit()
        raise bad

    user.password_hash = hash_password(data.new_password)
    record.used = True

    audit(db, user.id, "PASSWORD_RESET", "user", user.id, None)

    db.commit()

    return {"message": "Password updated"}


@app.post("/auth/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    email = str(
        data.email
    ).lower().strip()

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        data.password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {

        "access_token":
            create_access_token(
                user.id,
                user.role
            ),

        "token_type":
            "bearer",

        "user": {

            "id": user.id,

            "full_name":
                user.full_name,

            "email":
                user.email,

            "role":
                user.role

        }

    }


# ------------------------------------------------
# CURRENT USER
# ------------------------------------------------

@app.get("/auth/me")
def me(
    user=Depends(get_current_user)
):

    return {

        "id": user.id,

        "full_name":
            user.full_name,

        "email":
            user.email,

        "role":
            user.role

    }


# ------------------------------------------------
# CREATE LOST REPORT
# ------------------------------------------------

@app.post("/auth/change-password")
def change_password(
    data: ChangePassword,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    if not verify_password(
        data.current_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is wrong"
        )

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=400,
            detail="Choose a password different from the current one"
        )

    user.password_hash = hash_password(
        data.new_password
    )
    db.commit()

    return {"message": "Password changed"}


@app.post("/lost")
def create_lost(

    data: LostCreate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    report = LostReport(

        user_id=user.id,

        title=data.title,

        category=data.category,

        brand=data.brand,

        model=data.model,

        color=data.color,

        lost_date=data.lost_date,

        lost_time=data.lost_time,

        location=data.location,

        description=data.description,

        image_url=data.image_url,

        status="SEARCHING"

    )

    db.add(report)

    db.flush()

    # Smart Lost Watch

    db.add(
        Watch(
            lost_report_id=report.id,
            active=True
        )
    )

    best_score = 0

    # Search existing found reports

    found_reports = (
        db.query(FoundReport)
        .all()
    )

    for found in found_reports:

        score, details = calculate_match(
            report,
            found
        )

        if score >= MATCH_THRESHOLD:

            match = (
                db.query(Match)
                .filter(
                    Match.lost_report_id
                    == report.id,

                    Match.found_report_id
                    == found.id
                )
                .first()
            )

            if not match:

                match = Match(

                    lost_report_id=
                        report.id,

                    found_report_id=
                        found.id,

                    score=score,

                    status="SUGGESTED"

                )

                db.add(match)

            report.status = "MATCHED"

            found.status = "MATCHED"

            notify(

                db,

                user.id,

                "Possible match found",

                f"Found item may match Lost Report #{report.id}. Confidence: {score}%.",

                "MATCH"

            )

        best_score = max(
            best_score,
            score
        )

    if best_score < MATCH_THRESHOLD:

        report.status = "SMART_LOST_WATCH"

    audit(

        db,

        user.id,

        "CREATE_LOST_REPORT",

        "lost_report",

        report.id

    )

    db.commit()

    db.refresh(report)

    return {

        "message":
            "Lost report created",

        "report":
            safe_lost(report),

        "best_match_score":
            best_score,

        "status":
            report.status

    }


# ------------------------------------------------
# MY LOST REPORTS
# ------------------------------------------------

@app.get("/lost")
def get_my_lost(

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    reports = (

        db.query(LostReport)

        .filter(
            LostReport.user_id
            == user.id
        )

        .order_by(
            LostReport.created_at.desc()
        )

        .all()

    )

    return [
        safe_lost(x)
        for x in reports
    ]


# ------------------------------------------------
# CREATE FOUND REPORT
# ------------------------------------------------

@app.post("/found")
def create_found(

    data: FoundCreate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    report = FoundReport(

        finder_id=user.id,

        title=data.title,

        category=data.category,

        brand=data.brand,

        model=data.model,

        color=data.color,

        found_date=data.found_date,

        found_time=data.found_time,

        location=data.location,

        description=data.description,

        image_url=data.image_url,

        status="PROTECTED",

        privacy_until=
            datetime.utcnow()
            + timedelta(hours=48)

    )

    db.add(report)

    db.flush()

    # Search old lost reports

    lost_reports = (

        db.query(LostReport)

        .filter(

            LostReport.status.in_(
                [
                    "SEARCHING",
                    "SMART_LOST_WATCH"
                ]
            )

        )

        .all()

    )

    best_score = 0

    for lost in lost_reports:

        score, details = calculate_match(
            lost,
            report
        )

        best_score = max(
            best_score,
            score
        )

        if score >= MATCH_THRESHOLD:

            existing = (

                db.query(Match)

                .filter(

                    Match.lost_report_id
                    == lost.id,

                    Match.found_report_id
                    == report.id

                )

                .first()

            )

            if not existing:

                db.add(

                    Match(

                        lost_report_id=
                            lost.id,

                        found_report_id=
                            report.id,

                        score=score,

                        status="SUGGESTED"

                    )

                )

            lost.status = "MATCHED"

            report.status = "MATCHED"

            notify(

                db,

                lost.user_id,

                "Possible match found",

                f"A newly found item may match your Lost Report #{lost.id}. Confidence: {score}%.",

                "MATCH"

            )

    audit(

        db,

        user.id,

        "CREATE_FOUND_REPORT",

        "found_report",

        report.id

    )

    db.commit()

    db.refresh(report)

    return {

        "message":
            "Found report created",

        "found_report":
            safe_found(report),

        "best_match_score":
            best_score,

        "privacy_shield_hours":
            48

    }


# ------------------------------------------------
# MY FOUND REPORTS
# ------------------------------------------------

@app.get("/found")
def get_my_found(

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    reports = (

        db.query(FoundReport)

        .filter(
            FoundReport.finder_id
            == user.id
        )

        .order_by(
            FoundReport.created_at.desc()
        )

        .all()

    )

    return [own_found(x, db) for x in reports]


# ------------------------------------------------
# SMART MATCHES
# ------------------------------------------------

@app.get("/matches")
def get_matches(

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    matches = (

        db.query(Match)

        .join(
            LostReport,
            Match.lost_report_id
            == LostReport.id
        )

        .join(Item, Item.found_report_id == Match.found_report_id)
        .filter(

            LostReport.user_id
            == user.id,

            Match.score
            >= MATCH_THRESHOLD

        )

        .order_by(
            Match.score.desc()
        )

        .all()

    )

    output = []

    for match in matches:

        lost = db.get(
            LostReport,
            match.lost_report_id
        )

        found = db.get(
            FoundReport,
            match.found_report_id
        )

        output.append({

            "match_id":
                match.id,

            "confidence":
                match.score,

            "status":
                match.status,

            "lost_report":
                safe_lost(lost),

            "found_item":
                safe_found(found)

        })

    return output


# ------------------------------------------------
# CLAIM
# ------------------------------------------------

@app.post("/claims")
def create_claim(

    data: ClaimCreate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    lost = db.get(
        LostReport,
        data.lost_report_id
    )

    found = db.get(
        FoundReport,
        data.found_report_id
    )

    if not lost or not found:

        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    if not db.query(Item).filter(
        Item.found_report_id == found.id
    ).first():
        raise HTTPException(
            status_code=400,
            detail="The admin has not approved this found item yet"
        )

    if lost.user_id != user.id:

        raise HTTPException(
            status_code=403,
            detail="This is not your lost report"
        )

    match = (

        db.query(Match)

        .filter(

            Match.lost_report_id
            == lost.id,

            Match.found_report_id
            == found.id,

            Match.score
            >= MATCH_THRESHOLD

        )

        .first()

    )

    # If coming from limited public notice,
    # allow claim only after privacy shield.

    if not match:

        if (
            found.privacy_until
            and found.privacy_until
            > datetime.utcnow()
        ):

            raise HTTPException(
                status_code=403,
                detail=
                    "Found item is still protected"
            )

    existing = (

        db.query(Claim)

        .filter(

            Claim.claimant_id
            == user.id,

            Claim.lost_report_id
            == lost.id,

            Claim.found_report_id
            == found.id,

            Claim.status
            != "REJECTED"

        )

        .first()

    )

    if existing:

        return {

            "message":
                "Claim already exists",

            "claim_id":
                existing.id,

            "claim_code":
                existing.claim_code

        }

    claim_code = (
        f"CLM-{datetime.utcnow().year}-"
        f"{lost.id:04d}-{secrets.token_hex(2).upper()}"
    )

    claim = Claim(

        claim_code=claim_code,

        claimant_id=user.id,

        lost_report_id=lost.id,

        found_report_id=found.id,

        status="VERIFICATION_PENDING"

    )

    db.add(claim)

    lost.status = "CLAIM_CREATED"

    audit(

        db,

        user.id,

        "CREATE_CLAIM",

        "claim",

        claim.id

    )

    db.commit()

    db.refresh(claim)

    return {

        "message":
            "Claim created. Private chat and verification are available.",

        "claim_id":
            claim.id,

        "claim_code":
            claim.claim_code,

        "status":
            claim.status

    }


# ------------------------------------------------
# MY CLAIMS
# ------------------------------------------------

@app.get("/claims")
def get_claims(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    claims = (
        db.query(Claim)
        .filter(Claim.claimant_id == user.id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    out = []
    for c in claims:
        lost = db.get(LostReport, c.lost_report_id)
        found = db.get(FoundReport, c.found_report_id)
        out.append({
            "id": c.id,
            "claim_code": c.claim_code,
            "status": c.status,
            "lost_report_id": c.lost_report_id,
            "found_report_id": c.found_report_id,
            "created_at": c.created_at,
            "lost_title": lost.title if lost else None,
            "item_category": found.category if found else None,
            "item_color": found.color if found else None
        })
    return out


def get_claim_for_user(

    claim_id,
    user,
    db

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    found = db.get(
        FoundReport,
        claim.found_report_id
    )

    allowed = {

        claim.claimant_id,

        found.finder_id

    }

    if user.id not in allowed:

        raise HTTPException(
            status_code=403,
            detail=
                "You are not a participant"
        )

    return claim


# ------------------------------------------------
# PRIVATE CHAT - SEND
# ------------------------------------------------

@app.post(
    "/claims/{claim_id}/messages"
)
def send_message(

    claim_id: int,

    data: MessageCreate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    claim = get_claim_for_user(
        claim_id,
        user,
        db
    )

    message = PrivateMessage(

        claim_id=claim.id,

        sender_id=user.id,

        message=data.message.strip()

    )

    db.add(message)

    audit(

        db,

        user.id,

        "SEND_PRIVATE_MESSAGE",

        "claim",

        claim.id

    )

    db.commit()

    db.refresh(message)

    return {

        "id":
            message.id,

        "claim_id":
            message.claim_id,

        "sender_id":
            message.sender_id,

        "message":
            message.message,

        "created_at":
            message.created_at

    }


# ------------------------------------------------
# PRIVATE CHAT - READ
# ------------------------------------------------

@app.get(
    "/claims/{claim_id}/messages"
)
def get_messages(

    claim_id: int,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    claim = get_claim_for_user(
        claim_id,
        user,
        db
    )

    messages = (

        db.query(PrivateMessage)

        .filter(
            PrivateMessage.claim_id
            == claim.id
        )

        .order_by(
            PrivateMessage.created_at.asc()
        )

        .all()

    )

    return [

        {

            "id":
                message.id,

            "sender_id":
                message.sender_id,

            "message":
                message.message,

            "created_at":
                message.created_at

        }

        for message in messages

    ]


# ------------------------------------------------
# VERIFICATION QUESTIONS
# ------------------------------------------------

@app.get(
    "/claims/{claim_id}/verification/questions"
)
def verification_questions(

    claim_id: int,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    if claim.claimant_id != user.id:

        raise HTTPException(
            status_code=403,
            detail="Only claimant can verify"
        )

    if claim.status not in (
        "VERIFICATION_PENDING",
        "ADDITIONAL_VERIFICATION_REQUIRED"
    ):
        raise HTTPException(
            status_code=400,
            detail="This claim can no longer be verified"
        )

    attempts_used = (
        db.query(VerificationAttempt)
        .filter(VerificationAttempt.claim_id == claim.id)
        .count()
    )

    if attempts_used >= MAX_VERIFY_ATTEMPTS:
        claim.status = "CLAIM_LOCKED"
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Too many attempts. Please contact the lost and found desk."
        )

    item = (

        db.query(Item)

        .filter(
            Item.found_report_id
            == claim.found_report_id
        )

        .first()

    )

    if not item:

        raise HTTPException(
            status_code=400,
            detail=
                "Admin has not registered the physical item"
        )

    evidences = (

        db.query(Evidence)

        .filter(

            Evidence.item_id
            == item.id,

            Evidence.is_active
            == True

        )

        .all()

    )

    return [

        {

            "evidence_id":
                evidence.id,

            "question":
                generate_question(
                    evidence.evidence_type
                )

        }

        for evidence in evidences

    ]


# ------------------------------------------------
# SUBMIT VERIFICATION
# ------------------------------------------------

@app.post(
    "/claims/{claim_id}/verify"
)
def verify_claim(

    claim_id: int,

    data: VerifyRequest,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    if claim.claimant_id != user.id:

        raise HTTPException(
            status_code=403,
            detail="Only claimant can verify"
        )

    item = (

        db.query(Item)

        .filter(
            Item.found_report_id
            == claim.found_report_id
        )

        .first()

    )

    if not item:

        raise HTTPException(
            status_code=400,
            detail="Physical item not registered"
        )

    evidences = (

        db.query(Evidence)

        .filter(

            Evidence.item_id
            == item.id,

            Evidence.is_active
            == True

        )

        .all()

    )

    result = verify_ownership(

        evidences,

        data.answers

    )

    # Delete old verification records

    db.query(
        VerificationResult
    ).filter(
        VerificationResult.claim_id
        == claim.id
    ).delete(
        synchronize_session=False
    )

    for detail in result["details"]:

        db.add(

            VerificationResult(

                claim_id=
                    claim.id,

                evidence_id=
                    detail["evidence_id"],

                similarity=
                    detail["similarity"],

                contribution=
                    detail["contribution"],

                level=
                    detail["level"]

            )

        )

    db.add(
        VerificationAttempt(
            claim_id=claim.id,
            score=result["score"]
        )
    )
    attempts_used += 1

    if result["status"] == "STRONG_EVIDENCE":
        claim.status = "ADMIN_REVIEW"
    elif attempts_used >= MAX_VERIFY_ATTEMPTS:
        claim.status = "CLAIM_LOCKED"
    else:
        claim.status = "ADDITIONAL_VERIFICATION_REQUIRED"

    audit(

        db,

        user.id,

        "OWNERSHIP_VERIFICATION",

        "claim",

        claim.id,

        f"score={result['score']}"

    )

    db.commit()

    return {

        "claim_id":
            claim.id,

        "score":
            result["score"],

        "status":
            result["status"],

        "details":
            result["details"],
        "claim_status": claim.status,
        "attempts_left": max(0, MAX_VERIFY_ATTEMPTS - attempts_used),

        "important":
            "Ownership score is not final proof. Admin must physically verify the item."

    }


# ------------------------------------------------
# NOTIFICATIONS
# ------------------------------------------------

@app.get("/notifications")
def get_notifications(

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    notifications = (

        db.query(Notification)

        .filter(
            Notification.user_id
            == user.id
        )

        .order_by(
            Notification.created_at.desc()
        )

        .limit(50)

        .all()

    )

    return [

        {

            "id":
                n.id,

            "title":
                n.title,

            "message":
                n.message,

            "type":
                n.notification_type,

            "is_read":
                n.is_read,

            "created_at":
                n.created_at

        }

        for n in notifications

    ]


# =================================================
# ADMIN
# =================================================

# ------------------------------------------------
# ADMIN REGISTER PHYSICAL ITEM
# ------------------------------------------------

@app.post("/admin/items")
def admin_create_item(

    data: AdminItemCreate,

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    found = db.get(
        FoundReport,
        data.found_report_id
    )

    if not found:

        raise HTTPException(
            status_code=404,
            detail="Found report not found"
        )

    existing = (

        db.query(Item)

        .filter(
            Item.found_report_id
            == found.id
        )

        .first()

    )

    if existing:

        return {

            "item_id":
                existing.id,

            "item_code":
                existing.item_code

        }

    item_code = (
        f"ITEM-{datetime.utcnow().year}-"
        f"{found.id:05d}"
    )

    item = Item(

        found_report_id=
            found.id,

        item_code=
            item_code,

        storage_location=
            data.storage_location,

        physical_status=
            "STORED"

    )

    db.add(item)

    audit(

        db,

        admin.id,

        "REGISTER_PHYSICAL_ITEM",

        "item",

        item.id

    )

    db.commit()

    db.refresh(item)

    return {

        "message":
            "Physical item registered",

        "item_id":
            item.id,

        "item_code":
            item.item_code

    }


# ------------------------------------------------
# ADMIN SECRET EVIDENCE
# ------------------------------------------------

@app.post(
    "/admin/items/{item_id}/evidence"
)
def admin_add_evidence(

    item_id: int,

    data: EvidenceCreate,

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    item = db.get(
        Item,
        item_id
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )

    evidence = Evidence(

        item_id=item.id,

        evidence_type=
            data.evidence_type.lower(),

        secret_value=
            data.secret_value,

        base_weight=
            data.base_weight,

        is_active=True

    )

    db.add(evidence)

    audit(

        db,

        admin.id,

        "ADD_SECRET_EVIDENCE",

        "item",

        item.id

    )

    db.commit()

    db.refresh(evidence)

    # NEVER return secret_value.

    return {

        "message":
            "Secret evidence saved",

        "evidence_id":
            evidence.id,

        "evidence_type":
            evidence.evidence_type

    }


# ------------------------------------------------
# ADMIN CLAIMS
# ------------------------------------------------

@app.get("/admin/claims")
def admin_get_claims(

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    claims = (

        db.query(Claim)

        .order_by(
            Claim.created_at.desc()
        )

        .all()

    )

    result = []

    for claim in claims:

        verification = (

            db.query(
                VerificationResult
            )

            .filter(
                VerificationResult.claim_id
                == claim.id
            )

            .all()

        )

        score = None

        if verification:

            score = round(
                sum(
                    x.contribution
                    for x in verification
                ),
                2
            )

        item = (

            db.query(Item)

            .filter(
                Item.found_report_id
                == claim.found_report_id
            )

            .first()

        )

        claimant = db.get(User, claim.claimant_id)
        found_r = db.get(FoundReport, claim.found_report_id)
        lost_r = db.get(LostReport, claim.lost_report_id)
        result.append({

            "claim_id":
                claim.id,

            "claim_code":
                claim.claim_code,

            "status":
                claim.status,

            "claimant_id":
                claim.claimant_id,

            "lost_report_id":
                claim.lost_report_id,

            "found_report_id":
                claim.found_report_id,

            "item_id":
                item.id
                if item
                else None,

            "item_code":
                item.item_code
                if item
                else None,

            "ownership_score":
                score,
            "claimant_name": claimant.full_name if claimant else "",
            "claimant_email": claimant.email if claimant else "",
            "item_category": found_r.category if found_r else None,
            "lost_title": lost_r.title if lost_r else None,

            "created_at":
                claim.created_at

        })

    return result


# ------------------------------------------------
# ADMIN APPROVE
# ------------------------------------------------

@app.post(
    "/admin/claims/{claim_id}/approve"
)
def admin_approve(

    claim_id: int,

    data: ClaimDecision,

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    if claim.status != "ADMIN_REVIEW":
        raise HTTPException(
            status_code=400,
            detail="Only claims in admin review can be approved"
        )

    claim.status = (
        "READY_FOR_COLLECTION"
    )

    found = db.get(
        FoundReport,
        claim.found_report_id
    )

    found.status = (
        "READY_FOR_COLLECTION"
    )

    notify(

        db,

        claim.claimant_id,

        "Claim approved",

        f"Claim {claim.claim_code} approved. Collect your item from the College Lost & Found Desk.",

        "APPROVED"

    )

    audit(

        db,

        admin.id,

        "APPROVE_CLAIM",

        "claim",

        claim.id,

        data.note

    )

    db.commit()

    return {

        "message":
            "Claim approved",

        "status":
            claim.status,

        "collection_point":
            "College Lost & Found Desk"

    }


# ------------------------------------------------
# ADMIN REJECT
# ------------------------------------------------

@app.post(
    "/admin/claims/{claim_id}/reject"
)
def admin_reject(

    claim_id: int,

    data: ClaimDecision,

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    claim.status = "REJECTED"

    notify(

        db,

        claim.claimant_id,

        "Claim requires review",

        data.note
        or
        "The claim was not approved at this stage.",

        "REJECTED"

    )

    audit(

        db,

        admin.id,

        "REJECT_CLAIM",

        "claim",

        claim.id,

        data.note

    )

    db.commit()

    return {

        "message":
            "Claim rejected",

        "status":
            claim.status

    }


# ------------------------------------------------
# ADMIN RETURN ITEM
# ------------------------------------------------

@app.post(
    "/admin/claims/{claim_id}/return"
)
def admin_return(

    claim_id: int,

    data: ClaimDecision,

    db: Session = Depends(get_db),

    admin=Depends(require_admin)

):

    claim = db.get(
        Claim,
        claim_id
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    if claim.status != "READY_FOR_COLLECTION":

        raise HTTPException(

            status_code=400,

            detail=
                "Claim is not ready for collection"

        )

    claim.status = "RETURNED"

    found = db.get(
        FoundReport,
        claim.found_report_id
    )

    found.status = "RETURNED"

    item = (

        db.query(Item)

        .filter(
            Item.found_report_id
            == found.id
        )

        .first()

    )

    if item:

        item.physical_status = (
            "RETURNED"
        )

    notify(

        db,

        claim.claimant_id,

        "Item returned",

        f"Item for {claim.claim_code} has been returned through the Lost & Found Desk.",

        "RETURNED"

    )

    audit(

        db,

        admin.id,

        "RETURN_ITEM",

        "claim",

        claim.id,

        data.note

    )

    db.commit()

    return {

        "message":
            "Item marked as returned",

        "status":
            claim.status

    }


# ------------------------------------------------
# ADMIN RESET LOCKED CLAIM
# ------------------------------------------------
@app.post("/admin/claims/{claim_id}/reset")
def admin_reset_claim(
    claim_id: int,
    data: ClaimDecision,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    claim = db.get(Claim, claim_id)

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    if claim.status != "CLAIM_LOCKED":
        raise HTTPException(
            status_code=400,
            detail="Only locked claims can be reset"
        )

    db.query(VerificationAttempt).filter(
        VerificationAttempt.claim_id == claim.id
    ).delete(synchronize_session=False)

    claim.status = "VERIFICATION_PENDING"

    audit(
        db,
        admin.id,
        "RESET_CLAIM",
        "claim",
        claim.id,
        data.note
    )

    db.commit()

    return {
        "message": "Claim reset",
        "status": claim.status
    }


# ------------------------------------------------
# FRONTEND (keep this last, after every API route)
# ------------------------------------------------
@app.get("/admin/found")
def admin_found(
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    rows = (
        db.query(FoundReport)
        .order_by(FoundReport.created_at.desc())
        .all()
    )
    out = []
    for f in rows:
        d = own_found(f, db)
        u = db.get(User, f.finder_id)
        d["finder_name"] = u.full_name if u else ""
        out.append(d)
    return out


@app.get("/admin/lost")
def admin_lost(
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    rows = (
        db.query(LostReport)
        .order_by(LostReport.created_at.desc())
        .all()
    )
    out = []
    for r in rows:
        d = safe_lost(r)
        u = db.get(User, r.user_id)
        d["owner_name"] = u.full_name if u else ""
        out.append(d)
    return out


@app.post("/admin/found/{found_id}/reject")
def admin_reject_found(
    found_id: int,
    data: ClaimDecision,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    f = db.get(FoundReport, found_id)
    if not f:
        raise HTTPException(
            status_code=404,
            detail="Found report not found"
        )
    if db.query(Item).filter(Item.found_report_id == f.id).first():
        raise HTTPException(
            status_code=400,
            detail="This item is already registered"
        )
    f.status = "REJECTED"
    audit(db, admin.id, "REJECT_FOUND_REPORT", "found_report", f.id, data.note)
    db.commit()
    return {"message": "Found report rejected"}


from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend"
)

if os.path.isdir(FRONTEND_DIR):
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend"
    )
