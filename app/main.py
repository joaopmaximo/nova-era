import csv
import io
from datetime import timedelta
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from fastapi.templating import Jinja2Templates

from app.database import engine, get_db, Base
from app.models import Client, User
from app.auth import authenticate_user, create_access_token, login_required, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize database and default user
Base.metadata.create_all(bind=engine)

def create_admin():
    db = next(get_db())
    admin = db.scalars(select(User).where(User.username == "admin")).first()
    if not admin:
        hashed_pw = get_password_hash("admin")
        admin = User(username="admin", hashed_password=hashed_pw)
        db.add(admin)
        db.commit()

create_admin()

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Usuário ou senha incorretos"
        })
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request, 
    db: Session = Depends(get_db), 
    page: int = 1, 
    size: int = 10,
    search: str = None,
    user: User = Depends(login_required)
):
    query = select(Client)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Client.name.ilike(search_filter),
                Client.email.ilike(search_filter),
                Client.document.ilike(search_filter)
            )
        )
    
    total_clients = db.scalar(select(func.count()).select_from(query.subquery()))
    total_pages = (total_clients + size - 1) // size if total_clients > 0 else 1
    
    page = max(1, min(page, total_pages))
    
    clients = db.scalars(
        query.order_by(Client.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    
    return templates.TemplateResponse("clients.html", {
        "request": request, 
        "clients": clients,
        "page": page,
        "total_pages": total_pages,
        "total_clients": total_clients,
        "size": size,
        "search": search or "",
        "user": user
    })

@app.get("/export/csv")
async def export_csv(
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    clients = db.scalars(select(Client)).all()
    
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow(["Nome", "Email", "Telefone", "Documento", "Endereço"])
    
    for client in clients:
        writer.writerow([
            client.name,
            client.email,
            client.phone or "",
            client.document or "",
            client.address or ""
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"}
    )


@app.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    if not file.filename.endswith('.csv'):
        return {"success": False, "message": "Por favor, selecione um arquivo CSV."}
    
    try:
        content = await file.read()
        # Decode content, handling BOM if present
        text_content = content.decode('utf-8-sig')
        stream = io.StringIO(text_content)
        
        # Try semicolon first, then comma
        dialect = csv.Sniffer().sniff(text_content[:1024])
        reader = csv.DictReader(stream, dialect=dialect)
    except Exception:
        # Fallback to semicolon if sniffer fails
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=';')

    added = 0
    skipped = 0
    
    for row in reader:
        # Normalize keys (some CSVs might have spaces or different capitalization)
        row = {k.strip().lower(): v for k, v in row.items() if k}
        
        name = row.get('nome') or row.get('name')
        email = row.get('email')
        phone = row.get('telefone') or row.get('phone')
        document = row.get('documento') or row.get('document')
        address = row.get('endereço') or row.get('address') or row.get('endereco')
        
        if not name or not email:
            skipped += 1
            continue
            
        existing = db.scalars(select(Client).where(Client.email == email)).first()
        if existing:
            skipped += 1
            continue
            
        client = Client(name=name, email=email, phone=phone, document=document, address=address)
        db.add(client)
        added += 1
    
    db.commit()
    
    return {
        "success": True, 
        "message": f"Importação concluída: {added} adicionados, {skipped} ignorados (duplicados ou inválidos)."
    }

@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    existing = db.scalars(select(Client).where(Client.email == email)).first()
    
    if existing:
        return {"success": False, "message": "Email já cadastrado!"}
    
    client = Client(name=name, email=email, phone=phone, document=document, address=address)
    db.add(client)
    db.commit()
    
    return {"success": True, "message": "Cliente cadastrado com sucesso!"}

@app.get("/clients/{client_id}")
async def get_client(
    client_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    client = db.get(Client, client_id)
    if not client:
        return {"success": False, "message": "Cliente não encontrado"}
    return {
        "success": True, 
        "client": {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "phone": client.phone,
            "document": client.document,
            "address": client.address
        }
    }

@app.post("/clients/{client_id}/update")
async def update_client(
    client_id: int,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    client = db.get(Client, client_id)
    if not client:
        return {"success": False, "message": "Cliente não encontrado"}
    
    existing = db.scalars(select(Client).where(Client.email == email, Client.id != client_id)).first()
    if existing:
        return {"success": False, "message": "Este email já está sendo usado por outro cliente!"}
    
    client.name = name
    client.email = email
    client.phone = phone
    client.document = document
    client.address = address
    
    db.commit()
    return {"success": True, "message": "Cliente atualizado com sucesso!"}

@app.post("/clients/{client_id}/delete")
async def delete_client(
    client_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    client = db.get(Client, client_id)
    if not client:
        return {"success": False, "message": "Cliente não encontrado"}
    
    db.delete(client)
    db.commit()
    return {"success": True, "message": "Cliente removido com sucesso!"}
