import structlog
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from fastapi_mail import MessageSchema, MessageType
from solar_backend.config import fastmail, settings

logger = structlog.get_logger()

# Initialize Jinja2 environment for email templates
email_template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(loader=FileSystemLoader(str(email_template_dir)))


async def send_verify_mail(email: str, token: str) -> bool:
    """Send email verification mail with bilingual HTML template."""
    verify_url = f"{settings.BASE_URL}verify?token={token}"

    # Load and render template
    template = jinja_env.get_template("verify_email.html")
    html = template.render(verify_url=verify_url)

    message = MessageSchema(
        subject="E-Mail-Adresse bestätigen / Verify Email Address - Deye Hard",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    try:
        await fastmail.send_message(message)
        logger.info("Verification email sent", recipient=email)
        return True
    except Exception as e:
        logger.error("Email send failed", error=str(e), recipient=email, exc_info=True)
        return False


async def send_reset_passwort_mail(email: str, token: str) -> bool:
    """Send password reset mail with bilingual HTML template."""
    reset_url = f"{settings.BASE_URL}reset_passwort?token={token}"

    # Load and render template
    template = jinja_env.get_template("reset_password.html")
    html = template.render(reset_url=reset_url)

    message = MessageSchema(
        subject="Passwort zurücksetzen / Reset Password - Deye Hard",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    try:
        await fastmail.send_message(message)
        logger.info("Password reset email sent", recipient=email)
        return True
    except Exception as e:
        logger.error("Email send failed", error=str(e), recipient=email, exc_info=True)
        return False
