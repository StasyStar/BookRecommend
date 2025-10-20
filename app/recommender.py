import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict
import json
import aiofiles
import os
import random


class BookRecommender:
    def __init__(self):
        self.model = LogisticRegression(random_state=42, max_iter=1000)
        self.scaler = StandardScaler()
        self.knn = NearestNeighbors(n_neighbors=30, metric='cosine')
        self.books_data = None
        self.is_fitted = False

    async def load_books_data(self):
        """Загрузка данных о книгах"""
        if self.books_data is None:
            file_path = os.path.join("data", "books.json")
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    self.books_data = json.loads(content)
            except FileNotFoundError:
                # Создаем демо данные если файл не найден
                self.books_data = await self.create_demo_data()
                # Сохраняем демо данные
                os.makedirs("data", exist_ok=True)
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(self.books_data, ensure_ascii=False, indent=2))
        return self.books_data

    async def create_demo_data(self):
        """Создание демо данных о книгах"""
        books_data = {
            "initial_books": [],
            "all_books": []
        }

        # Список популярных книг
        popular_books = [
            {"title": "Мастер и Маргарита", "author": "Михаил Булгаков", "genre": "классика"},
            {"title": "Преступление и наказание", "author": "Федор Достоевский", "genre": "классика"},
            {"title": "Война и мир", "author": "Лев Толстой", "genre": "классика"},
            {"title": "1984", "author": "Джордж Оруэлл", "genre": "антиутопия"},
            {"title": "451° по Фаренгейту", "author": "Рэй Брэдбери", "genre": "антиутопия"},
            {"title": "Гарри Поттер и философский камень", "author": "Джоан Роулинг", "genre": "фэнтези"},
            {"title": "Властелин колец", "author": "Дж. Р. Р. Толкин", "genre": "фэнтези"},
            {"title": "Убить пересмешника", "author": "Харпер Ли", "genre": "драма"},
            {"title": "Три товарища", "author": "Эрих Мария Ремарк", "genre": "драма"},
            {"title": "Маленький принц", "author": "Антуан де Сент-Экзюпери", "genre": "философия"},
            {"title": "Анна Каренина", "author": "Лев Толстой", "genre": "классика"},
            {"title": "Братья Карамазовы", "author": "Федор Достоевский", "genre": "классика"},
            {"title": "О дивный новый мир", "author": "Олдос Хаксли", "genre": "антиутопия"},
            {"title": "Скотный двор", "author": "Джордж Оруэлл", "genre": "сатира"},
            {"title": "Шерлок Холмс", "author": "Артур Конан Дойл", "genre": "детектив"}
        ]

        # Дополнительные книги для рекомендаций
        additional_books = [
            {"title": "Идиот", "author": "Федор Достоевский", "genre": "классика"},
            {"title": "Отцы и дети", "author": "Иван Тургенев", "genre": "классика"},
            {"title": "Обломов", "author": "Иван Гончаров", "genre": "классика"},
            {"title": "Доктор Живаго", "author": "Борис Пастернак", "genre": "классика"},
            {"title": "Тихий Дон", "author": "Михаил Шолохов", "genre": "классика"},
            {"title": "Мы", "author": "Евгений Замятин", "genre": "антиутопия"},
            {"title": "Колыбель для кошки", "author": "Курт Воннегут", "genre": "сатира"},
            {"title": "Над пропастью во ржи", "author": "Джером Сэлинджер", "genre": "драма"},
            {"title": "Портрет Дориана Грея", "author": "Оскар Уайльд", "genre": "классика"},
            {"title": "Грозовой перевал", "author": "Эмили Бронте", "genre": "драма"},
            {"title": "Гордость и предубеждение", "author": "Джейн Остин", "genre": "роман"},
            {"title": "Великий Гэтсби", "author": "Фрэнсис Скотт Фицджеральд", "genre": "драма"},
            {"title": "Старик и море", "author": "Эрнест Хемингуэй", "genre": "драма"},
            {"title": "Лолита", "author": "Владимир Набоков", "genre": "классика"},
            {"title": "Атлант расправил плечи", "author": "Айн Рэнд", "genre": "философия"},
            {"title": "Сто лет одиночества", "author": "Габриэль Гарсиа Маркес", "genre": "магический реализм"},
            {"title": "Повесть о двух городах", "author": "Чарльз Диккенс", "genre": "классика"},
            {"title": "Дюна", "author": "Фрэнк Герберт", "genre": "фантастика"},
            {"title": "Фонд", "author": "Айзек Азимов", "genre": "фантастика"},
            {"title": "Норвежский лес", "author": "Харуки Мураками", "genre": "роман"},
            {"title": "Код да Винчи", "author": "Дэн Браун", "genre": "детектив"},
            {"title": "Алиса в Стране чудес", "author": "Льюис Кэрролл", "genre": "фэнтези"},
            {"title": "Хоббит", "author": "Дж. Р. Р. Толкин", "genre": "фэнтези"},
            {"title": "Унесенные ветром", "author": "Маргарет Митчелл", "genre": "роман"}
        ]

        # Создаем эмбеддинги на основе жанров
        genre_vectors = {
            "классика": [0.9, 0.1, 0.1],
            "антиутопия": [0.1, 0.9, 0.1],
            "фэнтези": [0.1, 0.1, 0.9],
            "драма": [0.7, 0.5, 0.3],
            "философия": [0.8, 0.2, 0.4],
            "сатира": [0.3, 0.7, 0.2],
            "детектив": [0.2, 0.8, 0.4],
            "роман": [0.6, 0.4, 0.6],
            "магический реализм": [0.4, 0.3, 0.8],
            "фантастика": [0.2, 0.2, 0.95]
        }

        # Заполняем initial_books
        for i, book_info in enumerate(popular_books, 1):
            genre = book_info["genre"]
            embedding = genre_vectors.get(genre, [0.5, 0.5, 0.5])
            # Добавляем немного случайности к эмбеддингам
            embedding = [x + random.uniform(-0.1, 0.1) for x in embedding]
            books_data["initial_books"].append({
                "id": i,
                **book_info,
                "embedding": embedding
            })

        # Заполняем all_books
        for i, book_info in enumerate(additional_books, len(popular_books) + 1):
            genre = book_info["genre"]
            embedding = genre_vectors.get(genre, [0.5, 0.5, 0.5])
            # Добавляем немного случайности к эмбеддингам
            embedding = [x + random.uniform(-0.1, 0.1) for x in embedding]
            books_data["all_books"].append({
                "id": i,
                **book_info,
                "embedding": embedding
            })

        return books_data

    def prepare_training_data(self, selected_book_ids: List[int]):
        """Подготовка данных для обучения модели"""
        all_books = self.books_data['initial_books'] + self.books_data['all_books']

        X = []
        y = []

        for book in all_books:
            embedding = book['embedding']
            X.append(embedding)
            # Помечаем выбранные книги как 1, остальные как 0
            y.append(1 if book['id'] in selected_book_ids else 0)

        return np.array(X), np.array(y)

    def train_model(self, selected_book_ids: List[int]):
        """Обучение модели на выбранных книгах"""
        X, y = self.prepare_training_data(selected_book_ids)

        # Проверяем, что есть как положительные, так и отрицательные примеры
        if sum(y) == 0:
            raise ValueError("Не выбрано ни одной книги")
        if sum(y) == len(y):
            raise ValueError("Выбраны все книги")

        # Увеличиваем max_iter для лучшей сходимости при большом количестве данных
        self.model = LogisticRegression(random_state=42, max_iter=1000)

        # Масштабирование признаков
        X_scaled = self.scaler.fit_transform(X)

        # Обучение логистической регрессии
        self.model.fit(X_scaled, y)
        self.is_fitted = True

        # Вычисление предпочтений пользователя
        preferences = self.model.coef_[0]
        return preferences.tolist()

    def get_recommendations(self, num_recommendations: int = 30) -> List[Dict]:
        """Получение рекомендаций на основе обученной модели"""
        if not self.is_fitted:
            # Если модель не обучена, возвращаем случайные книги
            return random.sample(self.books_data['all_books'],
                                 min(num_recommendations, len(self.books_data['all_books'])))

        all_books = self.books_data['all_books']
        book_ids = [book['id'] for book in all_books]
        embeddings = np.array([book['embedding'] for book in all_books])

        # Масштабирование и предсказание вероятностей
        embeddings_scaled = self.scaler.transform(embeddings)
        probabilities = self.model.predict_proba(embeddings_scaled)[:, 1]

        # Сортировка книг по вероятности выбора
        book_probs = list(zip(book_ids, probabilities, all_books))
        book_probs.sort(key=lambda x: x[1], reverse=True)

        # Выбор топ-N рекомендаций
        recommendations = [book for _, _, book in book_probs[:num_recommendations]]

        return recommendations


# Глобальный экземпляр рекомендательной системы
recommender = BookRecommender()
