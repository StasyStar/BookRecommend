from fastapi import FastAPI, Request, Depends, HTTPException, Form, status, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List
import random
import os
from datetime import datetime, timezone
import json

from app.database import get_db, engine
from app.models import Base, User, UserSession
from app.recommender import recommender
from app.auth import get_password_hash, verify_password, generate_session_token, get_session_expiry

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Book Recommendation System")

# Создаем директории если их нет
os.makedirs("app/templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Настройка шаблонов
templates = Jinja2Templates(directory="app/templates")

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")


# Загрузка данных о книгах при запуске
@app.on_event("startup")
async def startup_event():
    await recommender.load_books_data()


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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    # Проверяем, есть ли активная сессия
    current_user = get_current_user(request, db)
    if current_user:
        if current_user.initial_books_selected:
            return RedirectResponse(url=f"/profile/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)
        else:
            return RedirectResponse(url=f"/initial-books/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("register.html", {"request": request})


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
        raise HTTPException(
            status_code=400,
            detail="Неверный email или пароль"
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
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким именем или email уже существует"
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
    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    books_data = await recommender.load_books_data()
    initial_books = books_data['initial_books']

    # Выбираем случайные 10 книг из начального набора
    selected_books = random.sample(initial_books, min(10, len(initial_books)))

    return templates.TemplateResponse(
        "initial_books.html",
        {
            "request": request,
            "user": user,
            "books": selected_books
        }
    )


@app.post("/submit-initial-books/{user_id}")
async def submit_initial_books(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

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
    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not user.initial_books_selected:
        raise HTTPException(status_code=400, detail="Сначала выберите начальные книги")

    # Получение рекомендаций
    recommendations = recommender.get_recommendations(num_recommendations=30)

    return templates.TemplateResponse(
        "recommendations.html",
        {
            "request": request,
            "user": user,
            "recommendations": recommendations
        }
    )


@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def user_profile(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    books_data = await recommender.load_books_data()
    all_books = books_data['initial_books'] + books_data['all_books']

    selected_books_info = []
    if user.selected_books:
        for book in all_books:
            if book['id'] in user.selected_books:
                selected_books_info.append(book)

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "selected_books": selected_books_info
        }
    )


@app.post("/remove-book/{user_id}")
async def remove_book(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    print(f"=== DEBUG: remove-book called for user {user_id} ===")

    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        print("DEBUG: User not authorized")
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    form_data = await request.form()
    book_id_to_remove = form_data.get("book_id")

    print(f"DEBUG: Form data: {dict(form_data)}")
    print(f"DEBUG: Book ID to remove: {book_id_to_remove}")

    if not book_id_to_remove:
        print("DEBUG: No book_id provided")
        raise HTTPException(status_code=400, detail="Не указана книга для удаления")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print("DEBUG: User not found")
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    print(f"DEBUG: User selected_books before: {user.selected_books}")
    print(f"DEBUG: User ID: {user.id}")

    if not user.selected_books:
        print("DEBUG: No selected books")
        raise HTTPException(status_code=400, detail="Нет выбранных книг")

    # Преобразуем book_id в int
    try:
        book_id_to_remove = int(book_id_to_remove)
    except ValueError:
        print("DEBUG: Invalid book_id format")
        raise HTTPException(status_code=400, detail="Неверный формат ID книги")

    # Удаляем книгу из списка выбранных
    if book_id_to_remove in user.selected_books:
        # Создаем новый список без удаляемой книги
        new_selected_books = [book_id for book_id in user.selected_books if book_id != book_id_to_remove]
        user.selected_books = new_selected_books

        print(f"DEBUG: Book {book_id_to_remove} removed")
        print(f"DEBUG: User selected_books after: {user.selected_books}")

        # Если книг не осталось, сбрасываем флаг
        if not user.selected_books:
            user.initial_books_selected = False
            user.preferences = None
            print("DEBUG: All books removed, resetting flags")

        try:
            db.commit()
            print("DEBUG: Database committed successfully")

            # Проверяем, что изменения сохранились
            db.refresh(user)
            print(f"DEBUG: User selected_books after refresh: {user.selected_books}")

        except Exception as e:
            print(f"DEBUG: Database commit failed: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Ошибка при сохранении изменений")

        # Переобучаем модель, если есть оставшиеся книги
        if user.selected_books:
            try:
                preferences = recommender.train_model(user.selected_books)
                user.preferences = preferences
                db.commit()
                print("DEBUG: Model retrained and committed")
            except Exception as e:
                print(f"DEBUG: Model retraining failed: {e}")
                # Не прерываем выполнение если переобучение не удалось
    else:
        print(f"DEBUG: Book {book_id_to_remove} not found in selected_books")

    return RedirectResponse(url=f"/profile/{user_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/clear-all-books/{user_id}")
async def clear_all_books(
        request: Request,
        user_id: int,
        db: Session = Depends(get_db)
):
    # Проверяем, что пользователь авторизован
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Очищаем все выбранные книги
    user.selected_books = []
    user.initial_books_selected = False
    user.preferences = None

    db.commit()

    return RedirectResponse(url=f"/profile/{user_id}", status_code=status.HTTP_303_SEE_OTHER)


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
