let selectedBooks = new Set();

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем selectedBooks из данных шаблона
    if (window.userData && window.userData.selectedBooks) {
        selectedBooks = new Set(window.userData.selectedBooks);
    }
    updateSelectionCount();
    initializeEventListeners();
});

function initializeEventListeners() {
    // Поиск книг
    document.getElementById('book-search').addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const bookCards = document.querySelectorAll('.book-card');

        bookCards.forEach(card => {
            const title = card.getAttribute('data-title');
            const author = card.getAttribute('data-author');

            if (title.includes(searchTerm) || author.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    });

    // Фильтр по жанрам
    document.getElementById('genre-filter').addEventListener('change', function(e) {
        const selectedGenre = e.target.value;
        const bookCards = document.querySelectorAll('.book-card');

        bookCards.forEach(card => {
            const genre = card.getAttribute('data-genre');

            if (selectedGenre === 'all' || genre === selectedGenre) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    });

    // Снять все с видимых книг
    document.getElementById('deselect-all').addEventListener('click', function() {
        const visibleBooks = document.querySelectorAll('.book-card[style*="display: block"], .book-card:not([style*="display: none"])');

        visibleBooks.forEach(card => {
            const bookId = card.getAttribute('data-book-id');
            if (selectedBooks.has(parseInt(bookId))) {
                toggleBookSelection(parseInt(bookId));
            }
        });
    });
}

function toggleBookSelection(bookId) {
    const bookCard = document.querySelector(`[data-book-id="${bookId}"]`);

    if (selectedBooks.has(bookId)) {
        // Убираем выбор
        selectedBooks.delete(bookId);
        bookCard.classList.remove('selected');

        // Убираем индикатор
        const indicator = bookCard.querySelector('.selected-indicator');
        if (indicator) {
            indicator.remove();
        }
    } else {
        // Добавляем выбор
        selectedBooks.add(bookId);
        bookCard.classList.add('selected');

        // Добавляем индикатор
        if (!bookCard.querySelector('.selected-indicator')) {
            const indicator = document.createElement('div');
            indicator.className = 'selected-indicator';
            indicator.textContent = '✓ Выбрано';
            bookCard.querySelector('.book-info').appendChild(indicator);
        }
    }

    updateSelectionCount();
}

function updateSelectionCount() {
    const countElement = document.getElementById('selected-count');
    if (countElement) {
        countElement.innerHTML = `Сейчас выбрано: <strong>${selectedBooks.size}</strong> книг`;

        if (selectedBooks.size >= 10) {
            countElement.style.color = '#27ae60';
        } else if (selectedBooks.size >= 5) {
            countElement.style.color = '#3498db';
        } else {
            countElement.style.color = '#e74c3c';
        }
    }
}

function saveBookSelection() {
    const saveBtn = document.getElementById('save-btn');
    const statusElement = document.getElementById('save-status');

    if (selectedBooks.size < 3) {
        showCustomConfirm(
            'Для получения рекомендаций нужно выбрать хотя бы <strong>3 книги</strong>.<br><br>Рекомендуем выбрать 5-10 книг для лучших результатов!',
            function() {
                document.getElementById('book-search').focus();
            }
        );
        return;
    }

    saveBtn.disabled = true;
    saveBtn.innerHTML = '⏳ Сохранение...';
    statusElement.innerHTML = '<div style="color: #3498db;">⏳ Сохранение изменений...</div>';

    const formData = new FormData();
    selectedBooks.forEach(bookId => {
        formData.append('selected_books', bookId.toString());
    });

    // Используем userId из глобальных данных
    const userId = window.userData ? window.userData.userId : null;

    if (!userId) {
        statusElement.innerHTML = '<div style="color: #e74c3c;">❌ Ошибка: ID пользователя не найден</div>';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '📚 Перейти к рекомендациям';
        return;
    }

    fetch('/update-books/' + userId, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            statusElement.innerHTML = '<div style="color: #27ae60;">✅ Изменения сохранены успешно!</div>';
            saveBtn.innerHTML = '📚 Переход к рекомендациям...';

            setTimeout(() => {
                window.location.href = '/recommendations/' + userId;
            }, 1000);
        } else {
            statusElement.innerHTML = `<div style="color: #e74c3c;">❌ Ошибка: ${data.error}</div>`;
            saveBtn.disabled = false;
            saveBtn.innerHTML = '📚 Перейти к рекомендациям';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        statusElement.innerHTML = '<div style="color: #e74c3c;">❌ Ошибка при сохранении</div>';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '📚 Перейти к рекомендациям';
    });
}