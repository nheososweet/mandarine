from sqlalchemy.orm import Session
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate
from typing import List, Optional


def get_student(db: Session, student_id: int) -> Optional[Student]:
    """Lấy thông tin 1 học sinh theo ID"""
    return db.query(Student).filter(Student.id == student_id).first()


def get_student_by_email(db: Session, email: str) -> Optional[Student]:
    """Lấy học sinh theo email"""
    return db.query(Student).filter(Student.email == email).first()


def get_students(db: Session, skip: int = 0, limit: int = 100) -> List[Student]:
    """Lấy danh sách học sinh với phân trang"""
    return db.query(Student).offset(skip).limit(limit).all()


def create_student(db: Session, student: StudentCreate) -> Student:
    """Tạo học sinh mới"""
    db_student = Student(
        name=student.name,
        email=student.email,
        age=student.age,
        grade=student.grade
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


def update_student(db: Session, student_id: int, student: StudentUpdate) -> Optional[Student]:
    """Cập nhật thông tin học sinh"""
    db_student = get_student(db, student_id)
    if db_student:
        db_student.name = student.name
        db_student.email = student.email
        db_student.age = student.age
        db_student.grade = student.grade
        db.commit()
        db.refresh(db_student)
    return db_student


def delete_student(db: Session, student_id: int) -> Optional[Student]:
    """Xóa học sinh"""
    db_student = get_student(db, student_id)
    if db_student:
        db.delete(db_student)
        db.commit()
    return db_student