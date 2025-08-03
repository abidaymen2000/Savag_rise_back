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
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient
    msg["Subject"] = subject

    # 1) Toujours ajouter la partie texte
    msg.set_content(body)

    # 2) Si on a un template HTML, on l'ajoute en alternative
    if html:
        msg.add_alternative(html, subtype="html")

    # 3) Envoi via SMTP
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
