from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ---------------------------------------------------------
# 1. Import Settings và Base từ project của bạn
# ---------------------------------------------------------
from app.core.config import settings
from app.core.database import Base

# Import tất cả các model để Base nhận diện được (quan trọng cho autogenerate)
from app.models.student import Student 
# Nếu có thêm model khác, hãy import tiếp ở đây
# from app.models.teacher import Teacher 

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------
# 2. Gán Metadata để Alembic so sánh schema
# ---------------------------------------------------------
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Lấy URL từ settings thay vì file ini
    url = settings.DATABASE_URL
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # ---------------------------------------------------------
    # 3. Inject DATABASE_URL từ settings vào cấu hình Alembic
    # ---------------------------------------------------------
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}
    
    # Ghi đè sqlalchemy.url bằng giá trị thật từ code Python
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration, # Sử dụng dictionary đã sửa
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()