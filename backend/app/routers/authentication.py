from fastapi import HTTPException, Depends, APIRouter, status, Form, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm

from ..logger_manager import LoggerManager
from ..authentication.models import User, Token
from ..authentication.auth_methods \
import get_current_active_user, get_user, create_access_token, create_user, authenticate_user, delete_user_in_db
from ..database_manager import get_db
from pymongo.database import Database


router = APIRouter(
    tags=["user"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger_instance = LoggerManager()
logger = logger_instance.get_logger()

# Geschützter Endpunkt
@router.get("/user/all")
async def read_users_me(current_user: User = Depends(get_current_active_user), db: Database = Depends(get_db)):
    users = []

    async for user in db["users"].find():
        del user["_id"]
        del user["disabled"]
        del user["hashed_password"]
        users.append(user)

    return users

@router.get("/user/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# Neuen Nutzer anlegen
@router.post("/user/sign_up", response_model=Token)
async def sign_up_for_access_token(username: str = Form(...), fullname: str = Form(...), email: str = Form(...), password: str = Form(...), admin_key: str = Form(...)):
    user = await get_user(username)
    if user == None:
        user = await create_user(username, fullname, email, password, admin_key)
    else:
        logger.warning(f"username {username} already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )
    
    logger.info(f"user {username} created")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Nutzer entfernen
@router.post("/user/delete")
async def delete_user(background_tasks: BackgroundTasks, username: str = Form(...), password: str = Form(...)):
    user = await authenticate_user(username, password)
    if not user:
        logger.warning(f"user {username} could not be deleted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    background_tasks.add_task(delete_user_in_db, username)

    logger.info(f"user {username} deleted")
    return {"message": "user deleted"}

# Authentifizierung: Token-Endpunkt
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"wrong password for user {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}