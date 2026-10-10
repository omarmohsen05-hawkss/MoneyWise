"""CSV normalization and explainable transaction analysis."""
import re
from io import BytesIO

import pandas as pd

REQUIRED = ("date", "description", "amount")


def load_csv(contents: bytes) -> pd.DataFrame:
    if len(contents) > 2_000_000:
        raise ValueError("Please upload a CSV smaller than 2 MB.")
    try:
        df = pd.read_csv(BytesIO(contents), nrows=5001)
    except Exception as exc:
        raise ValueError("Couldn't read CSV. Please use a standard comma-separated file.") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not set(REQUIRED).issubset(df.columns):
        raise ValueError("CSV must have date,description,amount columns.")
    if len(df) > 5000:
        raise ValueError("CSV may contain at most 5,000 rows.")
    df = df[list(REQUIRED)].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["description"] = df["description"].fillna("").astype(str).str.slice(0, 100)
    df = df.dropna(subset=["date", "amount"])
    if df.empty:
        raise ValueError("No valid transactions found. Dates should look like YYYY-MM-DD.")
    return df.sort_values("date", ascending=False).reset_index(drop=True)


def merchant_name(description: str) -> str:
    text = re.sub(r"\b\d{3,}\b", "", description.upper())
    return re.sub(r"\s+", " ", text).strip() or "UNKNOWN"


def inspect(df: pd.DataFrame) -> dict:
    spend = df[df.amount < 0].copy()
    spend["merchant"] = spend.description.map(merchant_name)
    spend["cost"] = -spend.amount

    duplicates = spend[spend.duplicated(["date", "merchant", "cost"], keep=False)].copy()
    threshold = max(100.0, 2.5 * float(spend.cost.median())) if not spend.empty else 100.0
    unusual = spend[spend.cost >= threshold].copy()

    recurring = []
    for merchant, group in spend.groupby("merchant"):
        group = group.sort_values("date").drop_duplicates("date")
        dates = group["date"].tolist()
        if len(dates) < 2:
            continue
        gaps = [(b-a).days for a, b in zip(dates, dates[1:])]
        if len(gaps) and all(25 <= days <= 35 for days in gaps[-2:]):
            latest = float(group.iloc[-1].cost)
            previous = float(group.iloc[-2].cost)
            recurring.append({"Merchant": merchant, "Latest charge": latest,
                              "Change": round(latest - previous, 2),
                              "Occurrences": len(group)})
    recurring.sort(key=lambda x: x["Latest charge"], reverse=True)
    return {"spent": float(spend.cost.sum()), "transactions": len(df),
            "recurring": recurring, "duplicates": duplicates,
            "unusual": unusual, "threshold": threshold,
            "monthly_estimate": sum(item["Latest charge"] for item in recurring)}
