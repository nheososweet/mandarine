from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db
from app.services.student import student as crud_student
from app.schemas.student import Student, StudentCreate, StudentUpdate

router = APIRouter()


@router.get("/", response_model=List[Student])
def get_students(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách học sinh với phân trang
    
    - **skip**: Bỏ qua n bản ghi đầu tiên (mặc định: 0)
    - **limit**: Số lượng bản ghi tối đa (mặc định: 100)
    """
    students = crud_student.get_students(db, skip=skip, limit=limit)
    return students


@router.get("/{student_id}", response_model=Student)
def get_student(
    student_id: int,
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin chi tiết của 1 học sinh theo ID
    """
    student = crud_student.get_student(db, student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học sinh"
        )
    return student


@router.post("/", response_model=Student, status_code=status.HTTP_201_CREATED)
def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db)
):
    """
    Tạo học sinh mới
    
    Yêu cầu:
    - **name**: Tên học sinh (bắt buộc)
    - **email**: Email (bắt buộc, phải unique)
    - **age**: Tuổi (bắt buộc)
    - **grade**: Lớp (bắt buộc)
    """
    # Kiểm tra email đã tồn tại chưa
    existing_student = crud_student.get_student_by_email(db, email=student.email)
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )
    
    return crud_student.create_student(db=db, student=student)


@router.put("/{student_id}", response_model=Student)
def update_student(
    student_id: int,
    student: StudentUpdate,
    db: Session = Depends(get_db)
):
    """
    Cập nhật thông tin học sinh
    """
    # Kiểm tra học sinh có tồn tại không
    existing_student = crud_student.get_student(db, student_id=student_id)
    if not existing_student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học sinh"
        )
    
    # Kiểm tra email mới có bị trùng với học sinh khác không
    student_with_email = crud_student.get_student_by_email(db, email=student.email)
    if student_with_email and student_with_email.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng bởi học sinh khác"
        )
    
    updated_student = crud_student.update_student(db=db, student_id=student_id, student=student)
    return updated_student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db)
):
    """
    Xóa học sinh
    """
    student = crud_student.get_student(db, student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy học sinh"
        )
    
    crud_student.delete_student(db=db, student_id=student_id)
    return None