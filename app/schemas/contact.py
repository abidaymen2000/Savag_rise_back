from pydantic import BaseModel, EmailStr, Field

class ContactMessage(BaseModel):
    full_name: str = Field(..., title="Nom complet")
    email:    EmailStr = Field(..., title="Adresse email")
    subject:  str = Field(..., title="Sujet")
    message:  str = Field(..., title="Corps du message", min_length=10)
