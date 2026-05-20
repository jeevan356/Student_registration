from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
import logging
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from typing import Optional
import uuid
from datetime import datetime, timezone
import pandas as pd
import traceback

# =========================
# ENVIRONMENT
# =========================

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_KEY exists:", bool(SUPABASE_KEY))

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE environment variables")

# =========================
# SUPABASE
# =========================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# PRICING
# =========================

REGISTRATION_FEE = 50.00
EXTRA_TSHIRT_PRICE = 15.00

# =========================
# APP
# =========================

app = FastAPI(title="TAISM Student Registration")

api_router = APIRouter(prefix="/api")

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# =========================
# MODELS
# =========================

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
    origin_url: str


class AdminStats(BaseModel):
    total_students: int
    completed_registrations: int
    pending_registrations: int
    total_revenue: float

# =========================
# CSV LOADER
# =========================

def load_csv_to_supabase():
    csv_path = ROOT_DIR / "students.csv"

    print("CSV PATH:", csv_path)

    if not csv_path.exists():
        logger.warning("students.csv not found")
        return

    try:
        df = pd.read_csv(csv_path)

        print("CSV loaded successfully")
        print(df.head())

        for _, row in df.iterrows():

            student_id = str(row["StudentID"])

            print(f"Checking student: {student_id}")

            existing = (
                supabase
                .table("students")
                .select("student_id")
                .eq("student_id", student_id)
                .execute()
            )

            if not existing.data:

                print(f"Inserting student: {student_id}")

                supabase.table("students").insert({
                    "student_id": student_id,
                    "name": row["Name"],
                    "age": int(row["Age"]),
                    "email": row["Email"],
                    "department": row["Department"],
                    "gpa": float(row["GPA"]),
                    "graduation_year": int(row["GraduationYear"]),
                    "extra_tshirts": 0
                }).execute()

        logger.info(f"Loaded {len(df)} students")

    except Exception:
        print("\n========== FULL ERROR ==========\n")
        print(traceback.format_exc())
        print("\n================================\n")

# =========================
# AUTH
# =========================

@api_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):

    result = (
        supabase
        .table("students")
        .select("*")
        .eq("student_id", request.student_id)
        .eq("email", request.email)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    student = result.data[0]

    token = f"{student['student_id']}:{datetime.now(timezone.utc).isoformat()}"

    return LoginResponse(
        success=True,
        message="Login successful",
        student_id=student["student_id"],
        token=token
    )

# =========================
# STUDENT
# =========================

@api_router.get("/student/{student_id}")
async def get_student(student_id: str):

    result = (
        supabase
        .table("students")
        .select("*")
        .eq("student_id", student_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Student not found")

    return result.data[0]


@api_router.get("/pricing")
async def get_pricing():
    return {
        "registration_fee": REGISTRATION_FEE,
        "extra_tshirt_price": EXTRA_TSHIRT_PRICE,
        "currency": "usd"
    }


@api_router.post("/student/update-tshirt")
async def update_tshirt(request: UpdateTshirtRequest):

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

    return {"success": True}

# =========================
# MOCK PAYMENT
# =========================

@api_router.post("/payment/create-checkout")
async def create_checkout(request: CreateCheckoutRequest):

    result = (
        supabase
        .table("students")
        .select("*")
        .eq("student_id", request.student_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Student not found")

    student = result.data[0]

    extra = student.get("extra_tshirts", 0) or 0

    total = REGISTRATION_FEE + (extra * EXTRA_TSHIRT_PRICE)

    now = datetime.now(timezone.utc).isoformat()

    (
        supabase
        .table("students")
        .update({
            "payment_status": "paid",
            "payment_id": f"MOCK-{uuid.uuid4().hex[:8]}",
            "registered_at": now
        })
        .eq("student_id", request.student_id)
        .execute()
    )

    return {
        "message": "Mock payment successful",
        "total_amount": total
    }


@api_router.get("/payment/status/{session_id}")
async def payment_status(session_id: str):
    return {
        "status": "paid",
        "mode": "mock"
    }

# =========================
# ADMIN
# =========================

@api_router.get("/admin/stats", response_model=AdminStats)
async def stats():

    total = len(
        supabase
        .table("students")
        .select("student_id")
        .execute()
        .data or []
    )

    paid = len(
        supabase
        .table("students")
        .select("student_id")
        .eq("payment_status", "paid")
        .execute()
        .data or []
    )

    return AdminStats(
        total_students=total,
        completed_registrations=paid,
        pending_registrations=total - paid,
        total_revenue=paid * REGISTRATION_FEE
    )

# =========================
# ROOT
# =========================

@api_router.get("/")
async def root():
    return {"status": "running"}

# =========================
# MIDDLEWARE
# =========================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# STARTUP
# =========================

@app.on_event("startup")
async def startup():
    print("\n=== STARTUP RUNNING ===\n")
    load_csv_to_supabase()