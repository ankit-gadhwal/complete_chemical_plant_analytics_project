from typing import Any,Callable
from fastapi import Request,status
from fastapi.responses import JSONResponse
from fastapi import FastAPI

class ChemicalEquipmentException(Exception):
    """
    Base class for all Chemical Equipment Analytics exception.
    """
    def __init__(self, detail: str | None = None):
        self.detail = detail
        super().__init__(detail)

class DatasetNotFound(ChemicalEquipmentException):
    """Dataset not found."""

class NoDatasetAvailable(ChemicalEquipmentException):
    """No  datasets available."""

class DatasetUploadFailed(ChemicalEquipmentException):
    """Dataset upload failed."""

class EquipmentNotFound(ChemicalEquipmentException):
    """Equipment not found"""

class NoEquipmentAvailable(ChemicalEquipmentException):
    """No equipment available"""

class NoEquipmentForDataset(ChemicalEquipmentException):
    """No equipment available for this dataset."""

class NoFileSelected(ChemicalEquipmentException):
    """No file selected."""

class InvalidFileExtension(ChemicalEquipmentException):
    """Uploaded file extension is invalid."""

class InvalidContentType(ChemicalEquipmentException):
    """Uploaded content type is invalid."""

class FileTooLarge(ChemicalEquipmentException):
    """Uploaded file exceeds maximum allowed size."""

class CSVReadError(ChemicalEquipmentException):
    """Unable to read CSV file."""

class MissingCSVColumns(ChemicalEquipmentException):
    """Required CSV columns are missing."""

    def __init__(self, missing_columns: list[str]):
        self.missing_columns = missing_columns

class InvalidQuestion(ChemicalEquipmentException):
    """User question is empty or invalid"""

class SQLGenerationFailed(ChemicalEquipmentException):
    """LLM failed to generate SQL."""

class InvalidSQLGenerated(ChemicalEquipmentException):
    """Generate SQL failed validation."""

class SQLExecutionFailed(ChemicalEquipmentException):
    """Failed to execute generated SQL."""

class AIResponseGenerationFailed(ChemicalEquipmentException):
    """LLM failed to generate final response."""

class AIServiceUnavailable(ChemicalEquipmentException):
    """LLM service unavailable"""

class UserAlreadyExists(ChemicalEquipmentException):
    """User has provided an email for a user who exists during sign up."""
    pass
class InvalidToken(ChemicalEquipmentException):
    """User has provided an invalid or expired token"""
    pass

class RevokedToken(ChemicalEquipmentException):
    """User has provided a token that has been revoked"""
    pass

class AccessTokenRequired(ChemicalEquipmentException):
    """User has provided a refresh token when an access token is needed"""
    pass

class RefreshTokenRequired(ChemicalEquipmentException):
    """User has provided an access token when a refresh token is needed"""
    pass

class InvalidCredentials(ChemicalEquipmentException):
    """User has provided wrong email or password during log in."""
    pass

class AuthenticationFailed(ChemicalEquipmentException):
    """Authentication failed."""
    pass


class UserInactive(ChemicalEquipmentException):
    """User account is inactive."""
    pass


class UserNotVerified(ChemicalEquipmentException):
    """User account is not verified."""
    pass


class PermissionDenied(ChemicalEquipmentException):
    """User does not have permission to perform this action."""
    pass

class DuplicateDatasetException(ChemicalEquipmentException):
    def __init__(self, filename: str):
        self.filename = filename
        self.detail = (
            f"Dataset '{filename}' already exists. "
            "Please delete the existing dataset before uploading it again.")
class AuthorizationError(ChemicalEquipmentException):
    """You are not authorized to perform this operaion"""    

class ChatSessionNotFound(ChemicalEquipmentException):
    """Chat ssesion is not exist, create new one"""

class UserNotFound(ChemicalEquipmentException):
    """User Not found"""
    pass

def create_exception_handler(status_code: int,initial_detail: Any,)->Callable[[Request,Exception],JSONResponse]:
    async def exception_handler(request: Request,exec:ChemicalEquipmentException):
        return JSONResponse(
            status_code=status_code,
            content={
                "success":False,
                "detail": exec.detail or initial_detail,
            },
        )
    return exception_handler

async def missing_csv_columns_handler(
    request: Request,
    exc: MissingCSVColumns,
):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "detail": {
                "message": "Missing required CSV columns.",
                "missing_columns": exc.missing_columns,
            },
        },
    )

def register_error_handlers(app: FastAPI):
    app.add_exception_handler(NoFileSelected,
                              create_exception_handler(
                                  status.HTTP_400_BAD_REQUEST,"Only CSV files are allowed."))
    
    app.add_exception_handler(DuplicateDatasetException,
        create_exception_handler(
            status.HTTP_409_CONFLICT,
            "You have already uploaded this file. Please delete the existing dataset before uploading it again."))
    
    app.add_exception_handler(
    InvalidFileExtension,
    create_exception_handler(
        status.HTTP_400_BAD_REQUEST,
        "Only CSV files are allowed.",),)
    app.add_exception_handler(InvalidContentType,
                              create_exception_handler(
                                  status.HTTP_400_BAD_REQUEST,
                                  "Unsupported content type."
                              ))
    app.add_exception_handler(FileTooLarge,create_exception_handler(
                       status.HTTP_413_CONTENT_TOO_LARGE,
                       "File size exceeds 5 MB.",),)

    app.add_exception_handler(
        CSVReadError,
        create_exception_handler(
            status.HTTP_400_BAD_REQUEST,
            "Unable to read CSV file.",
         ),)

    app.add_exception_handler(
        MissingCSVColumns,missing_csv_columns_handler)

    app.add_exception_handler(DatasetNotFound,
                              create_exception_handler(
            status.HTTP_404_NOT_FOUND,
            "Dataset not found.",))
    
    app.add_exception_handler(
    NoDatasetAvailable,
    create_exception_handler(
        status.HTTP_404_NOT_FOUND,
        "No dataset available.",
    ),)

    app.add_exception_handler(
        EquipmentNotFound,
        create_exception_handler(
            status.HTTP_404_NOT_FOUND,
            "Equipment not found.",
        ),)

    app.add_exception_handler(
        NoEquipmentAvailable,
        create_exception_handler(
            status.HTTP_404_NOT_FOUND,
            "No equipment available.",
        ),)

    app.add_exception_handler(
        NoEquipmentForDataset,
        create_exception_handler(
            status.HTTP_404_NOT_FOUND,
            "No equipment available for this dataset.",))
    
    app.add_exception_handler(
    InvalidQuestion,
    create_exception_handler(
        status.HTTP_400_BAD_REQUEST,
        "Question cannot be empty."))

    app.add_exception_handler(
    SQLGenerationFailed,
    create_exception_handler(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Failed to generate SQL query."))

    app.add_exception_handler(
    InvalidSQLGenerated,
    create_exception_handler(
        status.HTTP_400_BAD_REQUEST,
        "Generated SQL is invalid.",
    ))

    app.add_exception_handler(
    SQLExecutionFailed,
    create_exception_handler(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Failed to execute SQL query.",
    ))

    app.add_exception_handler(
    AIResponseGenerationFailed,
    create_exception_handler(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Failed to generate AI response.",
    ))

    app.add_exception_handler(
    AIServiceUnavailable,
    create_exception_handler(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "AI service is currently unavailable.",
    ))

    app.add_exception_handler(
        UserAlreadyExists,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message": "User with email already exists",
                "error_code":"user_exists"
            }
        )
    )

    app.add_exception_handler(
        InvalidCredentials,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "message": "Invalid Email Or Password",
                "error_code": "invalid_email_or_password",
            },
        ),
    )
    app.add_exception_handler(
        InvalidToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message": "Token is invalid Or expired",
                "resolution": "Please get new token",
                "error_code": "invalid_token",
            },
        ),
    )
    app.add_exception_handler(
        RevokedToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message": "Token is invalid or has been revoked",
                "resolution": "Please get new token",
                "error_code": "token_revoked",
            },
        ),
    )
    app.add_exception_handler(
        AccessTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message": "Please provide a valid access token",
                "resolution": "Please get an access token",
                "error_code": "access_token_required",
            },
        ),
    )
    app.add_exception_handler(
        RefreshTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "message": "Please provide a valid refresh token",
                "resolution": "Please get an refresh token",
                "error_code": "refresh_token_required",
            },
        ),
    )
    app.add_exception_handler(
        AuthenticationFailed,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "message": "Authentication failed",
                "error_code": "authentication_failed",
            },
        ),
    )
    app.add_exception_handler(
        UserInactive,
        create_exception_handler(
            status.HTTP_403_FORBIDDEN,
            {
                "message": "Your account has been deactivated.",
                "error_code": "user_inactive",
            }
        )
    )
    app.add_exception_handler(
        UserNotVerified,
        create_exception_handler(
            status.HTTP_403_FORBIDDEN,
            {
                "message": "please verify your email address before continuing.",
                "error_code": "user_not_verified"
            }
        )
    )
    app.add_exception_handler(
    PermissionDenied,
    create_exception_handler(
        status.HTTP_403_FORBIDDEN,
        {
            "message": "You do not have permission to perform this action.",
            "error_code": "permission_denied",
        }
        ))

    app.add_exception_handler(
    AuthorizationError,
    create_exception_handler(
        status.HTTP_403_FORBIDDEN,
        {
            "message": "You do not have permission to perform this action.",
            "error_code": "UnAuthorized",
        }
        ))

    app.add_exception_handler(
        ChatSessionNotFound,
        create_exception_handler(
        status.HTTP_404_NOT_FOUND,
        {
            "message": "Chat session not found.",
            "error_code": "ChatSessionNotFound",
        },
    )
    )
    app.add_exception_handler(UserNotFound,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "message": "User not found",
                "error_code": "user_not_found",
            },
        ),)    