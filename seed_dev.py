import os
import sys

from app.database import SessionLocal, engine, Base
from app.models import Student, Course

if os.getenv("ENVIRONMENT") != "development":
    print("Este script deve ser executado apenas em ambiente de desenvolvimento!")
    sys.exit(1)

def seed_data():
    db = SessionLocal()
    try:
        # 1. Seed Courses
        course_names = ["Inglês Iniciante", "Inglês Avançado", "Espanhol", "Informática"]
        courses = {}
        for name in course_names:
            course = db.query(Course).filter(Course.name == name).first()
            if not course:
                course = Course(name=name)
                db.add(course)
                db.flush()
            courses[name] = course

        # 2. Seed Students
        students_data = [
            {"name": "João Pedro Santos", "email": "joao.santos@email.com", "phone": "11999887766", "document": "12345678901", "address": "Rua das Flores, 100 - São Paulo, SP", "is_online": True, "course_list": ["Inglês Avançado", "Informática"]},
            {"name": "Maria Oliveira Silva", "email": "maria.oliveira@email.com", "phone": "21988776655", "document": "23456789012", "address": "Av. Brasil, 500 - Rio de Janeiro, RJ", "is_online": False, "course_list": ["Espanhol"]},
            {"name": "Carlos Eduardo Ferreira", "email": "carlos.ferreira@email.com", "phone": "31977665544", "document": "34567890123", "address": "Rua Tiradentes, 200 - Belo Horizonte, MG", "is_online": True, "course_list": ["Inglês Iniciante"]},
            {"name": "Ana Paula Costa", "email": "ana.costa@email.com", "phone": "41966554433", "document": "45678901234", "address": "Alameda das Palmeiras, 150 - Curitiba, PR", "is_online": False, "course_list": ["Informática"]},
            {"name": "Paulo Roberto Lima", "email": "paulo.lima@email.com", "phone": "51955443322", "document": "56789012345", "address": "Av. Ipiranga, 800 - Porto Alegre, RS", "is_online": True, "course_list": ["Espanhol", "Inglês Avançado"]},
        ]

        for data in students_data:
            course_list = data.pop("course_list")
            student = db.query(Student).filter(Student.email == data["email"]).first()
            if not student:
                student = Student(**data)
                db.add(student)
            
            # Update online status and courses
            student.is_online = data["is_online"]
            student.courses = [courses[name] for name in course_list]
        
        db.commit()
        print(f"Seed concluído! {len(students_data)} alunos processados.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()