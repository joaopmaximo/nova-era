import csv
import io
import os
from datetime import timedelta, date, datetime
from fastapi import FastAPI, Form, Request, Depends, HTTPException, status, UploadFile, File, Response
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from fastapi.templating import Jinja2Templates

from app.database import engine, get_db, Base
from app.models import Student, User, Course, Turma, Enrollment, RollCall, Attendance
from app.auth import authenticate_user, create_access_token, login_required, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from xhtml2pdf import pisa

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
    user: User = Depends(login_required)
):
    # Turmas is now the home page
    return await list_turmas(request, db, user)

@app.get("/alunos", response_class=HTMLResponse)
async def list_alunos(
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

@app.get("/alunos/{student_id}/perfil", response_class=HTMLResponse)
async def student_profile(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    
    # Calculate attendance statistics
    attendance_data = []
    for enrollment in student.enrollments:
        total = len(enrollment.attendances)
        present = sum(1 for a in enrollment.attendances if a.presence)
        absent = total - present
        rate = (present / total * 100) if total > 0 else 100
        attendance_data.append({
            "turma": enrollment.turma,
            "total": total,
            "present": present,
            "absent": absent,
            "rate": rate
        })

    return templates.TemplateResponse("student_profile.html", {
        "request": request,
        "student": student,
        "attendance_data": attendance_data,
        "user": user
    })

# --- Courses CRUD ---

@app.get("/cursos", response_class=HTMLResponse)
async def list_courses(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    courses = db.scalars(select(Course).order_by(Course.name)).all()
    return templates.TemplateResponse("courses.html", {
        "request": request,
        "courses": courses,
        "user": user
    })

@app.post("/cursos")
async def create_course(
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    course = Course(name=name)
    db.add(course)
    db.commit()
    return RedirectResponse(url="/cursos", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/cursos/{course_id}/update")
async def update_course(
    course_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    course = db.get(Course, course_id)
    if course:
        course.name = name
        db.commit()
    return RedirectResponse(url="/cursos", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/cursos/{course_id}/delete")
async def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    course = db.get(Course, course_id)
    if course:
        db.delete(course)
        db.commit()
    return RedirectResponse(url="/cursos", status_code=status.HTTP_303_SEE_OTHER)

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
    ignored_list = []
    
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
            reason = "Nome ou Email ausentes"
            print(f"[CSV IMPORT] IGNORADO: {name or 'S/ Nome'} | Motivo: {reason}")
            ignored_list.append(f"{name or 'S/ Nome'} ({reason})")
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
            # Handle comma or semicolon separated lists
            separators = [',', ';']
            current_turmas = [turmas_str]
            for sep in separators:
                new_list = []
                for t in current_turmas:
                    new_list.extend([item.strip() for item in t.split(sep)])
                current_turmas = new_list

            for t_input in current_turmas:
                if not t_input: continue
                
                turma = None
                # Try to parse "Course Name (YYYY-MM-DD)" or similar
                if "(" in t_input and t_input.endswith(")"):
                    try:
                        course_part = t_input[:t_input.find("(")].strip()
                        date_part = t_input[t_input.find("(")+1 : -1].strip()
                        
                        # Match by course name and start_date
                        search_date = datetime.strptime(date_part, "%Y-%m-%d").date()
                        turma = db.scalars(
                            select(Turma).join(Turma.course)
                            .where(Course.name.ilike(course_part), Turma.start_date == search_date)
                        ).first()
                    except Exception:
                        turma = None # Fallback to name-only match
                
                # Fallback: Match just by course name (picks the most recent/active one)
                if not turma:
                    clean_name = t_input.split('(')[0].strip() if '(' in t_input else t_input.strip()
                    turma = db.scalars(
                        select(Turma).join(Turma.course)
                        .where(Course.name.ilike(clean_name))
                        .order_by(Turma.start_date.desc())
                    ).first()

                if turma:
                    # Check if already enrolled to avoid duplicates in the same import
                    existing_enrollment = db.scalars(
                        select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.class_id == turma.id)
                    ).first()
                    if not existing_enrollment:
                        enrollment = Enrollment(student_id=student.id, class_id=turma.id)
                        db.add(enrollment)
                else:
                    print(f"[CSV IMPORT] AVISO: Turma/Curso não encontrado: '{t_input}' para o aluno {name}")
                    
        added += 1
    
    db.commit()
    
    message = f"Importação concluída: {added} adicionados."
    if ignored_list:
        message += f" {len(ignored_list)} ignorados: {', '.join(ignored_list[:5])}"
        if len(ignored_list) > 5:
            message += " ..."

    return {
        "success": True, 
        "message": message,
        "added": added,
        "ignored": ignored_list
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

@app.post("/turmas/{turma_id}/update")
async def update_turma(
    turma_id: int,
    course_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    turma = db.get(Turma, turma_id)
    if turma:
        turma.course_id = course_id
        turma.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        turma.end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
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

from pydantic import BaseModel

class BulkAssignRequest(BaseModel):
    student_ids: List[int]
    turma_id: int

class BulkDeleteRequest(BaseModel):
    student_ids: List[int]

@app.post("/alunos/bulk/assign")
async def bulk_assign_students(
    request: BulkAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    turma = db.get(Turma, request.turma_id)
    if not turma:
        return {"success": False, "message": "Turma não encontrada"}
    
    added = 0
    for s_id in request.student_ids:
        # Check if already enrolled
        existing = db.scalars(
            select(Enrollment).where(Enrollment.student_id == s_id, Enrollment.class_id == request.turma_id)
        ).first()
        
        if not existing:
            enrollment = Enrollment(student_id=s_id, class_id=request.turma_id)
            db.add(enrollment)
            added += 1
            
    db.commit()
    return {"success": True, "message": f"{added} alunos matriculados com sucesso na turma {turma.course.name}."}

@app.post("/alunos/bulk/delete")
async def bulk_delete_students(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    count = 0
    for s_id in request.student_ids:
        student = db.get(Student, s_id)
        if student:
            db.delete(student)
            count += 1
            
    db.commit()
    return {"success": True, "message": f"{count} alunos removidos com sucesso."}

@app.post("/reports/bulk/frequency")
async def report_bulk_frequency(
    student_ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    all_students_data = []
    
    for s_id in student_ids:
        student = db.get(Student, s_id)
        if not student:
            continue
            
        attendance_data = []
        for enrollment in student.enrollments:
            total = len(enrollment.attendances)
            present = sum(1 for a in enrollment.attendances if a.presence)
            absent = total - present
            rate = (present / total * 100) if total > 0 else 100
            attendance_data.append({
                "turma": enrollment.turma,
                "attendances": sorted(enrollment.attendances, key=lambda x: x.roll_call.week_start, reverse=True),
                "total": total,
                "present": present,
                "absent": absent,
                "rate": rate
            })
            
        all_students_data.append({
            "student": student,
            "attendance_data": attendance_data
        })

    if not all_students_data:
        raise HTTPException(status_code=400, detail="Nenhum aluno encontrado")

    pdf_content = render_pdf("pdf/bulk_frequency.html", {
        "all_students_data": all_students_data,
        "now": datetime.now()
    })
    
    return Response(content=pdf_content, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=frequencias_em_massa.pdf"
    })

def render_pdf(template_path: str, context: dict):
    template = templates.get_template(template_path)
    html = template.render(context)
    result = io.BytesIO()
    pisa.pisaDocument(io.BytesIO(html.encode("utf-8")), result)
    return result.getvalue()

# --- PDF Reports ---

@app.post("/reports/roll_calls")
async def report_roll_calls(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    form_data = await request.form()
    roll_call_ids = [int(v) for k, v in form_data.items() if k.startswith('roll_call_ids')]
    
    if not roll_call_ids:
        roll_call_ids = [int(v) for v in form_data.getlist('roll_call_ids')]

    if not roll_call_ids:
        raise HTTPException(status_code=400, detail="Nenhuma chamada selecionada")
    
    roll_calls = db.scalars(
        select(RollCall).where(RollCall.id.in_(roll_call_ids)).order_by(RollCall.week_start)
    ).all()
    
    if not roll_calls:
        raise HTTPException(status_code=404, detail="Chamadas não encontradas")
    
    turma = roll_calls[0].turma
    
    pdf_content = render_pdf("pdf/roll_call_journal.html", {
        "turma": turma,
        "roll_calls": roll_calls,
        "now": datetime.now()
    })
    
    return Response(content=pdf_content, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=diario_classe_{turma.id}.pdf"
    })

@app.get("/reports/student/{student_id}/frequency")
async def report_student_frequency(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    
    attendance_data = []
    for enrollment in student.enrollments:
        total = len(enrollment.attendances)
        present = sum(1 for a in enrollment.attendances if a.presence)
        absent = total - present
        rate = (present / total * 100) if total > 0 else 100
        attendance_data.append({
            "turma": enrollment.turma,
            "attendances": sorted(enrollment.attendances, key=lambda x: x.roll_call.week_start, reverse=True),
            "total": total,
            "present": present,
            "absent": absent,
            "rate": rate
        })

    pdf_content = render_pdf("pdf/student_frequency.html", {
        "student": student,
        "attendance_data": attendance_data,
        "now": datetime.now()
    })
    
    return Response(content=pdf_content, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=frequencia_{student.id}.pdf"
    })

@app.get("/reports/blank_enrollment")
async def report_blank_enrollment(
    user: User = Depends(login_required)
):
    pdf_content = render_pdf("pdf/blank_enrollment.html", {"now": datetime.now()})
    return Response(content=pdf_content, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=ficha_matricula_vazia.pdf"
    })

@app.get("/reports/blank_roll_call")
async def report_blank_roll_call(
    turma_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(login_required)
):
    turma = db.get(Turma, turma_id) if turma_id else None
    pdf_content = render_pdf("pdf/blank_roll_call.html", {
        "turma": turma,
        "now": datetime.now()
    })
    return Response(content=pdf_content, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=lista_chamada_vazia.pdf"
    })

