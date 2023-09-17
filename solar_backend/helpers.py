from fastapi_mail import MessageSchema, MessageType
from solar_backend.config import fastmail, settings

async def send_verify_mail(email: str, token: str) -> None:
    verify_url = f"{settings.BASE_URL}verify?token={token}"
    html = f"""<p>Um deine Email-Adresse zu bestätigen klicke auf folgenden Link</p><br>
    <a href="{verify_url}">verify_url</a>"""
    message = MessageSchema(
        subject="Email-Adresse Best&auml;tigen",
        recipients=[email],
        body=html,
        subtype=MessageType.html)
    await fastmail.send_message(message)
    