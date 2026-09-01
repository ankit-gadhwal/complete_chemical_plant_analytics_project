from src.db.models import User,UserRole
from .schemas import UserCreateModel
from .utils import generate_password_hash
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
import uuid
from src.error import UserAlreadyExists
from .utils import (create_access_token,verify_password,
                    create_url_safe_token,decode_url_safe_token)
from src.celery_tasks import send_email
from fastapi.responses import JSONResponse
from datetime import timedelta,datetime
from src.error import InvalidCredentials
from .schemas import UserCreateModel,UserModel,UserLoginModel,UserSignupResponse
from fastapi import APIRouter, Depends, status, BackgroundTasks
from src.db.main import get_session
from src.config import Config
from src.mail import send_email_async

REFRESH_TOKEN_EXPIRY = 2

async def send_verification_email(email: str, link: str):
    html = f"""
    <h1>Verify your Email</h1>
    <p>Please click this <a href="{link}">link</a> to verify your email</p>
    """
    await send_email_async(recipients=[email], subject="Verify Your Email", body=html)

class UserService:
    async def login_users(self,
    login_data: UserLoginModel,session:AsyncSession) -> dict:
        email = login_data.email
        password = login_data.password

        user = await self.get_user_by_email(email,session)

        if user is not None:
            password_valid = verify_password(password,user.password_hash)

            if password_valid:
                access_token = create_access_token(user_data={"email":user.email,"user_uid":str(user.uid)})

                refresh_token = create_access_token(user_data={"email":user.email,"user_uid": str(user.uid)},
                                            refresh=True,
                                            expiry=timedelta(days = REFRESH_TOKEN_EXPIRY),)

                return JSONResponse(
                    content={
                    "message": "Login successful",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": {"email":user.email,"uid": str(user.uid)}
                })

        raise InvalidCredentials()


    async def create_user_account(
        self,
        user_data: UserCreateModel,
        session: AsyncSession,
        background_tasks: BackgroundTasks | None = None,
    ):
        email = user_data.email
        user_exists = await self.user_exists(email, session)
        if user_exists:
            raise UserAlreadyExists()
        new_user = await self.create_user(user_data, session)

        return UserSignupResponse(
            message="Account created and verified successfully! You can now log in directly.",
            user=new_user,
            verification_link=None,
        )

    
    async def get_user_by_uid(self,user_uid: uuid.UUID,
        session: AsyncSession,) -> User | None:

        statement = select(User).where(User.uid == user_uid)

        result = await session.exec(statement)

        return result.first()

    async def get_user_by_email(self,email:str,session:AsyncSession):
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        user = result.first()
        return user

    async def user_exists(self,email:str,session: AsyncSession):
        user = await self.get_user_by_email(email,session)
        return True if user is not None else False

    async def create_user(self,user_data: UserCreateModel,session: AsyncSession) -> User:
        if await self.user_exists(user_data.email, session):
            raise UserAlreadyExists()
        user_data_dict = user_data.model_dump()
        password = user_data_dict.pop("password")
        new_user = User(**user_data_dict,
                        password_hash=generate_password_hash(password),
                        role=UserRole.USER,          # Every new user is a normal user
                        is_active=True,
                        is_verified=True,            # Auto-verified directly on signup
                        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user

    async def update_user(self,user:User,user_data:dict,session:AsyncSession):

        for k,v in user_data.items():
            setattr(user,k,v)

        await session.commit()

        return user    