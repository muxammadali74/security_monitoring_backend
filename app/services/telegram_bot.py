import logging

import requests

from config import settings

logger = logging.getLogger(__name__)


class TelegramApiError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(self) -> None:
        self._token = settings.TELEGRAM_BOT_TOKEN
        self.username: str | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self._token
            and self._token != "YOUR_TELEGRAM_BOT_TOKEN_HERE"
        )

    def _request(self, method: str, *, params=None, data=None, files=None):
        if not self._token:
            raise TelegramApiError("Telegram bot is not configured.")

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self._token}/{method}",
                params=params,
                data=data,
                files=files,
                timeout=(5, 30),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise TelegramApiError("Telegram API request failed.") from None

        if not isinstance(payload, dict) or not payload.get("ok"):
            raise TelegramApiError("Telegram API rejected the request.")
        return payload.get("result")

    def get_me(self) -> dict:
        result = self._request("getMe")
        if not isinstance(result, dict):
            raise TelegramApiError("Telegram bot returned invalid account data.")
        username = result.get("username")
        if not isinstance(username, str) or not username:
            raise TelegramApiError("Telegram bot has no public username.")
        self.username = username
        return result

    def get_updates(self, offset: int | None) -> list[dict]:
        params: dict[str, int] = {"timeout": 20}
        if offset is not None:
            params["offset"] = offset
        result = self._request("getUpdates", params=params)
        if not isinstance(result, list):
            raise TelegramApiError("Telegram bot returned invalid update data.")
        return result

    def send_message(self, chat_id: str, text: str) -> None:
        self._request(
            "sendMessage",
            data={"chat_id": chat_id, "text": text},
        )

    def send_photo(self, chat_id: str, image: bytes, caption: str) -> None:
        self._request(
            "sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("vision-alert.jpg", image, "image/jpeg")},
        )


telegram_bot = TelegramBotClient()
