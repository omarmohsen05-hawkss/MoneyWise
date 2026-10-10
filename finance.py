"""Deterministic educational cash-flow projections for MoneyWise."""
from calendar import monthrange
from datetime import date, timedelta

import pandas as pd


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def forecast(
    *, balance: float, start: date, days: int, payment: float,
    payment_date: date, paycheck: float, payday: date, payday_every: int,
    rent: float, rent_date: date, groceries_weekly: float,
    subscriptions_monthly: float,
) -> pd.DataFrame:
    """Project end-of-day balance, repeating income and basic expenses.

    Assumptions: income arrives before bills on the same day; groceries
    first occur 7 days from start; subscriptions first occur in 30 days.
    Subscription billing date is an estimate, not read from a bank.
    """
    if days not in (30, 60, 90):
        raise ValueError("Choose 30, 60, or 90 days")
    if any(x < 0 for x in (balance, payment, paycheck, rent, groceries_weekly, subscriptions_monthly)):
        raise ValueError("Amounts cannot be negative")
    if payday_every not in (7, 14, 30):
        raise ValueError("Payday interval must be 7, 14 or 30 days")
    if min(payday, rent_date, payment_date) < start:
        raise ValueError("Payment and scheduled dates cannot be in the past")

    end = start + timedelta(days=days - 1)
    events = {}

    def add(d, amount, note):
        if start <= d <= end:
            events.setdefault(d, []).append((amount, note))

    cursor = payday
    while cursor <= end:
        add(cursor, paycheck, "Paycheck")
        cursor += timedelta(days=payday_every)

    cursor = rent_date
    while cursor <= end:
        add(cursor, -rent, "Rent")
        cursor = add_months(cursor, 1)

    cursor = start + timedelta(days=7)
    while cursor <= end:
        add(cursor, -groceries_weekly, "Groceries")
        cursor += timedelta(days=7)

    cursor = start + timedelta(days=30)
    while cursor <= end:
        add(cursor, -subscriptions_monthly, "Estimated subscriptions")
        cursor += timedelta(days=30)

    add(payment_date, -payment, "Payment")

    running = round(balance, 2)
    rows = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        changes = events.get(day, [])
        # Inflows are booked first on same-day transactions.
        changes = sorted(changes, key=lambda item: item[0], reverse=True)
        running = round(running + sum(amount for amount, _ in changes), 2)
        rows.append({"date": day, "balance": running,
                     "events": ", ".join(note for _, note in changes) or "—"})
    return pd.DataFrame(rows)


def goal_plan(goal: float, already_saved: float, months: int,
              paycheck: float, payday_every: int,
              rent: float, groceries_weekly: float,
              subscriptions_monthly: float) -> dict:
    """Rough goal affordability check; not a guarantee or financial advice."""
    needed = max(0.0, goal - already_saved)
    monthly_target = needed / months
    monthly_income = paycheck * 30.44 / payday_every
    monthly_essentials = rent + groceries_weekly * 30.44 / 7 + subscriptions_monthly
    headroom = monthly_income - monthly_essentials
    return {"needed": needed, "monthly_target": monthly_target,
            "weekly_target": monthly_target * 12 / 52,
            "monthly_headroom": headroom,
            "possible": headroom >= monthly_target}
