import configparser
import sys
import os
from pathlib import Path
from typing import List, Union, Dict, Any

from dotenv import load_dotenv

from app.utils.localization import localization
from app.utils.logger import error


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


class Config:
    """Class responsible for loading, parsing and managing application configuration."""

    def __init__(self):
        """
        Initialize configuration manager.
        Loads config file, sets up paths, properties and validates configuration.
        """
        self.parser = configparser.ConfigParser()
        self._load_config()
        self._setup_paths()
        self._setup_properties()
        self._validate()
        localization.set_locale(self.LANGUAGE)

    def _load_config(self) -> None:
        """
        Load configuration from config.ini file.
        Exits with error if file not found.
        """
        config_file = Path('config.ini')
        config_file.exists() or self._exit_with_error("Configuration file 'config.ini' not found!")
        self.parser.read(config_file, encoding='utf-8')

    def _setup_paths(self) -> None:
        """Set up paths for session and data storage."""
        base_dir = Path(__file__).parent
        self.SESSION = str(base_dir.parent / "data/account")
        self.DATA_FILEPATH = base_dir / "json/history.json"

    def _setup_properties(self) -> None:
        """
        Set up configuration properties from config file.
        Includes Telegram API credentials, bot settings, and gift preferences.
        """
        # self.API_ID = self.parser.getint('Telegram', 'API_ID', fallback=0)
        # self.API_HASH = self.parser.get('Telegram', 'API_HASH', fallback='')
        # self.PHONE_NUMBER = self.parser.get('Telegram', 'PHONE_NUMBER', fallback='')

        self.API_ID = os.getenv('API_ID', 0)
        self.API_HASH = os.getenv('API_HASH', '')
        self.PHONE_NUMBER = os.getenv('PHONE_NUMBER', '')

        self.CHANNEL_ID = self._parse_channel_id()

        self.INTERVAL = self.parser.getfloat('Bot', 'INTERVAL', fallback=15.0)
        self.LANGUAGE = self.parser.get('Bot', 'LANGUAGE', fallback='EN').lower()

        self.GIFT_RANGES = self._parse_gift_ranges()
        self.PURCHASE_ONLY_UPGRADABLE_GIFTS = self.parser.getboolean('Gifts', 'PURCHASE_ONLY_UPGRADABLE_GIFTS',
                                                                     fallback=False)
        self.PRIORITIZE_LOW_SUPPLY = self.parser.getboolean('Gifts', 'PRIORITIZE_LOW_SUPPLY', fallback=False)

    def _parse_channel_id(self) -> Union[int, str, None]:
        """
        Parse channel ID from configuration.
        
        Returns:
            Union[int, str, None]: Channel ID as integer for numeric IDs, string for usernames, or None if empty
        """
        # channel_value = self.parser.get('Telegram', 'CHANNEL_ID', fallback='').strip()
        channel_value = os.getenv('CHANNEL_ID', '').strip()

        channel_processors = {
            'empty_or_default': {
                'condition': lambda val: not val or val == '-100',
                'handler': lambda val: None
            },
            'username_with_at': {
                'condition': lambda val: val.startswith('@'),
                'handler': lambda val: channel_value
            },
            'negative_channel_id': {
                'condition': lambda val: val.startswith('-') and val[1:].isdigit(),
                'handler': lambda val: int(channel_value)
            },
            'numeric_id': {
                'condition': lambda val: val.isdigit(),
                'handler': lambda val: int(channel_value) or None
            },
            'username_fallback': {
                'condition': lambda val: True,
                'handler': lambda val: f"@{channel_value}"
            }
        }

        return self._process_with_handlers(channel_value, channel_processors)

    def _parse_gift_ranges(self) -> List[Dict[str, Any]]:
        """
        Parse gift ranges from configuration.
        
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing gift range configurations
        """
        ranges_str = self.parser.get('Gifts', 'GIFT_RANGES', fallback='')
        ranges = []

        for range_item in ranges_str.split(','):
            range_item = range_item.strip()
            range_item and ranges.append(self._parse_single_range(range_item))

        return [r for r in ranges if r]

    def _parse_single_range(self, range_item: str) -> Dict[str, Any]:
        """
        Parse a single gift range configuration string.
        
        Args:
            range_item (str): Gift range configuration string
            
        Returns:
            Dict[str, Any]: Dictionary containing parsed range configuration
        """
        try:
            price_part, rest = range_item.split(':', 1)
            supply_qty_part, recipients_part = rest.strip().split(':', 1)
            supply_part, quantity_part = supply_qty_part.strip().split(' x ')

            min_price, max_price = map(int, price_part.strip().split('-'))
            supply_limit = int(supply_part.strip())
            quantity = int(quantity_part.strip())
            recipients = self._parse_recipients_list(recipients_part.strip())

            return {
                'min_price': min_price,
                'max_price': max_price,
                'supply_limit': supply_limit,
                'quantity': quantity,
                'recipients': recipients
            }
        except (ValueError, IndexError):
            error(f"Invalid gift range format: {range_item}")
            return {}

    def _parse_recipients_list(self, recipients_str: str) -> List[Union[int, str]]:
        """
        Parse list of recipients from configuration string.
        
        Args:
            recipients_str (str): Comma-separated list of recipients
            
        Returns:
            List[Union[int, str]]: List of recipient IDs or usernames
        """
        recipients = []

        for recipient in recipients_str.split(','):
            recipient = recipient.strip()
            recipient and recipients.append(self._parse_single_recipient(recipient))

        return [r for r in recipients if r is not None]

    def _parse_single_recipient(self, recipient: str) -> Union[int, str, None]:
        """
        Parse a single recipient identifier.
        
        Args:
            recipient (str): Recipient identifier string
            
        Returns:
            Union[int, str, None]: Parsed recipient ID or username
        """
        recipient_processors = {
            'username_with_at': {
                'condition': lambda uid: uid.startswith('@'),
                'handler': lambda uid: uid[1:]
            },
            'numeric_id': {
                'condition': lambda uid: uid.isdigit(),
                'handler': lambda uid: int(uid)
            },
            'username_without_at': {
                'condition': lambda: True,
                'handler': lambda uid: uid
            }
        }

        return self._process_with_handlers(recipient, recipient_processors)

    @staticmethod
    def _process_with_handlers(value: str, processors: Dict) -> Any:
        """
        Process a value through a series of condition-handler pairs.
        
        Args:
            value (str): Value to process
            processors (Dict): Dictionary of processors with conditions and handlers
            
        Returns:
            Any: Result from the first matching processor's handler
        """
        for processor in processors.values():
            condition_func = processor['condition']
            condition_result = condition_func(value)
            # condition_result and processor['handler'](value) if 'handler' in processor else processor['handler']()

            if condition_result:
                return processor['handler'](value)
        return None

    def get_matching_range(self, price: int, total_amount: int) -> tuple[bool, int, List[Union[int, str]]]:
        """
        Find matching gift range configuration for given price and amount.
        
        Args:
            price (int): Gift price
            total_amount (int): Total amount of gifts
            
        Returns:
            tuple[bool, int, List[Union[int, str]]]: Tuple containing match status, quantity and recipients list
        """
        matching_ranges = [
            (range_config['quantity'], range_config['recipients'])
            for range_config in self.GIFT_RANGES
            if (range_config['min_price'] <= price <= range_config['max_price'] and
                total_amount <= range_config['supply_limit'])
        ]

        return (True, *matching_ranges[0]) if matching_ranges else (False, 0, [])

    def _validate(self) -> None:
        """
        Validate required configuration fields.
        Exits with error if any required field is missing or invalid.
        """
        validation_rules = {
            "Telegram > API_ID": lambda: self.API_ID == 0,
            "Telegram > API_HASH": lambda: not self.API_HASH,
            "Telegram > PHONE_NUMBER": lambda: not self.PHONE_NUMBER,
            "Gifts > GIFT_RANGES": lambda: not self.GIFT_RANGES,
        }

        invalid_fields = [field for field, check in validation_rules.items() if check()]
        invalid_fields and self._exit_with_validation_error(invalid_fields)

    @staticmethod
    def _exit_with_error(message: str) -> None:
        """
        Log error message and exit application.
        
        Args:
            message (str): Error message to log
        """
        error(message)
        sys.exit(1)

    def _exit_with_validation_error(self, invalid_fields: List[str]) -> None:
        """
        Handle validation error by logging missing fields and exiting.
        
        Args:
            invalid_fields (List[str]): List of invalid configuration fields
        """
        error_msg = localization.translate("errors.missing_config").format(
            '\n'.join(f'- {field}' for field in invalid_fields))
        self._exit_with_error(error_msg)

    @property
    def language_display(self) -> str:
        """Get display name of current language."""
        return localization.get_display_name(self.LANGUAGE)

    @property
    def language_code(self) -> str:
        """Get standardized language code of current language."""
        return localization.get_language_code(self.LANGUAGE)


config = Config()
t = localization.translate
get_language_display = localization.get_display_name
get_language_code = localization.get_language_code
get_all_translations = localization.load_all_translations
