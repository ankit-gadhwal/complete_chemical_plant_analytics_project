import uuid
from datetime import datetime,timezone
from sqlmodel import SQLModel, Field, Column,Relationship
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from typing import List,Optional,Dict
from sqlalchemy import ForeignKey
from enum import Enum
from sqlalchemy import func,DateTime,Text
from sqlalchemy import Enum as SQLEnum

class Datasetstatus(str,Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Dataset(SQLModel,table=True):

    __tablename__ = "datasets"

    uid: uuid.UUID = Field(
        sa_column=Column(pg.UUID,primary_key=True,
                         unique=True,
                         nullable=False,
                         default=uuid.uuid4
                         )
    )
    owner_uid: uuid.UUID = Field(
    sa_column=Column(pg.UUID(as_uuid=True),ForeignKey("user_accounts.uid", ondelete="CASCADE"),nullable=False))

    original_filename: str
    stored_filename: str
    file_path: str
    status: Datasetstatus = Field(default = Datasetstatus.PENDING)
    equipment_count: Optional[int] = Field(default=None)
    average_flowrate: Optional[float] = Field(default=None)
    average_pressure: Optional[float] = Field(default=None)
    average_temperature: Optional[float] = Field(default=None)

    min_flowrate: Optional[float] = Field(default=None)
    max_flowrate: Optional[float] = Field(default=None)

    min_pressure: Optional[float] = Field(default=None)
    max_pressure: Optional[float] = Field(default=None)

    min_temperature: Optional[float] = Field(default=None)
    max_temperature: Optional[float] = Field(default=None)

    equipment_summary: Optional[dict] = Field(
        default=None,sa_type=JSONB,nullable=True,)
    inactive_equipment: Optional[list] = Field(default=None, sa_type=JSONB, nullable=True)

    missing_data: Optional[list] = Field(default=None, sa_type=JSONB, nullable=True)
    created_at: datetime = Field(
        sa_column= Column(pg.TIMESTAMP,
                          default=datetime.now,
                          nullable=False)
    )

    updated_at: datetime = Field(
        sa_column = Column(
            pg.TIMESTAMP,
            default=datetime.now,
            onupdate=datetime.now,
            nullable=False
        )
    )

    
    equipments: list["Equipment"] = Relationship(
    back_populates="dataset",
    sa_relationship_kwargs={"cascade": "all, delete-orphan",
        "passive_deletes": True,})

    owner: Optional["User"] = Relationship(back_populates="datasets")

    chat_sessions: list["ChatSession"] = Relationship(
    sa_relationship_kwargs={
        "cascade": "all, delete-orphan"
    })

    def __repr__(self) -> str:
        return f"<Dataset {self.original_filename}>"
    

class Equipment(SQLModel,table=True):
    __tablename__ = "equipment"

    uid: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True
    )

    dataset_uid: uuid.UUID = Field(
    sa_column=Column(
        pg.UUID(as_uuid=True),
        ForeignKey("datasets.uid", ondelete="CASCADE"),
        nullable=False,
    )
)
    equipment_name: str = Field(nullable=False)
    equipment_type: str = Field(nullable=False)
    flowrate: float = Field(nullable=False)
    pressure: float = Field(nullable=False)
    temperature: float = Field(nullable=False)
    created_at: datetime = Field(default_factory = datetime.now,
                                 nullable=False)
    updated_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False)
    
    dataset: Optional["Dataset"] = Relationship(back_populates="equipments")


class UserRole(str,Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    
class User(SQLModel,table=True):
    __tablename__ = "user_accounts"

    uid: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
            info={"description": "Unique identifier for the user account"},
        ),
    )
    username: str
    first_name: str = Field(nullable = True)
    last_name: str = Field(nullable=True)
    is_verified: bool = True
    is_active: bool = Field(default=True)
    role: UserRole = Field(default=UserRole.USER)
    email: str
    password_hash: str = Field(exclude=True)
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(pg.TIMESTAMP, default=datetime.now, nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(pg.TIMESTAMP, default=datetime.now, onupdate=datetime.now, nullable=False)
    )
    datasets: list["Dataset"] = Relationship(back_populates="owner")
    chat_sessions: list["ChatSession"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan"
        })
    def __repr__(self) -> str:
        return f"<User {self.username}>"

class ChatType(str, Enum):
    SQL = "SQL"
    RAG = "RAG"

class ChatSession(SQLModel,table=True):
    __tablename__ = "chat_sessions"


    uid: uuid.UUID = Field(
            default_factory=uuid.uuid4,
            primary_key=True,
            index=True
        )
    owner_uid:uuid.UUID = Field(
        foreign_key="user_accounts.uid",
        nullable=False,
        index=True,ondelete="CASCADE"
    )

    dataset_uid: uuid.UUID = Field(
        foreign_key="datasets.uid",
        nullable=False,
        index=True,ondelete="CASCADE"
    )
    chat_type: ChatType = Field(
        sa_column=Column(SQLEnum(ChatType, names="chat_type"),
            nullable=False,default=ChatType.SQL))
    title: Optional[str] = Field(default=None,max_length=255)

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    )

    updated_at: datetime = Field(
        sa_column=Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ))

    messages: list["ChatMessage"] = Relationship(back_populates="session",
    sa_relationship_kwargs={
        "cascade":"all, delete-orphan","passive_deletes": True,
    })

class MessageRole(str,Enum):
    User = "User"
    ASSISTANT = "ASSISTANT"

class ChatMessage(SQLModel,table=True):
    __tablename__ = "chat_messages"
    uid: uuid.UUID = Field(default_factory=uuid.uuid4,primary_key=True)

    session_uid: uuid.UUID = Field(
        foreign_key="chat_sessions.uid",
        nullable=False,
        index=True,ondelete="CASCADE"
    )

    role: MessageRole
    message: str =  Field(
    sa_column=Column(
        Text,
        nullable=False,))

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False))

    session: Optional[ChatSession] = Relationship(
        back_populates="messages")


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        )
    )

    dataset_uid: uuid.UUID = Field(
        foreign_key="datasets.uid",
        nullable=False,
        index=True,
    )

    owner_uid: uuid.UUID = Field(
        foreign_key="user_accounts.uid",
        nullable=False,
        index=True,
    )

    original_filename: str = Field(nullable=False)

    stored_filename: str = Field(nullable=False)

    file_path: str = Field(nullable=False)

    created_at: datetime = Field(
            sa_column= Column(pg.TIMESTAMP,
                              default=datetime.now,
                              nullable=False))
    
    updated_at: datetime = Field(sa_column = Column(
                pg.TIMESTAMP,default=datetime.now,
                onupdate=datetime.now,nullable=False))

    dataset: "Dataset" = Relationship()