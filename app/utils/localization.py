from pathlib import Path
from typing import Dict, Any

import i18n
import yaml

LOCALES_DIR = Path(__file__).parent.parent.parent / 'locales'
LANGUAGE_MAP = {
    'en': {'display': 'English', 'code': 'EN-US'},
    'ru': {'display': 'Русский', 'code': 'RU-RU'},
}


class LocalizationManager:
    """Class responsible for managing application localization and translations."""

    def __init__(self):
        """Initialize the localization manager and set up i18n configuration."""
        self._initialize_i18n()

    @staticmethod
    def _initialize_i18n() -> None:
        """
        Initialize i18n configuration with default settings.
        Sets up file paths, formats, and available locales.
        """
        i18n.load_path.append(str(LOCALES_DIR))
        i18n.set('filename_format', '{locale}.{format}')
        i18n.set('file_format', 'yml')
        i18n.set('skip_locale_root_data', True)
        i18n.set('fallback', 'en')
        i18n.set('available_locales', list(LANGUAGE_MAP.keys()))

    @staticmethod
    def translate(key: str, **kwargs) -> str:
        """
        Translate a key into the current locale.
        
        Args:
            key (str): Translation key to look up
            **kwargs: Variables to format in the translation string
            
        Returns:
            str: Translated string
        """
        locale = kwargs.pop('locale', i18n.get('locale'))
        return i18n.t(key, locale=locale, **kwargs)

    @staticmethod
    def get_display_name(locale: str) -> str:
        """
        Get the display name for a locale.
        
        Args:
            locale (str): Locale code
            
        Returns:
            str: Display name of the locale
        """
        return LANGUAGE_MAP.get(locale.lower(), {}).get('display', locale)

    @staticmethod
    def get_language_code(locale: str) -> str:
        """
        Get the standardized language code for a locale.
        
        Args:
            locale (str): Locale code
            
        Returns:
            str: Standardized language code (e.g., 'EN-US', 'RU-RU')
        """
        return LANGUAGE_MAP.get(locale.lower(), {}).get('code', locale.upper())

    @staticmethod
    def load_all_translations(locale: str) -> Dict[str, Any]:
        """
        Load all translations for a specific locale.
        
        Args:
            locale (str): Locale code
            
        Returns:
            Dict[str, Any]: Dictionary containing all translations for the locale
        """
        locale_file = LOCALES_DIR / f"{locale.lower()}.yml"
        try:
            with open(locale_file, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        except (FileNotFoundError, yaml.YAMLError):
            return {}

    @staticmethod
    def set_locale(locale: str) -> None:
        """
        Set the current locale for translations.
        
        Args:
            locale (str): Locale code to set as current
        """
        i18n.set('locale', locale.lower())


localization = LocalizationManager()
