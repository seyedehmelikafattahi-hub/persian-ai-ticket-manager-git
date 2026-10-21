from contextlib import asynccontextmanager
import sqlite3
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field


DB_PATH = "tickets.db"


TAXONOMY = {
    "orders": [
        "order_status",
        "cancel_order",
        "edit_order",
        "order_failed",
    ],
    "payments": [
        "payment_failed",
        "charged_without_order",
        "refund",
        "billing_dispute",
    ],
    "shipping": [
        "shipping_delay",
        "delivery_delay",
        "lost_parcel",
        "wrong_or_missing_item",
    ],
    "returns_quality": [
        "damaged_item",
        "defective_item",
        "wrong_item",
        "return_exchange",
    ],
    "account": [
        "login",
        "password_reset",
        "profile",
        "registration",
    ],
    "products": [
        "out_of_stock",
        "product_details",
        "price_mismatch",
    ],
    "technical": [
        "website_error",
        "cart_error",
        "checkout_error",
    ],
    "promotions": [
        "invalid_coupon",
        "discount_issue",
        "loyalty_points",
    ],
    "other": [
        "unclassified",
    ],
}


ROUTING = {
    "orders": "order_support",
    "payments": "finance",
    "shipping": "logistics",
    "returns_quality": "returns_team",
    "account": "account_support",
    "products": "product_support",
    "technical": "technical_support",
    "promotions": "customer_support",
    "other": "manual_review",
}


KEYWORDS = {
    "payments": [
        "کسر وجه",
        "پول کم شد",
        "بازپرداخت",
        "استرداد وجه",
        "پرداخت ناموفق",
    ],
    "shipping": [
        "مرسوله",
        "ارسال",
        "تحویل",
        "پست",
        "بسته نرسیده",
        "تاخیر در ارسال",
        "تأخیر در ارسال",
    ],
    "returns_quality": [
        "مرجوع",
        "تعویض",
        "خراب",
        "شکسته",
        "معیوب",
        "کالای اشتباه",
    ],
    "account": [
        "رمز عبور",
        "ورود به حساب",
        "ثبت نام",
        "حساب کاربری",
    ],
    "promotions": [
        "کد تخفیف",
        "تخفیف",
        "باشگاه مشتریان",
    ],
    "technical": [
        "خطای سایت",
        "سبد خرید",
        "صفحه باز نمی‌شود",
        "صفحه باز نمی شود",
    ],
    "products": [
        "موجودی",
        "مشخصات محصول",
        "قیمت کالا",
    ],
    "orders": [
        "سفارش",
        "لغو سفارش",
        "آدرس سفارش",
    ],
}


class TicketInput(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=3, max_length=5000)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                assigned_team TEXT NOT NULL,
                suggested_reply TEXT NOT NULL
            )
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Persian AI Ticket Manager",
    version="0.1.0",
    lifespan=lifespan,
)


def analyze_ticket(subject: str, message: str) -> dict:
    text = f"{subject} {message}"

    category = "other"
    subcategory = "unclassified"

    # More specific payment rules must run before order rules.
    if any(word in text for word in [
        "پول از حساب کسر شده",
        "پول از حسابم کم شده",
        "کسر وجه",
        "پرداخت ناموفق",
        "استرداد وجه",
        "بازپرداخت",
    ]):
        category = "payments"
        subcategory = "charged_without_order"

    else:
        for cat, words in KEYWORDS.items():
            match = next(
                (word for word in words if word in text),
                None,
            )
            if match:
                category = cat
                break

    if any(word in text for word in [
        "کلاهبرداری",
        "سرقت",
        "حسابم هک شده",
        "برداشت غیرمجاز",
    ]):
        priority = "critical"

    elif any(word in text for word in [
        "فوری",
        "چند بار پول کم شد",
        "پولم برنگشته",
        "پول از حساب کسر شده",
        "پول از حسابم کم شده",
    ]):
        priority = "high"

    elif category == "other":
        priority = "low"

    else:
        priority = "medium"

    suggested_reply = (
        "سلام، درخواست شما ثبت شد. "
        "تیم مربوطه موضوع را بررسی می‌کند. "
        "لطفاً تا زمان بررسی، اطلاعات حساس مانند رمز "
        "عبور یا اطلاعات کامل کارت بانکی را ارسال نکنید."
    )

    return {
        "category": category,
        "subcategory": subcategory,
        "priority": priority,
        "assigned_team": ROUTING[category],
        "suggested_reply": suggested_reply,
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/taxonomy")
def get_taxonomy():
    return TAXONOMY


@app.get("/tickets/sample")
def sample_tickets():
    return [
        {
            "customer_id": "C001",
            "subject": "تأخیر در ارسال",
            "message": "سفارشم هنوز تحویل داده نشده است.",
        },
        {
            "customer_id": "C002",
            "subject": "مشکل پرداخت",
            "message": "پول از حسابم کم شده ولی سفارش ثبت نشده.",
        },
        {
            "customer_id": "C003",
            "subject": "کد تخفیف",
            "message": "کد تخفیف من هنگام خرید اعمال نمی‌شود.",
        },
    ]


@app.post("/tickets")
def create_ticket(ticket: TicketInput):

    result = analyze_ticket(
        ticket.subject,
        ticket.message
    )

    ticket_id = str(uuid4())

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO tickets (
                id,
                customer_id,
                subject,
                message,
                category,
                priority,
                assigned_team,
                suggested_reply
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                ticket.customer_id,
                ticket.subject,
                ticket.message,
                result["category"],
                result["priority"],
                result["assigned_team"],
                result["suggested_reply"],
            ),
        )

    return {
        "ticket_id": ticket_id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "message": ticket.message,
        **result,
        "analysis_method": "keyword_baseline",
        "requires_human_review": (
            result["category"] == "other"
            or result["priority"] == "critical"
        ),
    }