from main import analyze_ticket


def test_payment_without_order():
    result = analyze_ticket(
        "مشکل پرداخت",
        "پول از حسابم کم شده ولی سفارش ثبت نشده",
    )

    assert result["category"] == "payments"
    assert result["subcategory"] == "charged_without_order"
    assert result["priority"] == "high"
    assert result["assigned_team"] == "finance"