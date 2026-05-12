import csv
import io
import os
from datetime import timedelta, date, datetime
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from fastapi.templating import Jinja2Templates

from app.database import engine, get_db, Base
from app.models import Student, User, Course, Turma, Enrollment, RollCall, Attendance
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
    turma_id: int = None,
    user: User = Depends(login_required)
):
    query = select(Student)
    
    # Filter by turma
    if turma_id:
        query = query.join(Student.enrollments).where(Enrollment.class_id == turma_id)
        
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
    
    # Get all turmas for the tabs and forms
    all_turmas = db.scalars(select(Turma).order_by(Turma.id.desc())).all()
    
    return templates.TemplateResponse("students.html", {
        "request": request, 
        "students": students,
        "turmas": all_turmas,
        "page": page,
        "total_pages": total_pages,
        "total_students": total_students,
        "size": size,
        "search": search or "",
        "online": online,
        "turma_id": turma_id,
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
    
    writer.writerow(["Nome", "Email", "Telefone", "Tel. Emergência", "CPF", "Endereço", "Turmas", "Observações"])
    
    for student in students:
        turmas_str = ", ".join([f"{e.turma.course.name} ({e.turma.start_date})" for e in student.enrollments])
        writer.writerow([
            student.name,
            student.email,
            student.phone or "",
            student.emergency_phone or "",
            student.document or "",
            student.address or "",
            turmas_str,
            student.observations or ""
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
        text_content = content.decode('utf-8-sig')
        stream = io.StringIO(text_content)
        
        dialect = csv.Sniffer().sniff(text_content[:1024])
        reader = csv.DictReader(stream, dialect=dialect)
    except Exception:
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=';')

    added = 0
    skipped = 0
    
    for row in reader:
        row = {k.strip().lower(): v for k, v in row.items() if k}
        
        name = row.get('nome') or row.get('name')
        email = row.get('email')
        phone = row.get('telefone') or row.get('phone')
        emergency_phone = row.get('tel. emergência') or row.get('emergency_phone')
        document = row.get('cpf') or row.get('documento') or row.get('document')
        address = row.get('endereço') or row.get('address') or row.get('endereco')
        observations = row.get('observações') or row.get('observations')
        
        if not name or not email:
            skipped += 1
            continue
            
        existing = db.scalars(select(Student).where(Student.email == email)).first()
        if existing:
            skipped += 1
            continue
            
        student = Student(
            name=name, 
            email=email, 
            phone=phone, 
            emergency_phone=emergency_phone,
            document=document, 
            address=address, 
            observations=observations,
            is_online=False
        )
        db.add(student)
        db.flush() # Get student.id
        
        turmas_str = row.get('turmas') or row.get('classes')
        if turmas_str:
            turma_names = [t.strip() for t in turmas_str.split(',')]
            for t_name in turma_names:
                # Basic lookup by course name - might need more specific matching for Turmas
                turma = db.scalars(select(Turma).join(Turma.course).where(Course.name.ilike(t_name))).first()
                if turma:
                    enrollment = Enrollment(student_id=student.id, class_id=turma.id)
                    db.add(enrollment)
                    
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
    email: str = Form(None),
    phone: str = Form(None),
    emergency_phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    observations: str = Form(None),
    is_online: bool = Form(False),
    turma_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    if not turma_ids:
        return {"success": False, "message": "O aluno deve ser matriculado em pelo menos uma turma."}

    # Normalize CPF
    clean_cpf = "".join(filter(str.isdigit, document)) if document and document.strip() else None
    
    # Handle empty email string
    clean_email = email.strip() if email and email.strip() else None

    student = Student(
        name=name, 
        email=clean_email, 
        phone=phone, 
        emergency_phone=emergency_phone,
        document=clean_cpf, 
        address=address, 
        observations=observations,
        is_online=is_online
    )
    db.add(student)
    db.flush()
    
    for t_id in turma_ids:
        turma = db.get(Turma, t_id)
        if turma:
            enrollment = Enrollment(student_id=student.id, class_id=turma.id)
            db.add(enrollment)
                
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
            "emergency_phone": student.emergency_phone,
            "document": student.document,
            "address": student.address,
            "observations": student.observations,
            "is_online": student.is_online,
            "turma_ids": [e.class_id for e in student.enrollments]
        }
    }

@app.post("/students/{student_id}/update")
async def update_student(
    student_id: int,
    name: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    emergency_phone: str = Form(None),
    document: str = Form(None),
    address: str = Form(None),
    observations: str = Form(None),
    is_online: bool = Form(False),
    turma_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        return {"success": False, "message": "Aluno não encontrado"}
    
    # Normalize CPF
    clean_cpf = "".join(filter(str.isdigit, document)) if document and document.strip() else None
    
    # Handle empty email string
    clean_email = email.strip() if email and email.strip() else None

    student.name = name
    student.email = clean_email
    student.phone = phone
    student.emergency_phone = emergency_phone
    student.document = clean_cpf
    student.address = address
    student.observations = observations
    student.is_online = is_online
    
    # Update enrollments
    # In a real scenario, we might want to preserve attendance when updating enrollments
    # but for simplicity, we'll replace them if requested.
    if turma_ids:
        # Simple replace strategy: remove old, add new
        for e in student.enrollments:
            db.delete(e)
        db.flush()
        for t_id in turma_ids:
            turma = db.get(Turma, t_id)
            if turma:
                enrollment = Enrollment(student_id=student.id, class_id=turma.id)
                db.add(enrollment)
    
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

# --- Turmas (Classes) ---

@app.get("/turmas", response_class=HTMLResponse)
async def list_turmas(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    turmas = db.scalars(select(Turma).order_by(Turma.id.desc())).all()
    courses = db.scalars(select(Course).order_by(Course.name)).all()
    return templates.TemplateResponse("turmas.html", {
        "request": request,
        "turmas": turmas,
        "courses": courses,
        "user": user
    })

@app.post("/turmas")
async def create_turma(
    course_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    new_turma = Turma(
        course_id=course_id,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    )
    db.add(new_turma)
    db.commit()
    return RedirectResponse(url="/turmas", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/turmas/{turma_id}", response_class=HTMLResponse)
async def turma_details(
    turma_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    turma = db.get(Turma, turma_id)
    if not turma:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    
    # Students not yet in this turma
    enrolled_student_ids = [e.student_id for e in turma.enrollments]
    available_students = db.scalars(
        select(Student).where(Student.id.not_in(enrolled_student_ids) if enrolled_student_ids else True).order_by(Student.name)
    ).all()
    
    return templates.TemplateResponse("turma_details.html", {
        "request": request,
        "turma": turma,
        "available_students": available_students,
        "user": user
    })

@app.post("/turmas/{turma_id}/enroll")
async def enroll_student(
    turma_id: int,
    student_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    enrollment = Enrollment(student_id=student_id, class_id=turma_id)
    db.add(enrollment)
    db.commit()
    return RedirectResponse(url=f"/turmas/{turma_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/enrollments/{enrollment_id}/delete")
async def remove_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment:
        turma_id = enrollment.class_id
        db.delete(enrollment)
        db.commit()
        return RedirectResponse(url=f"/turmas/{turma_id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/turmas", status_code=status.HTTP_303_SEE_OTHER)

# --- Chamadas (Roll Calls) ---

@app.post("/turmas/{turma_id}/roll_calls")
async def create_roll_call(
    turma_id: int,
    week_start: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    end_date = start_date + timedelta(days=6)
    
    roll_call = RollCall(classe_id=turma_id, week_start=start_date, week_end=end_date)
    db.add(roll_call)
    db.commit()
    
    # Pre-populate attendance for all currently enrolled students
    turma = db.get(Turma, turma_id)
    for enrollment in turma.enrollments:
        attendance = Attendance(student_class_id=enrollment.id, roll_call_id=roll_call.id, presence=False)
        db.add(attendance)
    db.commit()
    
    return RedirectResponse(url=f"/roll_calls/{roll_call.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/roll_calls/{roll_call_id}", response_class=HTMLResponse)
async def take_attendance(
    roll_call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    roll_call = db.get(RollCall, roll_call_id)
    if not roll_call:
        raise HTTPException(status_code=404, detail="Chamada não encontrada")
    
    return templates.TemplateResponse("roll_call.html", {
        "request": request,
        "roll_call": roll_call,
        "user": user
    })

@app.post("/roll_calls/{roll_call_id}/submit")
async def submit_attendance(
    roll_call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    form_data = await request.form()
    roll_call = db.get(RollCall, roll_call_id)
    
    for attendance in roll_call.attendances:
        presence_key = f"presence_{attendance.id}"
        attendance.presence = True if form_data.get(presence_key) == "on" else False
    
    db.commit()
    return RedirectResponse(url=f"/turmas/{roll_call.classe_id}", status_code=status.HTTP_303_SEE_OTHER)

