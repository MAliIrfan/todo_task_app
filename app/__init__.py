import database
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import BYTEA
import datetime

Base = database.Base


class Todos(database.Base):
    __tablename__ = 'todo'

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(Integer)
    complete = Column(Boolean, default=False)
    file = Column(BYTEA)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    due_at = Column(DateTime)
    completed_at = Column(DateTime)
    # owner_id = Column(Integer, ForeignKey("users.id"))
