import uvicorn
import os

if __name__ == "__main__":
    # Создаем необходимые директории
    os.makedirs("data", exist_ok=True)
    os.makedirs("app/templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
