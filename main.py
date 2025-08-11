from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import httpx
import os
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta

# Cargar variables de entorno
load_dotenv()
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM")
RESEND_TO = os.getenv("RESEND_TO")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN")

# Rate limit: máx 5 emails por hora por IP
rate_limits = defaultdict(list)

# Modelo de datos esperado
class ContactData(BaseModel):
    name: str
    email: EmailStr
    message: str

app = FastAPI()

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "API FastAPI corriendo..."}


@app.post("/contact")
async def send_email(contact: ContactData, request: Request):
    client_ip = request.client.host

    # Rate limiting simple
    now = datetime.utcnow()
    rate_limits[client_ip] = [
        t for t in rate_limits[client_ip] if now - t < timedelta(hours=1)
    ]
    if len(rate_limits[client_ip]) >= 5:
        raise HTTPException(status_code=429, detail="Has excedido el límite de mensajes por hora.")

    rate_limits[client_ip].append(now)

    # Petición a Resend
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": RESEND_FROM, 
                    "to": [RESEND_TO],
                    "subject": f"Nuevo mensaje de {contact.name}",
                    "text": f"De: {contact.name} <{contact.email}>\n\n{contact.message}",
                },
            )
        if response.status_code >= 400:
            raise Exception(response.text)
        return {"message": "Mensaje enviado con éxito."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")
