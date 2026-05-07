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
async def root(request: Request, db: Session = Depends(get_db)):
    clients = db.scalars(select(Client)).all()
    return templates.TemplateResponse("clients.html", {"request": request, "clients": clients})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Redirect to root but with a hint to open the register tab
    return HTMLResponse(content="""
        <script>window.location.href = '/?tab=register';</script>
    """)


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
        return {"success": False, "message": "Email já cadastrado!"}
    
    client = Client(name=name, email=email, phone=phone, document=document, address=address)
    db.add(client)
    db.commit()
    
    return {"success": True, "message": "Cliente cadastrado com sucesso!"}


@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db)):
    clients = db.scalars(select(Client)).all()
    return templates.TemplateResponse("clients.html", {"request": request, "clients": clients})
