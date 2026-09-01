from fastapi import APIRouter, Depends, status, BackgroundTasks
from .schemas import (
    UserCreateModel,
    UserModel,
    UserLoginModel,
    PasswordResetConfirmModel,
    PasswordResetRequestModel,
    EmailModel,
    UserSignupResponse,
)
from .service import UserService
from src.db.main import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi.exceptions import HTTPException
from src.error import UserAlreadyExists
from fastapi.responses import JSONResponse, Response
from .dependencies import RefreshTokenBearer, AccessTokenBearer
from datetime import datetime
from src.error import (
    InvalidToken,
    RefreshTokenRequired,
    AccessTokenRequired,
    UserNotFound,
)
from src.db.redis import add_jti_to_blocklist
from .utils import (
    create_access_token,
    create_url_safe_token,
    decode_url_safe_token,
    generate_password_hash,
)
from src.celery_tasks import send_email
from src.mail import send_email_async
from src.config import Config

auth_router = APIRouter()
user_service = UserService()


@auth_router.post("/login")
async def login_user(
    login_data: UserLoginModel,
    session: AsyncSession = Depends(get_session),
):
    response = await user_service.login_users(
        login_data=login_data,
        session=session,
    )

    return response


@auth_router.post("/signup", response_model=UserSignupResponse)
async def create_user_account(
    user_data: UserCreateModel,
    session: AsyncSession = Depends(get_session),
):
    result = await user_service.create_user_account(
        user_data=user_data,
        session=session,
    )
    return result

@auth_router.get("/refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]

    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(user_data=token_details["user"])

        return JSONResponse(content={"access_token": new_access_token})
    
    raise InvalidToken()

@auth_router.get('/logout')
async def revoke_token(token_details:dict=Depends(AccessTokenBearer())):
    jti = token_details['jti']

    await add_jti_to_blocklist(jti)

    return JSONResponse(
        content={
            "message":"Logged Out Successfully"
        },
        status_code=status.HTTP_200_OK
    )

@auth_router.get("/verify/{token}")
async def verify_user_account(token: str,session:AsyncSession=Depends(get_session)):

    token_data = decode_url_safe_token(token)
    if not token_data:
        raise InvalidToken()
    user_email = token_data.get("email")

    if user_email:
        user = await user_service.get_user_by_email(user_email,session)

        if not user:
            raise UserNotFound()
        await user_service.update_user(user,{"is_verified":True},session)

        return JSONResponse(
            content={"message":"Account verified successfully"},
            status_code=status.HTTP_200_OK
        )


@auth_router.post("/password-reset-request")
async def password_Reset_request(
    email_data: PasswordResetRequestModel,
    background_tasks: BackgroundTasks,
):
    email = email_data.email

    token = create_url_safe_token({"email": email})

    domain = Config.DOMAIN.rstrip("/")
    if not domain.startswith("http://") and not domain.startswith("https://"):
        domain = f"https://{domain}"

    link = f"{domain}/auth/password-reset-confirm/{token}"

    html = f"""
    <h1>Reset Your Password</h1>
    <p>Please click this <a href="{link}">link</a> to Reset Your Password</p>"""
    subject = "Reset Your Password"

    background_tasks.add_task(send_email_async, [email], subject, html)

    return JSONResponse(
        content={
            "message": "Please check your email for instructions to reset your password",
        },
        status_code=status.HTTP_200_OK,
    )

@auth_router.post("/password-reset-confirm/{token}")
async def reset_account_password(
    token: str,
    passwords: PasswordResetConfirmModel,
    session: AsyncSession = Depends(get_session),
):
    new_password = passwords.new_password
    confirm_password = passwords.confirm_new_password
    if new_password != confirm_password:
        raise HTTPException(
            detail="Passwords do not match",status_code=status.HTTP_400_BAD_REQUEST
        )
    token_data = decode_url_safe_token(token)

    user_email = token_data.get("email")
    if user_email:
        user = await user_service.get_user_by_email(user_email,session)

        if not user:
            raise UserNotFound()
        
        passwd_hash = generate_password_hash(new_password)
        await user_service.update_user(user,{"password_hash":passwd_hash},session)

        return JSONResponse(
            content={"message": "Password reset Successfully"},
            status_code=status.HTTP_200_OK,
        )
    
    return JSONResponse(
        content={"message":"Error occured during password reset."},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
@auth_router.post('/send_mail')
async def send_mail(emails:EmailModel):
    emails = emails.addresses

    html = "<h1>Welcome to the app</h1>"
    subject = "Welcome to our app"

    send_email.delay(emails,subject,html)

    return {"message":"Email sent successfully"}