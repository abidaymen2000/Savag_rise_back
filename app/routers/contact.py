from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader, pass_eval_context
from app.schemas.contact import ContactMessage
from app.utils.email import send_email
from app.config import settings
from markupsafe import Markup, escape

router = APIRouter(tags=["contact"])

# Initialisation de Jinja avec un filtre nl2br
jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True
)

@pass_eval_context
def nl2br(eval_ctx, value: str) -> Markup:
    """
    Transforme les sauts de ligne en <br> pour l’email HTML.
    """
    escaped = escape(value)
    result = escaped.replace("\n", "<br>\n")
    return Markup(result)

jinja_env.filters["nl2br"] = nl2br

@router.post(
    "/contact",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Envoyer un message depuis le formulaire de contact"
)
async def submit_contact(
    payload: ContactMessage,
    background_tasks: BackgroundTasks
):
    # 1) Charge le template HTML
    template = jinja_env.get_template("contact_email.html")
    html_body = template.render(
        full_name=payload.full_name,
        email=payload.email,
        subject=payload.subject,
        message=payload.message
    )

    # 2) Prépare le fallback texte brut
    text_body = (
        f"Vous avez reçu un nouveau message de contact :\n\n"
        f"Nom    : {payload.full_name}\n"
        f"Email  : {payload.email}\n"
        f"Sujet  : {payload.subject}\n\n"
        f"Message :\n{payload.message}"
    )

    # 3) Envoi en background
    background_tasks.add_task(
        send_email,
        subject=f"[Contact] {payload.subject}",
        recipient=settings.ADMIN_EMAIL,
        body=text_body,
        html=html_body
    )

    # 4) Réponse JSON au client
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"message": "Votre message a bien été envoyé, nous vous répondrons sous peu."}
    )
