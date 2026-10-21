import json
from urllib.request import Request, urlopen

data = {
    "model": "qwen2.5:3b",
    "prompt": """فقط یک شیء JSON معتبر برگردان؛ هیچ متن دیگری ننویس.
مقادیر مجاز:
category: orders, payments, shipping, returns_quality, account, products, technical, promotions
subcategory: charged_without_order
priority: low, medium, high
assigned_team: finance

تیکت: پول از حسابم کم شده ولی سفارش ثبت نشده
خروجی مورد انتظار:
{"category":"payments","subcategory":"charged_without_order","priority":"high","assigned_team":"finance"}""",
    "stream": False,
}

request = Request(
    "http://localhost:11434/api/generate",
    data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urlopen(request, timeout=300) as response:
    result = json.loads(response.read().decode("utf-8"))

print(repr(result["response"]))
print(result)
