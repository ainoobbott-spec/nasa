import os

def run_flask():
    # Render сам назначает порт через переменную окружения PORT. 
    # Если её нет, используем 10000 (стандарт Render).
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)
