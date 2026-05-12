from sqlalchemy import Column, Integer, String, Boolean, Table, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    document = Column(String(20), nullable=True)
    address = Column(String(200), nullable=True)
    emergency_phone = Column(String(20), nullable=True)
    observations = Column(String(500), nullable=True)
    is_online = Column(Boolean, default=False)
    
    # Relationships
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    
    # Relationship to classes
    classes = relationship("Turma", back_populates="course")

class Turma(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    course = relationship("Course", back_populates="classes")
    enrollments = relationship("Enrollment", back_populates="turma", cascade="all, delete-orphan")
    roll_calls = relationship("RollCall", back_populates="turma", cascade="all, delete-orphan")

class Enrollment(Base):
    __tablename__ = "student_classes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    student = relationship("Student", back_populates="enrollments")
    turma = relationship("Turma", back_populates="enrollments")
    attendances = relationship("Attendance", back_populates="enrollment", cascade="all, delete-orphan")

class RollCall(Base):
    __tablename__ = "roll_call"

    id = Column(Integer, primary_key=True, index=True)
    classe_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)

    turma = relationship("Turma", back_populates="roll_calls")
    attendances = relationship("Attendance", back_populates="roll_call", cascade="all, delete-orphan")

class Attendance(Base):
    __tablename__ = "student_roll_call"

    id = Column(Integer, primary_key=True, index=True)
    student_class_id = Column(Integer, ForeignKey("student_classes.id"), nullable=False)
    roll_call_id = Column(Integer, ForeignKey("roll_call.id"), nullable=False)
    presence = Column(Boolean, nullable=False, default=False)

    enrollment = relationship("Enrollment", back_populates="attendances")
    roll_call = relationship("RollCall", back_populates="attendances")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
