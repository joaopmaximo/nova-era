from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi.templating import Jinja2Templates

from app.database import engine, get_db, Base
from app.models import Client

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="0;url=/clients" />
        </head>
        <body>
            <p>Redirecting...</p>
        </body>
        </html>
    """)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db)
):
    existing = db.scalars(select(Client).where(Client.email == email)).first()
    
    if existing:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "message": "Email já cadastrado!",
            "success": False
        })
    
    client = Client(name=name, email=email, phone=phone, document=document, address=address)
    db.add(client)
    db.commit()
    
    return templates.TemplateResponse("register.html", {
        "request": request,
        "message": "Cliente cadastrado com sucesso!",
        "success": True
    })


@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db)):
    clients = db.scalars(select(Client)).all()
    return templates.TemplateResponse("clients.html", {"request": request, "clients": clients})
