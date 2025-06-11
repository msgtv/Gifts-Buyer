import asyncio
import traceback

from pyrogram import Client

from app.core.banner import display_title, get_app_info, set_window_title
from app.core.callbacks import new_callback
from app.notifications import send_start_message
from app.utils.detector import detector
from app.utils.logger import info, error
from data.config import config, t, get_language_display

app_info = get_app_info()


class Application:
    """Main application class that handles the initialization and execution of the Gifts Buyer bot."""

    @staticmethod
    async def run() -> None:
        """
        Initializes and runs the main application loop.
        Sets up the window title, displays the banner, and starts the Telegram client.
        """
        set_window_title(app_info)
        display_title(app_info, get_language_display(config.LANGUAGE))

        async with Client(
                name=config.SESSION,
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                phone_number=config.PHONE_NUMBER
        ) as client:
            await send_start_message(client)
            await detector(client, new_callback)

    @staticmethod
    def main() -> None:
        """
        Entry point of the application.
        Handles the main execution loop and error handling.
        """
        try:
            asyncio.run(Application.run())
        except KeyboardInterrupt:
            info(t("console.terminated"))
        except Exception:
            error(t("console.unexpected_error"))
            traceback.print_exc()


if __name__ == "__main__":
    Application.main() 
