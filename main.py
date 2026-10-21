from contextlib import asynccontextmanager
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field


DB_PATH = Path(__file__).resolve().parent / "tickets.db"


TAXONOMY = {
    "orders": [
        "order_status", "cancel_order", "edit_order",
        "order_failed", "duplicate_order",
    ],
    "payments": [
        "payment_failed", "charged_without_order", "refund",
        "billing_dispute", "duplicate_charge", "payment_method_issue",
    ],
    "shipping": [
        "shipping_status", "shipping_delay", "lost_parcel",
        "delivery_failed", "tracking_issue", "address_change",
        "delivery_address_issue",
    ],
    "returns_quality": [
        "damaged_item", "defective_item", "poor_quality",
        "wrong_item", "product_mismatch", "missing_parts",
        "missing_item", "missing_seal", "return_request",
        "exchange_request", "return_status",
    ],
    "warranty": [
        "warranty_claim", "warranty_coverage", "warranty_status",
        "repair_request", "warranty_denied",
    ],
    "products": [
        "product_details", "out_of_stock", "price_mismatch",
        "product_availability", "product_comparison",
    ],
    "account": [
        "login", "password_reset", "registration",
        "profile", "account_access", "account_security",
    ],
    "technical": [
        "website_error", "cart_error", "checkout_error",
        "app_error", "technical_bug",
    ],
    "promotions": [
        "invalid_coupon", "discount_issue",
        "loyalty_points", "promotion_terms",
    ],
    "feedback": [
        "suggestion", "complaint", "staff_complaint",
        "service_feedback", "compliment",
    ],
    "other": ["unclassified"],
}


ROUTING = {
    "orders": "order_support",
    "payments": "finance",
    "shipping": "logistics",
    "returns_quality": "returns_team",
    "warranty": "warranty_team",
    "products": "product_support",
    "account": "account_support",
    "technical": "technical_support",
    "promotions": "customer_support",
    "feedback": "customer_experience",
    "other": "manual_review",
}


KEYWORDS = {
    "payments": {
        "charged_without_order": [
            "پول از حسابم کم شده ولی سفارش ثبت نشده",
            "پول از حسابم کم شده",
            "پول از حساب کم شده",
            "سفارش ثبت نشده ولی پول",
            "پول کم شد ولی سفارش",
            "کسر وجه بدون ثبت سفارش",
            "برداشت وجه بدون سفارش",
        ],
        "duplicate_charge": [
            "دوبار پول کم",
            "دو بار پول کم",
            "دوبار از حساب",
            "دو بار از حساب",
            "پرداخت تکراری",
            "دو بار پرداخت",
        ],
        "payment_failed": [
            "پرداخت ناموفق",
            "پرداخت انجام نشد",
            "پرداخت خطا داد",
            "تراکنش ناموفق",
            "پول پرداخت نشد",
        ],
        "refund": [
            "بازپرداخت",
            "استرداد وجه",
            "پولم برنگشته",
            "وجه برنگشته",
            "پول برگشت نخورده",
            "هنوز پولم را پس نداد",
        ],
        "billing_dispute": [
            "مبلغ اشتباه",
            "مبلغ غیرمجاز",
            "صورتحساب اشتباه",
            "هزینه اضافی",
        ],
        "payment_method_issue": [
            "روش پرداخت",
            "کارت بانکی",
            "درگاه پرداخت",
            "پرداخت اینترنتی",
        ],
    },
    "warranty": {
        "warranty_claim": [
            "گارانتی",
            "ضمانت نامه",
            "ضمانت‌نامه",
        ],
        "warranty_coverage": [
            "شامل گارانتی",
            "تحت پوشش گارانتی",
            "شرایط گارانتی",
        ],
        "warranty_status": [
            "وضعیت گارانتی",
            "پیگیری گارانتی",
        ],
        "repair_request": [
            "تعمیر محصول",
            "درخواست تعمیر",
            "تعمیر دستگاه",
            "تعمیر کالا",
        ],
        "warranty_denied": [
            "گارانتی قبول نکرد",
            "گارانتی رد شد",
            "گارانتی را نپذیرفت",
        ],
    },
    "returns_quality": {
        "missing_seal": [
            "پلمپ نبود",
            "پلمپ باز بود",
            "پلمپ نداشت",
            "بدون پلمپ",
            "پلمپ شده نبود",
            "بسته بندی باز بود",
            "بسته بندی دستکاری شده",
            "بسته‌بندی دستکاری شده",
        ],
        "missing_parts": [
            "قطعه کم است",
            "قطعه ای کم است",
            "قطعه‌ای کم است",
            "لوازم جانبی نیست",
            "متعلقات ناقص",
            "قطعه داخل جعبه نبود",
            "پیچ داخل جعبه نبود",
        ],
        "missing_item": [
            "یکی از کالاها نرسیده",
            "یکی از محصولات نرسیده",
            "کالا داخل بسته نبود",
            "محصول داخل بسته نبود",
            "سفارش ناقص رسید",
            "یک قلم از سفارش نیست",
        ],
        "product_mismatch": [
            "رنگ اشتباه",
            "رنگش فرق دارد",
            "رنگ با سفارش فرق",
            "سایز اشتباه",
            "مدل اشتباه",
            "با چیزی که سفارش دادم فرق",
            "با عکس فرق دارد",
            "با عکس فرق داشت",
            "مشخصات فرق دارد",
            "کالای متفاوت",
        ],
        "damaged_item": [
            "کالا آسیب دیده",
            "محصول آسیب دیده",
            "بسته آسیب دیده",
            "شکسته به دستم رسید",
            "کالا شکسته",
            "ضربه خورده",
        ],
        "defective_item": [
            "کار نمی کند",
            "کار نمیکند",
            "خراب است",
            "معیوب است",
            "از کار افتاده",
            "روشن نمی شود",
            "روشن نمیشود",
        ],
        "poor_quality": [
            "کیفیت پایین",
            "کیفیتش بد است",
            "کیفیت خوبی ندارد",
            "جنس بی کیفیت",
            "بی کیفیت است",
            "کیفیت نامناسب",
        ],
        "wrong_item": [
            "کالای اشتباه",
            "محصول اشتباه فرستادید",
            "چیز دیگری فرستادید",
            "کالای دیگری فرستاده",
        ],
        "return_request": [
            "می خواهم مرجوع",
            "میخوام مرجوع",
            "درخواست مرجوعی",
            "پس دادن کالا",
            "پس بفرستم",
            "مرجوع کنم",
        ],
        "exchange_request": [
            "درخواست تعویض",
            "می خواهم تعویض",
            "میخوام تعویض",
            "تعویض کالا",
        ],
        "return_status": [
            "وضعیت مرجوعی",
            "پیگیری مرجوعی",
            "مرجوعی من",
        ],
    },
    "shipping": {
        "lost_parcel": [
            "بسته گم شده",
            "مرسوله گم شده",
            "بسته پیدا نمی شود",
            "بسته پیدا نمیشه",
        ],
        "delivery_failed": [
            "تحویل ناموفق",
            "مامور تحویل نیامد",
            "مامور پست نیامد",
            "تحویل نگرفتم",
        ],
        "tracking_issue": [
            "کد رهگیری",
            "رهگیری نمی شود",
            "رهگیری نمیشه",
            "وضعیت مرسوله مشخص نیست",
        ],
        "address_change": [
            "تغییر آدرس ارسال",
            "آدرس ارسال را عوض",
            "اصلاح آدرس سفارش",
        ],
        "delivery_address_issue": [
            "به آدرس اشتباه",
            "آدرس اشتباه ارسال",
            "به آدرس دیگری فرستادید",
        ],
        "shipping_delay": [
            "ارسال دیر",
            "تاخیر در ارسال",
            "تأخیر در ارسال",
            "خیلی دیر رسید",
            "هنوز به دستم نرسیده",
            "بسته نرسیده",
            "سفارشم نرسیده",
        ],
        "shipping_status": [
            "وضعیت ارسال",
            "سفارشم کجاست",
            "بسته من کجاست",
            "مرسوله کجاست",
        ],
    },
    "orders": {
        "cancel_order": [
            "لغو سفارش",
            "سفارش را لغو",
            "کنسل کردن سفارش",
        ],
        "edit_order": [
            "ویرایش سفارش",
            "تغییر سفارش",
            "تغییر آدرس سفارش",
            "تغییر تعداد سفارش",
        ],
        "duplicate_order": [
            "سفارش تکراری",
            "دوبار سفارش ثبت",
            "دو بار سفارش ثبت",
        ],
        "order_failed": [
            "سفارش ثبت نمی شود",
            "سفارش ثبت نمیشود",
            "ثبت سفارش خطا",
            "سفارش ناموفق",
        ],
        "order_status": [
            "وضعیت سفارش",
            "پیگیری سفارش",
            "سفارشم ثبت شده",
            "جزئیات سفارش",
        ],
    },
    "account": {
        "password_reset": [
            "فراموشی رمز",
            "رمز عبور را فراموش",
            "بازیابی رمز",
            "تغییر رمز عبور",
        ],
        "login": [
            "نمی توانم وارد",
            "نمیتوانم وارد",
            "ورود به حساب",
            "لاگین",
        ],
        "registration": [
            "ثبت نام",
            "ثبت‌نام",
            "ساخت حساب",
        ],
        "account_security": [
            "حسابم هک شده",
            "حساب هک شده",
            "ورود غیرمجاز به حساب",
            "فعالیت مشکوک در حساب",
        ],
        "account_access": [
            "حسابم مسدود",
            "حساب مسدود شده",
            "دسترسی به حساب",
        ],
        "profile": [
            "ویرایش پروفایل",
            "تغییر شماره موبایل",
            "تغییر اطلاعات حساب",
        ],
    },
    "technical": {
        "checkout_error": [
            "صفحه پرداخت باز نمی شود",
            "صفحه پرداخت باز نمیشود",
            "خطای تسویه حساب",
        ],
        "cart_error": [
            "سبد خرید",
            "اضافه به سبد",
            "سبد خرید کار نمی کند",
        ],
        "app_error": [
            "اپلیکیشن خراب",
            "برنامه باز نمی شود",
            "برنامه باز نمیشود",
            "خطای اپلیکیشن",
        ],
        "website_error": [
            "سایت باز نمی شود",
            "سایت باز نمیشود",
            "سایت خطا می دهد",
            "صفحه باز نمی شود",
        ],
        "technical_bug": [
            "باگ",
            "خطای فنی",
            "مشکل فنی",
            "ارور می دهد",
        ],
    },
    "promotions": {
        "invalid_coupon": [
            "کد تخفیف کار نمی کند",
            "کد تخفیف معتبر نیست",
            "کد تخفیف نامعتبر",
            "کوپن نامعتبر",
        ],
        "discount_issue": [
            "تخفیف اعمال نشد",
            "تخفیف اعمال نشده",
            "تخفیف محاسبه نشده",
        ],
        "loyalty_points": [
            "امتیاز وفاداری",
            "امتیاز باشگاه مشتریان",
            "امتیازم اضافه نشده",
        ],
        "promotion_terms": [
            "شرایط تخفیف",
            "شرایط جشنواره",
            "شرایط پیشنهاد ویژه",
        ],
    },
    "products": {
        "price_mismatch": [
            "قیمت اشتباه",
            "قیمت سایت فرق دارد",
            "قیمت متفاوت",
        ],
        "out_of_stock": [
            "موجود نیست",
            "ناموجود",
            "موجودی ندارد",
        ],
        "product_availability": [
            "موجود می شود",
            "موجود میشه",
            "موجودی محصول",
        ],
        "product_comparison": [
            "مقایسه محصولات",
            "کدام محصول بهتر",
            "فرق این دو محصول",
        ],
        "product_details": [
            "مشخصات محصول",
            "اطلاعات محصول",
            "ویژگی های محصول",
            "ابعاد محصول",
        ],
    },
    "feedback": {
        "staff_complaint": [
            "شکایت از کارمند",
            "شکایت از کارکنان",
            "برخورد بد کارمند",
            "رفتار بد پشتیبانی",
            "کارمند بی ادب",
        ],
        "suggestion": [
            "پیشنهاد می کنم",
            "پیشنهاد میکنم",
            "پیشنهاد من",
            "بهتر است که",
            "ایده من",
        ],
        "compliment": [
            "از خدمات راضی هستم",
            "تشکر از پشتیبانی",
            "کار شما عالی است",
            "برخورد عالی",
        ],
        "service_feedback": [
            "نظر درباره خدمات",
            "بازخورد درباره خدمات",
            "انتقاد از خدمات",
        ],
        "complaint": [
            "شکایت دارم",
            "ناراضی هستم",
            "اعتراض دارم",
            "رفتار نامناسب",
            "خدمات بد",
        ],
    },
}


CRITICAL_KEYWORDS = [
    "کلاهبرداری",
    "سرقت",
    "حسابم هک شده",
    "حساب هک شده",
    "برداشت غیرمجاز",
    "برداشت غیر مجاز",
    "ورود غیرمجاز به حساب",
]

HIGH_KEYWORDS = [
    "فوری",
    "در اسرع وقت رسیدگی بشه",
    "خیلی فوری",
    "دوبار پول کم",
    "دو بار پول کم",
    "پولم برنگشته",
    "پول برگشت نخورده",
    "کسر وجه بدون ثبت سفارش",
    "پول از حسابم کم شده ولی سفارش ثبت نشده",
    "پول از حساب کم شده ولی سفارش ثبت نشده",
]


class TicketInput(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=3, max_length=5000)


def normalize_text(text: str) -> str:
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
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
            """
        )

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(tickets)").fetchall()
        }

        if "subcategory" not in columns:
            conn.execute(
                """
                ALTER TABLE tickets
                ADD COLUMN subcategory TEXT NOT NULL DEFAULT 'unclassified'
                """
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Persian AI Ticket Manager",
    version="0.2.0",
    lifespan=lifespan,
)


def analyze_ticket(subject: str, message: str) -> dict:
    text = normalize_text(f"{subject} {message}")

    category = "other"
    subcategory = "unclassified"

    # Keep the tested payment scenario ahead of general order keywords.
    payment_first = [
        "پول از حسابم کم شده ولی سفارش ثبت نشده",
        "سفارش ثبت نشده ولی پول",
        "کسر وجه بدون ثبت سفارش",
        "برداشت وجه بدون سفارش",
    ]

    for phrase in payment_first:
        if normalize_text(phrase) in text:
            category = "payments"
            subcategory = "charged_without_order"
            break

    # Match specific problems before general complaint/feedback phrases.
    if category == "other":
        for candidate_category, subcategories in KEYWORDS.items():
            found = False
            for candidate_subcategory, phrases in subcategories.items():
                for phrase in phrases:
                    if normalize_text(phrase) in text:
                        category = candidate_category
                        subcategory = candidate_subcategory
                        found = True
                        break
                if found:
                    break
            if found:
                break

    if any(normalize_text(word) in text for word in CRITICAL_KEYWORDS):
        priority = "critical"
    elif (
        category == "payments"
        and subcategory == "charged_without_order"
    ) or any(normalize_text(word) in text for word in HIGH_KEYWORDS):
        priority = "high"
    elif category == "other":
        priority = "low"
    else:
        priority = "medium"

    assigned_team = ROUTING.get(category, "manual_review")

    if category == "other":
        suggested_reply = (
            "از اینکه با ما تماس گرفتید سپاسگزاریم. "
            "برای بررسی دقیق‌تر، لطفاً جزئیات بیشتری از مشکل خود ارائه دهید."
        )
    elif category == "payments":
        suggested_reply = (
            "از بروز مشکل در پرداخت متأسفیم. "
            "تیم مالی موضوع را بررسی می‌کند. لطفاً اطلاعات حساس کارت بانکی "
            "یا رمز خود را ارسال نکنید."
        )
    elif category == "shipping":
        suggested_reply = (
            "از تأخیر یا مشکل در ارسال متأسفیم. "
            "تیم ارسال موضوع را بررسی می‌کند. در صورت امکان، شماره سفارش "
            "را برای پیگیری در اختیار ما قرار دهید."
        )
    elif category == "returns_quality":
        suggested_reply = (
            "از مشکل پیش‌آمده در کالای دریافتی متأسفیم. "
            "تیم مربوطه درخواست شما را بررسی می‌کند. لطفاً شماره سفارش "
            "و در صورت امکان تصویر کالا یا بسته‌بندی را ارسال کنید."
        )
    elif category == "warranty":
        suggested_reply = (
            "درخواست شما درباره گارانتی یا تعمیر دریافت شد. "
            "تیم مربوطه شرایط و مراحل پیگیری را بررسی می‌کند."
        )
    elif category == "feedback":
        suggested_reply = (
            "از اینکه نظر و بازخورد خود را با ما در میان گذاشتید "
            "سپاسگزاریم. پیام شما برای بررسی به تیم تجربه مشتری ارجاع شد."
        )
    else:
        suggested_reply = (
            "پیام شما دریافت شد. تیم مربوطه موضوع را بررسی می‌کند. "
            "در صورت نیاز برای دریافت اطلاعات تکمیلی با شما تماس می‌گیریم."
        )

    return {
        "category": category,
        "subcategory": subcategory,
        "priority": priority,
        "assigned_team": assigned_team,
        "suggested_reply": suggested_reply,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/taxonomy")
def get_taxonomy():
    return TAXONOMY


@app.get("/tickets/sample")
def sample_tickets():
    return [
        {
            "customer_id": "customer_001",
            "subject": "کسر وجه از حساب",
            "message": "پول از حسابم کم شده ولی سفارش ثبت نشده",
        },
        {
            "customer_id": "customer_002",
            "subject": "کالای آسیب دیده",
            "message": "محصول شکسته به دستم رسید",
        },
        {
            "customer_id": "customer_003",
            "subject": "پیشنهاد برای سایت",
            "message": "پیشنهاد می کنم امکان مقایسه محصولات اضافه شود",
        },
    ]


@app.post("/tickets")
def create_ticket(ticket: TicketInput):
    result = analyze_ticket(ticket.subject, ticket.message)
    ticket_id = str(uuid4())

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO tickets (
                id, customer_id, subject, message, category,
                priority, assigned_team, suggested_reply, subcategory
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                result["subcategory"],
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