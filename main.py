from handlers import app
import os
from config import BASE_DOWNLOAD_FOLDER
from handlers import delete_command

if __name__ == "__main__":
    print("Bot is starting...")
    # Ensure download folder exists
    if not os.path.exists(BASE_DOWNLOAD_FOLDER):
        os.makedirs(BASE_DOWNLOAD_FOLDER)
    app.run()
