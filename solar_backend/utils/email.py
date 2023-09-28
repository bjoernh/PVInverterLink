from fastapi_mail import MessageSchema, MessageType
from solar_backend.config import fastmail, settings

async def send_verify_mail(email: str, token: str) -> bool:
    verify_url = f"{settings.BASE_URL}verify?token={token}"
    html = f"""<p>Um deine Email-Adresse zu bestätigen klicke auf folgenden Link</p><br>
    <a href="{verify_url}">Email verifizieren</a>"""
    message = MessageSchema(
        subject="Email-Adresse Bestätigen",
        recipients=[email],
        body=html,
        subtype=MessageType.html)
    try:
        await fastmail.send_message(message)
        return True
    except:
        return False
    

async def send_reset_passwort_mail(email: str, token: str) -> bool:
    verify_url = f"{settings.BASE_URL}reset_passwort?token={token}"
    html = f"""<p>Um dein Passwort zurückzusetzen klicke auf folgenden Link</p><br>
    <a href="{verify_url}">Passwort Zurücksetzen</a>"""
    message = MessageSchema(
        subject="Email-Adresse zurücksetzen",
        recipients=[email],
        body=html,
        subtype=MessageType.html)
    try:
        await fastmail.send_message(message)
        return True
    except:
        return False