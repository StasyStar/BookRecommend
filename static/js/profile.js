// Глобальная переменная для ID пользователя
let userId = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Получаем ID пользователя из глобальных данных
    if (window.userData && window.userData.userId) {
        userId = window.userData.userId;
    }

    console.log('Profile JS loaded, user ID:', userId);

    // Добавляем обработчик для кнопки "Удалить все книги"
    initializeClearAllButton();
});

function initializeClearAllButton() {
    const clearAllBtn = document.querySelector('.clear-all-btn');
    if (clearAllBtn) {
        // Убираем стандартное поведение формы и добавляем наш обработчик
        clearAllBtn.onclick = function(e) {
            e.preventDefault();
            showClearAllConfirm();
        };
    }
}

// Кастомный диалог подтверждения для удаления одной книги
function showCustomConfirm(message, onConfirm, onCancel) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    `;

    modal.innerHTML = `
        <div style="
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            max-width: 400px;
            text-align: center;
        ">
            <div style="font-size: 48px; margin-bottom: 15px;">📚</div>
            <h3 style="margin-bottom: 15px; color: #2c3e50;">Book4U</h3>
            <div style="margin-bottom: 25px; color: #555; line-height: 1.5;">${message}</div>
            <div>
                <button id="confirm-yes" style="
                    background: #27ae60;
                    color: white;
                    border: none;
                    padding: 12px 25px;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-right: 10px;
                    font-size: 16px;
                ">Да, удалить</button>
                <button id="confirm-no" style="
                    background: #e74c3c;
                    color: white;
                    border: none;
                    padding: 12px 25px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 16px;
                ">Отмена</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Обработчики для кнопок
    document.getElementById('confirm-yes').addEventListener('click', function() {
        document.body.removeChild(modal);
        if (onConfirm) onConfirm();
    });

    document.getElementById('confirm-no').addEventListener('click', function() {
        document.body.removeChild(modal);
        if (onCancel) onCancel();
    });
}

// Кастомный диалог для удаления всех книг
function showClearAllConfirm() {
    showCustomConfirm(
        'Вы уверены, что хотите удалить <strong>все выбранные книги</strong> из Book4U?<br><br>Это действие нельзя отменить!',
        function() {
            // Показываем индикатор загрузки
            const clearAllBtn = document.querySelector('.clear-all-btn');
            if (clearAllBtn) {
                clearAllBtn.disabled = true;
                clearAllBtn.innerHTML = '⏳ Удаление...';
            }

            // Отправляем AJAX запрос для удаления всех книг
            fetch('/clear-all-books/' + userId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Успешно удалено - удаляем все карточки из DOM
                    const bookCards = document.querySelectorAll('.book-card');
                    bookCards.forEach(card => {
                        // Плавное исчезновение
                        card.style.transition = 'all 0.3s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'translateX(100px)';
                    });

                    setTimeout(() => {
                        // Удаляем все карточки и показываем пустое состояние
                        const booksGrid = document.querySelector('.book-grid');
                        if (booksGrid) {
                            booksGrid.innerHTML = '';
                        }
                        updateBooksCount();
                        checkEmptyState();

                        // Восстанавливаем кнопку
                        if (clearAllBtn) {
                            clearAllBtn.disabled = false;
                            clearAllBtn.innerHTML = '🗑️ Удалить все книги';
                        }
                    }, 300);
                } else {
                    // Ошибка
                    alert('Ошибка при удалении всех книг: ' + data.error);
                    if (clearAllBtn) {
                        clearAllBtn.disabled = false;
                        clearAllBtn.innerHTML = '🗑️ Удалить все книги';
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Ошибка при удалении всех книг');
                if (clearAllBtn) {
                    clearAllBtn.disabled = false;
                    clearAllBtn.innerHTML = '🗑️ Удалить все книги';
                }
            });
        },
        function() {
            console.log('Clear all books cancelled');
        }
    );
}

// Функция для удаления одной книги через AJAX
function removeBook(bookId, bookTitle) {
    console.log('Removing book:', bookId, bookTitle);

    showCustomConfirm(
        `Удалить книгу "<strong>${bookTitle}</strong>" из выбранных?`,
        function() {
            // Показываем индикатор загрузки
            const bookCard = document.getElementById('book-card-' + bookId);
            if (bookCard) {
                bookCard.style.opacity = '0.5';
                bookCard.style.pointerEvents = 'none';
            }

            // Отправляем AJAX запрос
            fetch('/remove-book/' + userId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'book_id=' + bookId
            })
            .then(response => {
                console.log('Response status:', response.status);
                if (response.ok) {
                    // Успешно удалено - удаляем карточку из DOM
                    if (bookCard) {
                        // Плавное исчезновение
                        bookCard.style.transition = 'all 0.3s ease';
                        bookCard.style.opacity = '0';
                        bookCard.style.transform = 'translateX(100px)';

                        setTimeout(() => {
                            bookCard.remove();
                            updateBooksCount();
                            checkEmptyState();
                        }, 300);
                    }
                } else {
                    // Ошибка
                    alert('Ошибка при удалении книги');
                    if (bookCard) {
                        bookCard.style.opacity = '1';
                        bookCard.style.pointerEvents = 'auto';
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Ошибка при удалении книги');
                if (bookCard) {
                    bookCard.style.opacity = '1';
                    bookCard.style.pointerEvents = 'auto';
                }
            });
        },
        function() {
            console.log('Deletion cancelled');
        }
    );
}

// Функция для обновления счетчика книг
function updateBooksCount() {
    const bookCards = document.querySelectorAll('.book-card');
    const countElement = document.getElementById('books-count');
    if (countElement) {
        countElement.textContent = bookCards.length;
        console.log('Books count updated:', bookCards.length);
    }
}

// Функция для проверки пустого состояния
function checkEmptyState() {
    const bookCards = document.querySelectorAll('.book-card');
    const booksContainer = document.getElementById('books-container');

    if (bookCards.length === 0 && booksContainer) {
        console.log('Showing empty state');
        booksContainer.innerHTML = `
            <div class="empty-message">
                <h3>📚 У вас пока нет выбранных книг в Book4U</h3>
                <p>Чтобы получить персонализированные рекомендации, выберите книги которые вам нравятся</p>
                <a href="/" class="btn btn-success" style="margin-top: 15px;">
                    🎯 Выбрать книги
                </a>
            </div>
        `;

        // Скрываем кнопку "Удалить все книги" и счетчик
        const clearAllSection = document.querySelector('div[style*="text-align: center"]');
        if (clearAllSection) {
            clearAllSection.style.display = 'none';
        }
    }
}