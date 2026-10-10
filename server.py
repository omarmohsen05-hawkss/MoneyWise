"""MoneyWise custom full-stack website. One FastAPI server serves HTML + JSON APIs.

All financial/security calculations remain in reusable Python modules. No real
payments, live bank access, external URL fetching or CSV persistence occur.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from finance import forecast, goal_plan
from security import analyze_message
from transactions import inspect, load_csv
from ai_agent import respond, evaluate_savings_changes

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
app = FastAPI(title="MoneyWise API", version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class FinanceInput(BaseModel):
    balance: float = Field(default=850, ge=0, le=1e8)
    paycheck: float = Field(default=500, ge=0, le=1e8)
    payday: date
    cadence: Literal[7, 14, 30] = 14
    rent: float = Field(default=600, ge=0, le=1e8)
    rent_date: date
    groceries: float = Field(default=50, ge=0, le=1e8)
    subscriptions: float = Field(default=55, ge=0, le=1e8)

class PaymentInput(BaseModel):
    financial: FinanceInput
    message: str = Field(default="", max_length=5000)
    link: str = Field(default="", max_length=2000)
    payment: float = Field(default=300, ge=0, le=1e8)
    days: Literal[30, 60, 90] = 30

class PurchaseInput(BaseModel):
    financial: FinanceInput
    price: float = Field(default=500, ge=0, le=1e8)
    cheaper: float = Field(default=250, ge=0, le=1e8)
    days: Literal[30, 60, 90] = 60
    selected_savings: float = Field(default=0, ge=0, le=1e8)
    include_savings: bool = False

class TransactionsInput(BaseModel):
    csv_text: str = Field(max_length=2_000_000)

class GoalInput(BaseModel):
    financial: FinanceInput
    goal: float = Field(default=1200, gt=0, le=1e8)
    saved: float = Field(default=200, ge=0, le=1e8)
    months: int = Field(default=4, ge=1, le=36)
    selected_savings: float = Field(default=0, ge=0, le=1e8)

class TransactionSummary(BaseModel):
    transactions: int = Field(default=0, ge=0, le=5000)
    spent: float = Field(default=0, ge=0, le=1e9)
    monthly_estimate: float = Field(default=0, ge=0, le=1e8)
    duplicate_count: int = Field(default=0, ge=0, le=5000)
    unusual_count: int = Field(default=0, ge=0, le=5000)

class ChatItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=700)

class CoachInput(GoalInput):
    question: str = Field(min_length=1, max_length=600)
    history: list[ChatItem] = Field(default_factory=list, max_length=12)
    payment: float = Field(default=300, ge=0, le=1e8)
    message: str = Field(default="", max_length=5000)
    link: str = Field(default="", max_length=2000)
    days: Literal[30, 60, 90] = 30
    transactions: TransactionSummary | None = None


def ensure_dates(data: FinanceInput) -> None:
    today = date.today()
    if data.payday < today or data.rent_date < today:
        raise HTTPException(status_code=422, detail="Payday and next rent date cannot be in the past.")
    if (data.payday - today).days > 365 or (data.rent_date - today).days > 365:
        raise HTTPException(status_code=422, detail="Select payday and bill dates within the next year.")


def projection(data: FinanceInput, days: int, payment: float, payment_date: date,
               subscription_override: float | None = None) -> dict:
    ensure_dates(data)
    result = forecast(balance=data.balance, start=date.today(), days=days,
        payment=payment, payment_date=payment_date, paycheck=data.paycheck,
        payday=data.payday, payday_every=data.cadence, rent=data.rent,
        rent_date=data.rent_date, groceries_weekly=data.groceries,
        subscriptions_monthly=(data.subscriptions if subscription_override is None else subscription_override))
    rows = [{"date": r.date.isoformat(), "balance": float(r.balance),
             "events": r.events} for r in result.itertuples(index=False)]
    return {"points": rows, "lowest": round(float(result.balance.min()), 2),
            "ending": round(float(result.balance.iloc[-1]), 2)}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/status")
def status():
    return {"status": "ok", "today": date.today().isoformat(),
            "live_ai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip())}


@app.get("/api/demo-csv")
def demo_csv():
    return PlainTextResponse((ROOT / "data" / "demo_transactions.csv").read_text(encoding="utf-8"),
                             media_type="text/csv")


@app.post("/api/payment")
def payment_analysis(payload: PaymentInput):
    review = analyze_message(payload.message, payload.link)
    pay_now = projection(payload.financial, payload.days, payload.payment, date.today())
    pay_later = projection(payload.financial, payload.days, payload.payment, payload.financial.payday)
    return {"security": review, "pay_now": pay_now, "pay_later": pay_later,
            "assumptions": "Payday timing is estimated. Only delay payments if permitted. Warning signs are not proof of fraud."}


@app.post("/api/purchase")
def purchase_analysis(payload: PurchaseInput):
    f = payload.financial
    selected = min(payload.selected_savings, f.subscriptions) if payload.include_savings else 0.0
    base = max(0.0, f.subscriptions - selected)
    scenarios = {
        "Buy now": projection(f, payload.days, payload.price, date.today(), base),
        "Buy on payday": projection(f, payload.days, payload.price, f.payday, base),
        "Cheaper option now": projection(f, payload.days, payload.cheaper, date.today(), base),
    }
    # Essential comparison: same purchase with and without subscription savings.
    original = projection(f, payload.days, payload.price, date.today(), f.subscriptions)
    improvement = round(scenarios["Buy now"]["ending"] - original["ending"], 2)
    return {"scenarios": scenarios, "baseline_buy_now": original,
            "savings_monthly": round(selected, 2),
            "ending_improvement": improvement,
            "first_subscription_day": 30,
            "note": "Selected cancellations are hypothetical. The current model starts recurring subscription charges on Day 30."}


@app.post("/api/transactions")
def transactions_analysis(payload: TransactionsInput):
    try:
        records = load_csv(payload.csv_text.encode("utf-8"))
        data = inspect(records)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    def rows(frame):
        return [{"date": r.date.strftime("%Y-%m-%d"), "description": str(r.description),
                 "cost": round(float(r.cost), 2)} for r in frame.head(75).itertuples(index=False)]

    return {"transactions": data["transactions"], "spent": round(data["spent"], 2),
            "monthly_estimate": round(data["monthly_estimate"], 2), "recurring": data["recurring"],
            "duplicates": rows(data["duplicates"]), "unusual": rows(data["unusual"]),
            "threshold": round(data["threshold"], 2),
            "duplicate_count": len(data["duplicates"]), "unusual_count": len(data["unusual"])}


@app.post("/api/goal")
def goal_analysis(payload: GoalInput):
    f = payload.financial
    ensure_dates(f)
    plan = goal_plan(payload.goal, payload.saved, payload.months, f.paycheck, f.cadence,
                     f.rent, f.groceries, f.subscriptions)
    cut = min(f.subscriptions, payload.selected_savings)
    adjusted = goal_plan(payload.goal, payload.saved, payload.months, f.paycheck,
                         f.cadence, f.rent, f.groceries, f.subscriptions - cut)
    return {"plan": plan, "adjusted_plan": adjusted, "selected_savings": round(cut, 2),
            "progress": round(min(100.0, (payload.saved / payload.goal) * 100), 1)}


@app.post("/api/coach")
def chat(payload: CoachInput):
    f = payload.financial
    ensure_dates(f)
    current = projection(f, payload.days, payload.payment, date.today())
    later = projection(f, payload.days, payload.payment, f.payday)
    tx = payload.transactions or TransactionSummary()
    risk = analyze_message(payload.message, payload.link)
    context = {
        "goal": payload.goal, "saved": payload.saved, "months": payload.months,
        "paycheck": f.paycheck, "cadence": f.cadence, "rent": f.rent,
        "groceries": f.groceries, "subscriptions": f.subscriptions,
        "chosen_savings": min(payload.selected_savings, f.subscriptions),
        "payment": payload.payment,
        "pay_now_min": current["lowest"], "pay_now_end": current["ending"],
        "pay_later_min": later["lowest"], "pay_later_end": later["ending"],
        "horizon": payload.days, "security_status": risk["status"],
        "security_alerts": risk["alerts"],
        "transaction_count": tx.transactions, "total_debits": tx.spent,
        "recurring_total": tx.monthly_estimate,
        "duplicate_count": tx.duplicate_count, "unusual_count": tx.unusual_count,
    }
    response, live_ai = respond(payload.question, context,
        [h.model_dump() for h in payload.history[-6:]],
        api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    return {"answer": response, "mode": "live_ai" if live_ai else "offline_rules"}
