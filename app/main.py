from fastapi import FastAPI, Request, Depends, HTTPException, Form, status, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import random
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from app.database import get_db, engine
from app.models import Base, User, UserSession
from app.recommender import recommender
from app.auth import get_password_hash, verify_password, generate_session_token, get_session_expiry, \
    validate_password_strength

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Создаем директории если их нет
os.makedirs("app/templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("data", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await recommender.load_books_data()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Book4U - Система рекомендаций книг",
    description="Персонализированная система рекомендаций книг Book4U",
    version="1.0.0",
    lifespan=lifespan
)

# Настройка шаблонов
templates = Jinja2Templates(directory="app/templates")

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получение текущего пользователя из сессии"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None

    # Ищем активную сессию
    session = db.query(UserSession).filter(
        UserSession.session_token == session_token,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()

    if not session:
        return None

    # Получаем пользователя
    user = db.query(User).filter(User.id == session.user_id).first()
    return user


async def require_auth(request: Request, db: Session = Depends(get_db), user_id: int = None):
    """Проверка авторизации пользователя"""
    current_user = get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    if user_id and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    return current_user


async def get_user_books_data(user):
    """Получение данных о книгах пользователя"""
    books_data = await recommender.load_books_data()
    all_books = books_data['initial_books'] + books_data['all_books']

    user_books = []
    if user.selected_books:
        for book in all_books:
            if book['id'] in user.selected_books:
                user_books.append(book)

    return user_books, all_books


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    # Проверяем, есть ли активная сессия
    current_user = get_current_user(request, db)

    if current_user:
        # Если пользователь авторизован, показываем главную с книгами
        user_books, all_books = await get_user_books_data(current_user)

        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "user": current_user,
                "selected_books": user_books,
                "all_books": all_books
            }
        )
    else:
        # Если не авторизован, показываем страницу регистрации
        return templates.TemplateResponse("register.html", {"request": request})


@app.post("/update-books/{user_id}")
async def update_books(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    form_data = await request.form()
    selected_books = form_data.getlist("selected_books")

    # Преобразуем в int
    selected_books = [int(book_id) for book_id in selected_books] if selected_books else []

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Пользователь не найден"}
        )

    try:
        # Обновляем выбранные книги
        user.selected_books = selected_books

        # Если есть выбранные книги, устанавливаем флаг
        if selected_books:
            user.initial_books_selected = True
            # Переобучаем модель
            preferences = recommender.train_model(selected_books)
            user.preferences = preferences
        else:
            user.initial_books_selected = False
            user.preferences = None

        db.commit()

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Книги обновлены"}
        )

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка при обновлении: {str(e)}"}
        )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    # Ищем пользователя по email
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        # Возвращаем страницу входа с сообщением об ошибке
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Неверный email или пароль",
                "email": email  # Сохраняем введенный email для удобства
            }
        )

    # Создаем новую сессию
    session_token = generate_session_token()
    expires_at = get_session_expiry()

    session = UserSession(
        user_id=user.id,
        session_token=session_token,
        expires_at=expires_at
    )

    db.add(session)
    db.commit()

    # Перенаправление в зависимости от состояния пользователя
    if user.initial_books_selected:
        redirect_url = f"/profile/{user.id}"
    else:
        redirect_url = f"/initial-books/{user.id}"

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True
    )
    return response


@app.post("/register")
async def register(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    # Проверка существующего пользователя
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        # Возвращаем страницу регистрации с ошибкой
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Пользователь с таким именем или email уже существует",
                "username": username,
                "email": email
            }
        )

    # Проверка сложности пароля
    is_valid, password_error = validate_password_strength(password)
    if not is_valid:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": password_error,
                "username": username,
                "email": email
            }
        )

    # Создание нового пользователя
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        initial_books_selected=False
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Создаем сессию для нового пользователя
    session_token = generate_session_token()
    expires_at = get_session_expiry()

    session = UserSession(
        user_id=user.id,
        session_token=session_token,
        expires_at=expires_at
    )

    db.add(session)
    db.commit()

    # Перенаправление на выбор начальных книг
    response = RedirectResponse(
        url=f"/initial-books/{user.id}",
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True
    )
    return response


@app.get("/initial-books/{user_id}", response_class=HTMLResponse)
async def initial_books(request: Request, user_id: int, db: Session = Depends(get_db)):
    current_user = await require_auth(request, db, user_id)

    books_data = await recommender.load_books_data()
    initial_books = books_data['initial_books']

    # Увеличиваем количество показываемых книг до 20
    selected_books = random.sample(initial_books, min(20, len(initial_books)))

    return templates.TemplateResponse(
        "initial_books.html",
        {
            "request": request,
            "user": current_user,
            "books": selected_books
        }
    )


@app.post("/submit-initial-books/{user_id}")
async def submit_initial_books(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    form_data = await request.form()
    selected_books = form_data.getlist("selected_books")

    if not selected_books:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну книгу")

    # Преобразуем в int
    selected_books = [int(book_id) for book_id in selected_books]

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        # Обучение модели на выбранных книгах
        preferences = recommender.train_model(selected_books)

        # Обновление пользователя
        user.preferences = preferences
        user.selected_books = selected_books
        user.initial_books_selected = True

        db.commit()

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка при обучении модели: {str(e)}")

    # Перенаправление на страницу рекомендаций
    return RedirectResponse(
        url=f"/recommendations/{user_id}",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/recommendations/{user_id}", response_class=HTMLResponse)
async def get_recommendations(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    if not current_user.initial_books_selected:
        raise HTTPException(status_code=400, detail="Сначала выберите начальные книги")

    # Получение рекомендаций
    recommendations = recommender.get_recommendations(num_recommendations=30)

    return templates.TemplateResponse(
        "recommendations.html",
        {
            "request": request,
            "user": current_user,
            "recommendations": recommendations
        }
    )


@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def user_profile(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    selected_books_info, _ = await get_user_books_data(current_user)

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": current_user,
            "selected_books": selected_books_info
        }
    )


@app.post("/remove-book/{user_id}")
async def remove_book(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    form_data = await request.form()
    book_id_to_remove = form_data.get("book_id")

    if not book_id_to_remove:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Не указана книга для удаления"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Пользователь не найден"}
        )

    if not user.selected_books:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Нет выбранных книг"}
        )

    # Преобразуем book_id в int
    try:
        book_id_to_remove = int(book_id_to_remove)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Неверный формат ID книги"}
        )

    # Удаляем книгу из списка выбранных
    if book_id_to_remove in user.selected_books:
        user.selected_books.remove(book_id_to_remove)

        # Если книг не осталось, сбрасываем флаг
        if not user.selected_books:
            user.initial_books_selected = False
            user.preferences = None

        db.commit()

        # Переобучаем модель, если есть оставшиеся книги
        if user.selected_books:
            try:
                preferences = recommender.train_model(user.selected_books)
                user.preferences = preferences
                db.commit()
            except Exception as e:
                print(f"DEBUG: Model retraining failed: {e}")

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Книга удалена"}
        )
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Книга не найдена в выбранных"}
        )


@app.post("/clear-all-books/{user_id}")
async def clear_all_books(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    current_user = await require_auth(request, db, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Пользователь не найден"}
        )

    # Очищаем все выбранные книги
    user.selected_books = []
    user.initial_books_selected = False
    user.preferences = None

    db.commit()

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "Все книги удалены"}
    )


@app.post("/logout")
async def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    # Удаляем сессию из базы данных
    session_token = request.cookies.get("session_token")
    if session_token:
        session = db.query(UserSession).filter(UserSession.session_token == session_token).first()
        if session:
            db.delete(session)
            db.commit()

    # Удаляем cookie
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="session_token")
    return response


# Главная страница с проверкой авторизации
@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return RedirectResponse(url=f"/profile/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)


# API endpoint для получения рекомендаций в JSON формате
@app.get("/api/recommendations/{user_id}")
async def api_recommendations(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.initial_books_selected:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    recommendations = recommender.get_recommendations(num_recommendations=30)
    return {"user_id": user_id, "recommendations": recommendations}


# Добавим favicon, чтобы убрать 404 ошибку
@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")