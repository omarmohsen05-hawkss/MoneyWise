"""Explainable heuristics: warnings are NOT proof of fraud."""
import re
from ipaddress import ip_address
from urllib.parse import urlparse


SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly"}
PAYMENT_PRESSURE = [
    (r"\b(immediately|urgent|right now|act now)\b", "Urgent language creates pressure to pay quickly."),
    (r"\b(account suspended|classes cancelled|final warning|legal action)\b", "Threatening consequences may be a pressure tactic."),
    (r"\b(gift cards?|cryptocurrency|bitcoin|wire transfer)\b", "Unusual or hard-to-reverse payment methods deserve verification."),
    (r"\b(password|social security number|ssn|verification code|one.time code)\b", "Request for sensitive information needs independent verification."),
]
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def analyze_message(message: str, link: str = "") -> dict:
    text = (message or "")[:5000]
    found = [link.strip()] if link.strip() else []
    found += URL_PATTERN.findall(text)
    alerts = []
    for pattern, reason in PAYMENT_PRESSURE:
        if re.search(pattern, text, flags=re.IGNORECASE):
            alerts.append(reason)

    for raw in found[:5]:
        raw = raw.rstrip(".,);]>")
        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            if parsed.scheme not in ("http", "https") or not host:
                alerts.append("Link format is invalid or incomplete; do not open it.")
                continue
            if parsed.scheme == "http":
                alerts.append("Link uses HTTP instead of HTTPS. Avoid entering personal data.")
            if host in SHORTENERS:
                alerts.append("Shortened link hides the final destination.")
            try:
                ip_address(host)
                alerts.append("Link uses a numerical IP address instead of a domain name.")
            except ValueError:
                pass
            if host.startswith("xn--") or ".xn--" in host:
                alerts.append("Internationalized domain needs careful verification.")
            if "@" in parsed.netloc:
                alerts.append("Link contains an @ symbol that can disguise its destination.")
        except ValueError:
            alerts.append("Unable to inspect link safely; verify it independently.")

    alerts = list(dict.fromkeys(alerts))
    if len(alerts) >= 3:
        status = "Multiple warning signs"
    elif alerts:
        status = "Review recommended"
    else:
        status = "No listed warning signs detected"
    return {"alerts": alerts, "status": status}
