import asyncio
from typing import Dict, Any, Tuple, List, Optional

from pyrogram import Client

from app.notifications import send_notification
from app.purchase import buy_gift
from app.utils.logger import warn, info
from data.config import config, t


class GiftProcessor:
    """
    Class responsible for evaluating and processing new gifts.
    
    This class contains methods to determine if a gift is eligible for purchase
    based on various business rules and configurations.
    """

    @staticmethod
    async def evaluate_gift(gift_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate if a gift is eligible for purchase based on various rules.
        
        Args:
            gift_data (Dict[str, Any]): Gift data containing:
                - price: int, cost of the gift
                - is_limited: bool, whether it's a limited edition
                - is_sold_out: bool, availability status
                - upgrade_price: Optional[int], price for upgrade if available
                - total_amount: int, total quantity available (for limited gifts)
            
        Returns:
            Tuple[bool, Dict[str, Any]]: A tuple containing:
                - bool: True if gift is eligible, False otherwise
                - Dict[str, Any]: Processing data or reason for exclusion
                
        Example:
            >>> gift_data = {
            ...     "price": 100,
            ...     "is_limited": True,
            ...     "is_sold_out": False,
            ...     "total_amount": 50
            ... }
            >>> is_eligible, data = await GiftProcessor.evaluate_gift(gift_data)
        """
        # Extract gift properties
        gift_price = gift_data.get("price", 0)
        is_limited = gift_data.get("is_limited", False)
        is_sold_out = gift_data.get("is_sold_out", False)
        is_upgradable = "upgrade_price" in gift_data
        total_amount = gift_data.get("total_amount", 0) if is_limited else 0

        # Define exclusion rules with clear conditions
        exclusion_rules = {
            'sold_out': lambda: is_sold_out,  # Gift is no longer available
            'non_limited_blocked': lambda: not is_limited,  # Only limited gifts are allowed
            'non_upgradable_blocked': lambda: (
                config.PURCHASE_ONLY_UPGRADABLE_GIFTS and not is_upgradable
            )  # Must be upgradable if configured
        }

        # Check if any exclusion rule is triggered
        failed_rule = next(
            (rule for rule, condition in exclusion_rules.items() if condition()),
            None
        )

        if failed_rule is None:
            # If no rules are violated, evaluate price and amount ranges
            return GiftProcessor._evaluate_range_match(gift_price, total_amount)

        return False, {'exclusion_reason': failed_rule}

    @staticmethod
    def _evaluate_range_match(gift_price: int, total_amount: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if gift price and amount match configured ranges.
        
        Args:
            gift_price (int): Price of the gift
            total_amount (int): Total amount available for limited gifts
            
        Returns:
            Tuple[bool, Dict[str, Any]]: A tuple containing:
                - bool: True if ranges match configuration
                - Dict[str, Any]: Matching data including quantity and recipients
        """
        # Get matching range from configuration
        range_matched, quantity, recipients = config.get_matching_range(
            gift_price,
            total_amount
        )

        if range_matched:
            return True, {
                'quantity': quantity,
                'recipients': recipients
            }

        return False, {
            "range_error": True,
            "gift_price": gift_price,
            "total_amount": total_amount
        }


async def process_new_gift(app: Client, gift_data: Dict[str, Any]) -> None:
    """
    Process a newly detected gift by evaluating eligibility and handling distribution.
    
    Args:
        app (Client): Telegram client instance for communication
        gift_data (Dict[str, Any]): Complete gift data to process
        
    Example:
        >>> gift_data = {
        ...     "id": 12345,
        ...     "price": 100,
        ...     "is_limited": True
        ... }
        >>> await process_new_gift(app, gift_data)
    """
    gift_id = gift_data.get("id")

    # Evaluate if the gift is eligible for processing
    is_eligible, processing_data = await GiftProcessor.evaluate_gift(gift_data)

    if not is_eligible:
        # If not eligible, send notification with processing data
        return await send_notification(app, gift_id, **processing_data)
    
    # If eligible, distribute gifts to recipients
    quantity = processing_data.get("quantity", 1)
    recipients = processing_data.get("recipients", [])
    return await _distribute_gifts(app, gift_id, quantity, recipients)


async def _distribute_gifts(
    app: Client,
    gift_id: int,
    quantity: int,
    recipients: List[int]
) -> None:
    """
    Distribute gifts to specified recipients with error handling.
    
    Args:
        app (Client): Telegram client instance
        gift_id (int): ID of the gift to distribute
        quantity (int): Number of gifts per recipient
        recipients (List[int]): List of recipient chat IDs
    """
    info(t("console.processing_gift",
           gift_id=gift_id,
           quantity=quantity,
           recipients_count=len(recipients)))

    for recipient_id in recipients:
        try:
            # Attempt to purchase gift for recipient
            await buy_gift(app, recipient_id, gift_id, quantity)
        except Exception as ex:
            # Log warning and notify about purchase failure
            warn(t("console.purchase_error",
                  gift_id=gift_id,
                  chat_id=recipient_id))
            await send_notification(app, gift_id, error_message=str(ex))
        
        # Add delay between purchases to avoid rate limiting
        await asyncio.sleep(0.5)


# Main callback function for new gifts
new_callback = process_new_gift
