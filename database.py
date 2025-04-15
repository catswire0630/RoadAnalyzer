from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'traffic_data.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DetectionRecord(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    timestamp = Column(DateTime)
    type = Column(String)

class WarningRecord(Base):
    __tablename__ = "warnings"
    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, nullable=True)
    warning_type = Column(String)
    image_path = Column(String)
    timestamp = Column(DateTime)

class QARecord(Base):
    __tablename__ = "qa_records"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(String)
    timestamp = Column(DateTime)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()