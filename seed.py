import logging
from app.core.database import SessionLocal
from app.models.student import Student

# Setup logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_data():
    """
    Function to seed initial data into the database.
    """
    db = SessionLocal()
    try:
        # 1. Check if data already exists to avoid duplication
        # Kiểm tra xem đã có dữ liệu chưa để tránh tạo trùng lặp
        if db.query(Student).first():
            logger.info("Database already contains data. Skipping seed.")
            return

        logger.info("Seeding data...")

        # 2. Create list of dummy students
        # Tạo danh sách sinh viên mẫu
        # Note: Adjust fields (full_name, email, etc.) to match your Student model exactly!
        students = [
            Student(
                full_name="Nguyen Van A",
                email="vana@example.com",
                phone="0901234567",
                age=20,
                gender="Male"
            ),
            Student(
                full_name="Tran Thi B",
                email="thib@example.com",
                phone="0909876543",
                age=21,
                gender="Female"
            ),
            Student(
                full_name="Le Van C",
                email="vanc@example.com",
                phone="0912345678",
                age=22,
                gender="Male"
            ),
        ]

        # 3. Add to session and commit
        # Thêm vào session và lưu vào database
        db.add_all(students)
        db.commit()
        
        logger.info("✅ Data seeded successfully!")

    except Exception as e:
        logger.error(f"❌ Error seeding data: {e}")
        db.rollback() # Rollback if error occurs
    finally:
        db.close() # Always close the connection

if __name__ == "__main__":
    seed_data()