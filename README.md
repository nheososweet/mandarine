# FastAPI Project - Student Management System

## 📁 Cấu trúc Project

```
fastapi-project/
├── alembic/                    # Thư mục quản lý database migrations
│   ├── versions/              # Các file migration
│   └── env.py                 # Cấu hình alembic environment
├── app/
│   ├── __init__.py
│   ├── main.py                # Entry point của ứng dụng
│   ├── config.py              # Cấu hình môi trường (database, secret key,...)
│   ├── database.py            # Setup database connection
│   ├── models/                # SQLAlchemy models (database tables)
│   │   ├── __init__.py
│   │   └── student.py         # Model Student
│   ├── schemas/               # Pydantic schemas (validation & serialization)
│   │   ├── __init__.py
│   │   └── student.py         # Schema cho Student
│   ├── api/                   # API routes
│   │   ├── __init__.py
│   │   ├── deps.py            # Dependencies (get_db, auth,...)
│   │   └── v1/                # API version 1
│   │       ├── __init__.py
│   │       ├── router.py      # Router tổng hợp
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── students.py # CRUD endpoints cho students
│   └── crud/                  # CRUD operations
│       ├── __init__.py
│       └── student.py         # CRUD functions cho Student
├── .env                       # Environment variables
├── .env.example              # Mẫu file .env
├── alembic.ini               # Cấu hình Alembic
├── requirements.txt          # Python dependencies
└── README.md                 # File này
```

## 📖 Giải thích các thư mục

### `alembic/`
- Quản lý database migrations (thay đổi schema database)
- Cho phép version control cho database schema
- Dễ dàng rollback hoặc áp dụng thay đổi database

### `app/models/`
- Chứa SQLAlchemy models - định nghĩa cấu trúc bảng database
- Mỗi model tương ứng với 1 bảng trong database
- Định nghĩa relationships giữa các bảng

### `app/schemas/`
- Pydantic schemas để validate dữ liệu đầu vào/đầu ra
- Tự động generate API documentation
- Type safety và validation

### `app/crud/`
- Business logic cho database operations (Create, Read, Update, Delete)
- Tách biệt logic database khỏi API endpoints
- Dễ dàng test và tái sử dụng

### `app/api/`
- Định nghĩa API endpoints
- Xử lý HTTP requests/responses
- Gọi CRUD functions để thao tác với database

## 🚀 Cài đặt

### 1. Clone project và tạo virtual environment

```bash
# Tạo virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate
```

### 2. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup database

Tạo file `.env` từ `.env.example`:

```bash
cp .env.example .env
```

Sửa thông tin database trong `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/student_db
```

**Lưu ý**: Đảm bảo PostgreSQL đã cài đặt và tạo database `student_db`

```sql
CREATE DATABASE student_db;
```

### 4. Chạy migrations với Alembic

```bash
# Khởi tạo migration đầu tiên (nếu chưa có)
alembic revision --autogenerate -m "Initial migration"

# Áp dụng migrations vào database
alembic upgrade head
```

### 5. Chạy server

```bash
uvicorn app.main:app --reload
```

Server sẽ chạy tại: `http://localhost:8000`

## 📚 API Documentation

Sau khi chạy server, truy cập:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 API Endpoints

### Students

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/students/` | Lấy danh sách học sinh |
| GET | `/api/v1/students/{id}` | Lấy thông tin 1 học sinh |
| POST | `/api/v1/students/` | Tạo học sinh mới |
| PUT | `/api/v1/students/{id}` | Cập nhật thông tin học sinh |
| DELETE | `/api/v1/students/{id}` | Xóa học sinh |

### Ví dụ Request Body (POST/PUT)

```json
{
  "name": "Nguyễn Văn A",
  "email": "nguyenvana@example.com",
  "age": 20,
  "grade": "12A"
}
```

## 🗄️ Làm việc với Alembic

### Tạo migration mới khi thay đổi model

```bash
alembic revision --autogenerate -m "Mô tả thay đổi"
```

### Áp dụng migrations

```bash
# Nâng cấp lên version mới nhất
alembic upgrade head

# Nâng cấp lên version cụ thể
alembic upgrade <revision_id>
```

### Rollback migrations

```bash
# Rollback 1 bước
alembic downgrade -1

# Rollback về version cụ thể
alembic downgrade <revision_id>

# Rollback tất cả
alembic downgrade base
```

### Xem lịch sử migrations

```bash
alembic history
```

### Xem trạng thái hiện tại

```bash
alembic current
```

## 🧪 Testing

Test API bằng cURL:

```bash
# Tạo học sinh mới
curl -X POST "http://localhost:8000/api/v1/students/" \
  -H "Content-Type: application/json" \
  -d '{"name":"Nguyễn Văn A","email":"test@example.com","age":20,"grade":"12A"}'

# Lấy danh sách học sinh
curl -X GET "http://localhost:8000/api/v1/students/"
```

## 📝 Notes

- Project sử dụng async/await cho performance tốt hơn
- Database connection được quản lý bằng dependency injection
- Tất cả packages không fix version để luôn cài bản mới nhất
- Sử dụng Pydantic V2 cho validation

## 🔐 Best Practices được áp dụng

1. **Separation of Concerns**: Model, Schema, CRUD, API tách biệt
2. **Dependency Injection**: Sử dụng FastAPI dependencies
3. **Type Safety**: Python type hints ở mọi nơi
4. **Async/Await**: Xử lý bất đồng bộ
5. **Environment Variables**: Cấu hình qua `.env`
6. **Database Migrations**: Version control cho database schema
7. **API Versioning**: Sẵn sàng cho nhiều versions

## 🛠️ Troubleshooting

### Lỗi connection database
- Kiểm tra PostgreSQL đã chạy chưa
- Kiểm tra thông tin trong `.env` đúng chưa
- Kiểm tra database đã tạo chưa

### Lỗi import modules
- Đảm bảo đã activate virtual environment
- Chạy lại `pip install -r requirements.txt`

### Lỗi migrations
- Xóa thư mục `alembic/versions/` và tạo lại migration
- Kiểm tra model có import đúng trong `alembic/env.py` không