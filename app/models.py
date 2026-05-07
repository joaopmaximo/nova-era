from sqlalchemy import Column, Integer, String, Date
from app.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    document = Column(String(20))
    address = Column(String(200))
