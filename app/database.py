from sqlalchemy import create_engine, String, Text, Float, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .core import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled role")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements_json: Mapped[str] = mapped_column(Text, default="{}")

class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    digest: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), default="processed")
    text: Mapped[str] = mapped_column(Text, default="")
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    score: Mapped[float] = mapped_column(Float, default=0)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}")

def init_db(): Base.metadata.create_all(engine)
