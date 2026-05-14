from typing import List, Optional
from sqlmodel import create_engine, Session, select
from sqlalchemy.pool import QueuePool
import config
from models import Employee # Import the Employee model
from datetime import datetime
import logging

# Database URL
DATABASE_URL = (
    f"mysql+mysqlconnector://{config.DATABASE_USER}:{config.DATABASE_PASSWORD}@"
    f"{config.DATABASE_HOST}/{config.DATABASE_DB_NAME}"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# Create the engine with connection pooling
# pool_size: The number of connections to keep open in the pool.
# max_overflow: The number of connections that can be opened beyond the pool_size.
# pool_recycle: Recycle connections after this many seconds. Prevents stale connections.
engine = create_engine(
    DATABASE_URL,
    echo=False, # Set to True to see SQL statements
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600 # Recycle connections after 1 hour
)

def create_db_and_tables():
    """Creates database tables based on SQLModel metadata."""
    # SQLModel.metadata.create_all(engine)
    # For MySQL, it's better to manage table creation via SQL scripts
    # or ensure the table exists before running the app.
    # This function is mainly for ensuring the engine is set up.
    pass

def get_session():
    """Dependency to get a database session."""
    with Session(engine) as session:
        yield session

def list_employees() -> List[Employee]:
    """Select all the employees from the database."""
    with Session(engine) as session:
        statement = select(Employee).order_by(Employee.full_name.desc())
        employees = session.exec(statement).all()
        return employees

def load_employee(employee_id: int) -> Optional[Employee]:
    """Select one the employee from DB and update last_access_time."""
    with Session(engine) as session:
        employee = session.get(Employee, employee_id)
        logging.info(f"Employee {employee} load_employee called with employee_id={employee_id}")

        if employee:
            logging.info("접근 시간 업데이트")
            # 접근 시간 업데이트
            employee.last_access_time = datetime.now()
            session.add(employee)
            session.flush()
            session.commit()
            session.refresh(employee)
            logging.info(f"Employee {employee_id} accessed, last_access_time updated.")

        return employee

def add_employee(employee_data: Employee) -> Employee:
    """Add an employee to the database."""
    with Session(engine) as session:
        session.add(employee_data)
        session.commit()
        session.refresh(employee_data)
        return employee_data

def update_employee(employee_id: int, employee_data: Employee) -> Optional[Employee]:
    """Update an employee in the database."""
    with Session(engine) as session:
        existing_employee = session.get(Employee, employee_id)
        if not existing_employee:
            return None
        
        # Update fields from employee_data
        for key, value in employee_data.dict(exclude_unset=True).items():
            setattr(existing_employee, key, value)
        
        session.add(existing_employee)
        session.commit()
        session.refresh(existing_employee)
        return existing_employee

def delete_employee(employee_id: int):
    """Delete an employee."""
    with Session(engine) as session:
        employee = session.get(Employee, employee_id)
        if employee:
            session.delete(employee)
            session.commit()
