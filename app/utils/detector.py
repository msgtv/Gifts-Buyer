import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from pyrogram import Client, types

from app.notifications import send_summary_message
from app.utils.logger import log_same_line, info
from data.config import config, t


# Animation constants
ANIMATION_FRAMES = 4
ANIMATION_DELAY = 0.2


class GiftDetector:
    """
    Class responsible for detecting and managing gift data.
    
    This class handles:
    - Loading and saving gift history from/to persistent storage
    - Fetching current gifts from Telegram
    - Categorizing gifts based on skip rules
    - Prioritizing gifts based on configured rules
    """

    @staticmethod
    async def load_gift_history() -> Dict[int, dict]:
        """
        Load the previously saved gift history from the data file.
        
        Returns:
            Dict[int, dict]: Dictionary where:
                - key: gift ID (int)
                - value: gift data dictionary containing properties like price, availability, etc.
                
        Note:
            Returns an empty dictionary if the history file doesn't exist.
        """
        try:
            with config.DATA_FILEPATH.open("r", encoding='utf-8') as file:
                gift_history = json.load(file)

            return {gift["id"]: gift for gift in gift_history}
        except FileNotFoundError:
            return {}

    @staticmethod
    async def save_gift_history(gifts: List[dict]) -> None:
        """
        Save the current gift data to the history file for persistence.
        
        Args:
            gifts: List of gift dictionaries containing complete gift information
                  Each gift must have at least an 'id' field
        """
        with config.DATA_FILEPATH.open("w", encoding='utf-8') as file:
            json.dump(gifts, file, indent=4, default=types.Object.default, ensure_ascii=False)

    @staticmethod
    async def fetch_current_gifts(app: Client) -> Tuple[Dict[int, dict], List[int]]:
        """
        Fetch and process currently available gifts from Telegram.
        
        Args:
            app: Initialized Telegram client instance
            
        Returns:
            Tuple containing:
            - Dictionary mapping gift IDs to their complete data
            - List of gift IDs in their original order (for maintaining position info)
        """
        current_gifts = [
            json.loads(json.dumps(gift, default=types.Object.default, ensure_ascii=False))
            for gift in await app.get_available_gifts()
        ]
        gifts_dict = {gift["id"]: gift for gift in current_gifts}
        gift_ids = list(gifts_dict.keys())
        
        return gifts_dict, gift_ids

    @staticmethod
    def categorize_skipped_gifts(gift_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Analyze a gift and determine if it should be skipped based on configuration rules.
        
        Args:
            gift_data: Complete gift information dictionary
            
        Returns:
            Dictionary with skip categories as keys and boolean values (0 or 1) indicating if the
            gift should be skipped for that reason. Categories include:
            - sold_out_count: Gift is no longer available
            - non_limited_count: Gift is not a limited edition
            - non_upgradable_count: Gift cannot be upgraded (if upgrade-only mode is enabled)
        """
        return {
            'sold_out_count': 1 if gift_data.get("is_sold_out", False) else 0,
            'non_limited_count': 0 if gift_data.get("is_limited") else 1,
            'non_upgradable_count': 1 if (config.PURCHASE_ONLY_UPGRADABLE_GIFTS and 
                                        "upgrade_price" not in gift_data) else 0
        }

    @staticmethod
    def prioritize_gifts(gifts: Dict[int, dict], gift_ids: List[int]) -> List[Tuple[int, dict]]:
        """
        Sort gifts based on configured priority rules.
        
        Args:
            gifts: Dictionary of all gifts to prioritize
            gift_ids: Original order of gift IDs for position reference
            
        Returns:
            List of (gift_id, gift_data) tuples sorted by priority rules:
            - If PRIORITIZE_LOW_SUPPLY is enabled, gifts with lower supply are prioritized
            - Original position is always considered (higher position = higher priority)
        """
        # Add position information to each gift
        for gift_id, gift_data in gifts.items():
            gift_data["position"] = len(gift_ids) - gift_ids.index(gift_id)

        # Sort by position first
        position_sorted = sorted(gifts.items(), key=lambda x: x[1]["position"])

        if not config.PRIORITIZE_LOW_SUPPLY:
            return position_sorted

        # If enabled, prioritize by supply amount and then position
        return sorted(
            position_sorted, 
            key=lambda x: (
                x[1].get("total_amount", float('inf')) if x[1].get("is_limited", False) else float('inf'), 
                x[1]["position"],
            )
        )


class GiftMonitor:
    """
    Class responsible for continuously monitoring and processing new gifts.
    
    This class handles:
    - Running the main detection loop
    - Processing newly detected gifts
    - Managing the detection animation
    - Coordinating with the callback handler
    """

    @staticmethod
    async def run_detection_loop(app: Client, callback: Callable) -> None:
        """
        Run the continuous gift detection loop.
        
        Args:
            app: Initialized Telegram client instance
            callback: Function to call for each new gift detected
                     Should accept (app: Client, gift_data: dict) as parameters
        """
        animation_counter = 0

        while True:
            # Update loading animation
            animation_counter = (animation_counter + 1) % ANIMATION_FRAMES
            log_same_line(f'{t("console.gift_checking")}{"." * animation_counter}')
            time.sleep(ANIMATION_DELAY)

            # Ensure connection is active
            if not app.is_connected:
                await app.start()

            # Compare current gifts with history
            old_gifts = await GiftDetector.load_gift_history()
            current_gifts, gift_ids = await GiftDetector.fetch_current_gifts(app)

            # Identify new gifts
            new_gifts = {
                gift_id: gift_data for gift_id, gift_data in current_gifts.items()
                if gift_id not in old_gifts
            }

            # Process any new gifts found
            if new_gifts:
                await GiftMonitor._process_new_gifts(app, new_gifts, gift_ids, callback)

            # Update history and wait for next check
            await GiftDetector.save_gift_history(list(current_gifts.values()))
            await asyncio.sleep(config.INTERVAL)

    @staticmethod
    async def _process_new_gifts(
        app: Client,
        new_gifts: Dict[int, dict],
        gift_ids: List[int],
        callback: Callable
    ) -> None:
        """
        Process and handle newly detected gifts.
        
        Args:
            app: Telegram client instance
            new_gifts: Dictionary of newly detected gifts
            gift_ids: List of all gift IDs in original order
            callback: Handler function for processing each gift
        """
        info(f'{t("console.new_gifts")} {len(new_gifts)}')

        # Track gifts skipped for various reasons
        skip_counts = {'sold_out_count': 0, 'non_limited_count': 0, 'non_upgradable_count': 0}

        # Categorize all new gifts
        for gift_data in new_gifts.values():
            gift_skips = GiftDetector.categorize_skipped_gifts(gift_data)
            for key, value in gift_skips.items():
                skip_counts[key] += value

        # Process gifts in priority order
        prioritized_gifts = GiftDetector.prioritize_gifts(new_gifts, gift_ids)
        for gift_id, gift_data in prioritized_gifts:
            gift_data['id'] = gift_id
            await callback(app, gift_data)

        # Send summary notifications
        await send_summary_message(app, **skip_counts)

        # Log skip summary if any gifts were skipped
        if any(skip_counts.values()):
            info(t("console.skip_summary",
                  sold_out=skip_counts['sold_out_count'],
                  non_limited=skip_counts['non_limited_count'],
                  non_upgradable=skip_counts['non_upgradable_count']))


# Convenience alias for the main detection loop
detector = GiftMonitor.run_detection_loop
