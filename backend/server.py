from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel, ConfigDict
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import traceback
import logging
import uuid
import os

# ======================================================
# ENVIRONMENT
# ======================================================

ROOT_DIR = Path(__file__).parent

load_dotenv(ROOT_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE environment variables")

# ======================================================
# LOGGING
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ======================================================
# SUPABASE
# ======================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# ======================================================
# CONSTANTS
# ======================================================

REGISTRATION_FEE = 50.00
EXTRA_TSHIRT_PRICE = 15.00

# ======================================================
# FASTAPI
# ======================================================

app = FastAPI(
    title="TAISM Student Registration API",
    version="1.0.0"
)

api_router = APIRouter(prefix="/api")

# ======================================================
# MODELS
# ======================================================

class LoginRequest(BaseModel):
    student_id: str
    email: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    student_id: Optional[str] = None
    token: Optional[str] = None


class Student(BaseModel):

    model_config = ConfigDict(extra="ignore")

    student_id: str
    name: str
    age: int
    email: str
    department: str
    gpa: float
    graduation_year: int

    tshirt_size: Optional[str] = None
    extra_tshirts: Optional[int] = 0
    extra_tshirt_size: Optional[str] = None

    payment_id: Optional[str] = None
    payment_status: Optional[str] = None
    registered_at: Optional[str] = None


class UpdateTshirtRequest(BaseModel):
    student_id: str
    tshirt_size: str
    extra_tshirts: Optional[int] = 0
    extra_tshirt_size: Optional[str] = None


class CreateCheckoutRequest(BaseModel):
    student_id: str
    origin_url: Optional[str] = None


class AdminStats(BaseModel):
    total_students: int
    completed_registrations: int
    pending_registrations: int
    total_revenue: float

# ======================================================
# CSV LOADER
# ======================================================

def load_csv_to_supabase():

    csv_path = ROOT_DIR / "students.csv"

    if not csv_path.exists():
        logger.warning("students.csv not found")
        return

    try:

        df = pd.read_csv(csv_path)

        logger.info(f"CSV loaded successfully with {len(df)} students")

        for _, row in df.iterrows():

            student_id = str(row["StudentID"]).strip()

            existing = (
                supabase
                .table("students")
                .select("student_id")
                .eq("student_id", student_id)
                .execute()
            )

            # Skip existing students
            if existing.data:
                continue

            student_data = {
                "student_id": student_id,
                "name": row["Name"],
                "age": int(row["Age"]),
                "email": row["Email"],
                "department": row["Department"],
                "gpa": float(row["GPA"]),
                "graduation_year": int(row["GraduationYear"]),
                "extra_tshirts": 0,
                "payment_status": "pending"
            }

            supabase.table("students").insert(student_data).execute()

            logger.info(f"Inserted student {student_id}")

    except Exception as e:

        logger.error("Error loading CSV")
        logger.error(str(e))

        print("\n========== FULL ERROR ==========\n")
        print(traceback.format_exc())
        print("\n================================\n")

# ======================================================
# ROOT
# ======================================================

@api_router.get("/")
async def root():
    return {
        "status": "running",
        "message": "TAISM Student Registration API"
    }

# ======================================================
# AUTH
# ======================================================

@api_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):

    try:

        result = (
            supabase
            .table("students")
            .select("*")
            .eq("student_id", request.student_id)
            .eq("email", request.email)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        student = result.data[0]

        token = (
            f"{student['student_id']}:"
            f"{datetime.now(timezone.utc).isoformat()}"
        )

        return LoginResponse(
            success=True,
            message="Login successful",
            student_id=student["student_id"],
            token=token
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(str(e))
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )

# ======================================================
# STUDENT
# ======================================================

@api_router.get("/student/{student_id}")
async def get_student(student_id: str):

    try:

        result = (
            supabase
            .table("students")
            .select("*")
            .eq("student_id", student_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        return result.data[0]

    except HTTPException:
        raise

    except Exception as e:
        logger.error(str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch student"
        )

# ======================================================
# PRICING
# ======================================================

@api_router.get("/pricing")
async def get_pricing():

    return {
        "registration_fee": REGISTRATION_FEE,
        "extra_tshirt_price": EXTRA_TSHIRT_PRICE,
        "currency": "USD"
    }

# ======================================================
# TSHIRT UPDATE
# ======================================================

@api_router.post("/student/update-tshirt")
async def update_tshirt(request: UpdateTshirtRequest):

    try:

        update_data = {
            "tshirt_size": request.tshirt_size,
            "extra_tshirts": request.extra_tshirts or 0,
            "extra_tshirt_size": request.extra_tshirt_size
        }

        (
            supabase
            .table("students")
            .update(update_data)
            .eq("student_id", request.student_id)
            .execute()
        )

        return {
            "success": True,
            "message": "T-shirt updated successfully"
        }

    except Exception as e:

        logger.error(str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to update T-shirt"
        )

# ======================================================
# MOCK PAYMENT
# ======================================================

@api_router.post("/payment/create-checkout")
async def create_checkout(request: CreateCheckoutRequest):

    try:

        result = (
            supabase
            .table("students")
            .select("*")
            .eq("student_id", request.student_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        student = result.data[0]

        extra_tshirts = student.get("extra_tshirts", 0) or 0

        total_amount = (
            REGISTRATION_FEE +
            (extra_tshirts * EXTRA_TSHIRT_PRICE)
        )

        payment_id = f"MOCK-{uuid.uuid4().hex[:8]}"

        now = datetime.now(timezone.utc).isoformat()

        (
            supabase
            .table("students")
            .update({
                "payment_status": "paid",
                "payment_id": payment_id,
                "registered_at": now
            })
            .eq("student_id", request.student_id)
            .execute()
        )

        return {
            "success": True,
            "message": "Mock payment successful",
            "payment_id": payment_id,
            "total_amount": total_amount,
            "currency": "USD"
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.error(str(e))

        raise HTTPException(
            status_code=500,
            detail="Payment failed"
        )

# ======================================================
# PAYMENT STATUS
# ======================================================

@api_router.get("/payment/status/{session_id}")
async def payment_status(session_id: str):

    return {
        "status": "paid",
        "mode": "mock",
        "session_id": session_id
    }

# ======================================================
# ADMIN
# ======================================================

@api_router.get("/admin/stats", response_model=AdminStats)
async def get_admin_stats():

    try:

        total_students = len(
            supabase
            .table("students")
            .select("student_id")
            .execute()
            .data or []
        )

        completed_registrations = len(
            supabase
            .table("students")
            .select("student_id")
            .eq("payment_status", "paid")
            .execute()
            .data or []
        )

        pending_registrations = (
            total_students - completed_registrations
        )

        total_revenue = (
            completed_registrations * REGISTRATION_FEE
        )

        return AdminStats(
            total_students=total_students,
            completed_registrations=completed_registrations,
            pending_registrations=pending_registrations,
            total_revenue=total_revenue
        )

    except Exception as e:

        logger.error(str(e))

        raise HTTPException(
            status_code=500,
            detail="Failed to fetch admin stats"
        )

# ======================================================
# HEALTH CHECK
# ======================================================

@api_router.get("/health")
async def health_check():

    return {
        "status": "healthy"
    }

# ======================================================
# REGISTER ROUTER
# ======================================================

app.include_router(api_router)

# ======================================================
# CORS
# ======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# STARTUP
# ======================================================

@app.on_event("startup")
async def startup_event():

    logger.info("Starting application...")

    load_csv_to_supabase()

    logger.info("Application started successfully")

# ======================================================
# RENDER ENTRYPOINT
# ======================================================

# Run locally:
# uvicorn server:app --reload
