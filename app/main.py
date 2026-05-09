import csv
import io
import os
from datetime import timedelta
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from fastapi.templating import Jinja2Templates

from app.database import engine, get_db, Base
from app.models import Student, User, Course
from app.auth import authenticate_user, create_access_token, login_required, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize database and default data
Base.metadata.create_all(bind=engine)

def init_db():
    db = next(get_db())
    
    # Initialize Admin
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    admin = db.scalars(select(User).where(User.username == admin_username)).first()
    if not admin:
        hashed_pw = get_password_hash(admin_password)
        admin = User(username=admin_username, hashed_password=hashed_pw)
        db.add(admin)
    
    # Initialize Courses
    course_names = ["Inglês Iniciante", "Inglês Avançado", "Espanhol", "Informática"]
    for name in course_names:
        course = db.scalars(select(Course).where(Course.name == name)).first()
        if not course:
            db.add(Course(name=name))
    
    db.commit()

init_db()

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
    online: bool = False,
    course_id: int = None,
    user: User = Depends(login_required)
):
    query = select(Student)
    
    # Filter by course
    if course_id:
        query = query.join(Student.courses).where(Course.id == course_id)
        
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Student.name.ilike(search_filter),
                Student.email.ilike(search_filter),
                Student.document.ilike(search_filter)
            )
        )
    
    if online:
        query = query.where(Student.is_online == True)
    
    total_students = db.scalar(select(func.count()).select_from(query.distinct().subquery()))
    total_pages = (total_students + size - 1) // size if total_students > 0 else 1
    
    page = max(1, min(page, total_pages))
    
    students = db.scalars(
        query.order_by(Student.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).unique().all()
    
    # Get all courses for the tabs and forms
    all_courses = db.scalars(select(Course).order_by(Course.id)).all()
    
    return templates.TemplateResponse("students.html", {
        "request": request, 
        "students": students,
        "courses": all_courses,
        "page": page,
        "total_pages": total_pages,
        "total_students": total_students,
        "size": size,
        "search": search or "",
        "online": online,
        "course_id": course_id,
        "user": user
    })

from typing import List

@app.get("/export/csv")
async def export_csv(
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    students = db.scalars(select(Student)).all()
    
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow(["Nome", "Email", "Telefone", "Documento", "Endereço", "Online", "Cursos"])
    
    for student in students:
        courses_str = ", ".join([c.name for c in student.courses])
        writer.writerow([
            student.name,
            student.email,
            student.phone or "",
            student.document or "",
            student.address or "",
            "Sim" if student.is_online else "Não",
            courses_str
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alunos.csv"}
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
        # Normalize keys
        row = {k.strip().lower(): v for k, v in row.items() if k}
        
        name = row.get('nome') or row.get('name')
        email = row.get('email')
        phone = row.get('telefone') or row.get('phone')
        document = row.get('documento') or row.get('document')
        address = row.get('endereço') or row.get('address') or row.get('endereco')
        is_online_val = row.get('online') or row.get('is_online')
        
        is_online = False
        if is_online_val:
            is_online = str(is_online_val).lower() in ('sim', 'yes', 'true', '1')
        
        if not name or not email:
            skipped += 1
            continue
            
        existing = db.scalars(select(Student).where(Student.email == email)).first()
        if existing:
            skipped += 1
            continue
            
        student = Student(name=name, email=email, phone=phone, document=document, address=address, is_online=is_online)
        
        # Handle courses from CSV if present
        courses_str = row.get('cursos') or row.get('courses')
        if courses_str:
            course_names = [c.strip() for c in courses_str.split(',')]
            for c_name in course_names:
                course = db.scalars(select(Course).where(Course.name.ilike(c_name))).first()
                if course:
                    student.courses.append(course)
                    
        db.add(student)
        added += 1
    
    db.commit()
    
    return {
        "success": True, 
        "message": f"Importação concluída: {added} adicionados, {skipped} ignorados."
    }

@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    is_online: bool = Form(False),
    course_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    existing = db.scalars(select(Student).where(Student.email == email)).first()
    
    if existing:
        return {"success": False, "message": "Email já cadastrado!"}
    
    student = Student(name=name, email=email, phone=phone, document=document, address=address, is_online=is_online)
    
    if course_ids:
        for c_id in course_ids:
            course = db.get(Course, c_id)
            if course:
                student.courses.append(course)
                
    db.add(student)
    db.commit()
    
    return {"success": True, "message": "Aluno cadastrado com sucesso!"}

@app.get("/students/{student_id}")
async def get_student(
    student_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        return {"success": False, "message": "Aluno não encontrado"}
    return {
        "success": True, 
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "phone": student.phone,
            "document": student.document,
            "address": student.address,
            "is_online": student.is_online,
            "course_ids": [c.id for c in student.courses]
        }
    }

@app.post("/students/{student_id}/update")
async def update_student(
    student_id: int,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    is_online: bool = Form(False),
    course_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        return {"success": False, "message": "Aluno não encontrado"}
    
    existing = db.scalars(select(Student).where(Student.email == email, Student.id != student_id)).first()
    if existing:
        return {"success": False, "message": "Este email já está sendo usado por outro aluno!"}
    
    student.name = name
    student.email = email
    student.phone = phone
    student.document = document
    student.address = address
    student.is_online = is_online
    
    # Update courses
    student.courses = []
    if course_ids:
        for c_id in course_ids:
            course = db.get(Course, c_id)
            if course:
                student.courses.append(course)
    
    db.commit()
    return {"success": True, "message": "Aluno atualizado com sucesso!"}

@app.post("/students/{student_id}/delete")
async def delete_student(
    student_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        return {"success": False, "message": "Aluno não encontrado"}
    
    db.delete(student)
    db.commit()
    return {"success": True, "message": "Aluno removido com sucesso!"}
