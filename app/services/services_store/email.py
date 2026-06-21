# app/utils/email.py
import smtplib
from email.message import EmailMessage
from typing import Optional
from app.config import settings

def send_email(
    subject: str,
    recipient: str,
    body: str,
    html: Optional[str] = None
) -> None:
    """
    Envoie un e-mail multipart/plain+html.

    - subject   : objet du message
    - recipient : adresse de destination
    - body      : contenu texte brut (plain)
    - html      : contenu HTML (optionnel)
    """
    subject = (subject or "").strip()
    recipient = (recipient or "").strip()
    body = body or ""
    html = html or None

    if not recipient:
        raise ValueError("Email recipient is required")
    if not subject:
        raise ValueError(f"Refusing to send email without subject to {recipient}")
    if not body.strip() and not (html and html.strip()):
        raise ValueError(f"Refusing to send empty email to {recipient}")

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient
    msg["Subject"] = subject

    # 1) Toujours ajouter la partie texte
    msg.set_content(body, subtype="plain", charset="utf-8")

    # 2) Si on a un template HTML, on l'ajoute en alternative
    if html:
        msg.add_alternative(html, subtype="html", charset="utf-8")

    # 3) Envoi via SMTP
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
