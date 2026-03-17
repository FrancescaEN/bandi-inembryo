from sqlalchemy import Column, String, Text
from database import Base

class Bando(Base):
    __tablename__ = "bandi"

    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    url = Column(String, unique=True)
    summary = Column(Text)
    ente = Column(String)
    published_at = Column(String)
    deadline = Column(String)
    source = Column(String)