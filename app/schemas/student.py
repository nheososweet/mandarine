from pydantic import BaseModel, EmailStr, ConfigDict


class StudentBase(BaseModel):
    name: str
    email: EmailStr
    age: int
    grade: str


class StudentCreate(StudentBase):
    pass


class StudentUpdate(StudentBase):
    pass


class StudentInDB(StudentBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)


class Student(StudentInDB):
    pass