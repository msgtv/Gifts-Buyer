from typing import Tuple, Optional

from pyrogram import Client
from pyrogram.errors import RPCError

from app.errors import handle_gift_error
from app.notifications import send_notification
from app.utils.helper import get_recipient_info, get_user_balance
from app.utils.logger import success, warn
from data.config import t


class GiftPurchaser:
    """
    Class responsible for handling gift purchase operations.
    
    This class provides functionality to purchase and send gifts to Telegram users,
    handling balance checks, notifications, and error cases.
    """

    @staticmethod
    async def buy_gift(
        app: Client,
        chat_id: int,
        gift_id: int,
        quantity: int = 1
    ) -> None:
        """
        Purchase and send gift(s) to a recipient.
        
        Args:
            app: Telegram client instance for making API calls
            chat_id: Telegram chat ID of the gift recipient
            gift_id: Identifier of the gift to purchase
            quantity: Number of gifts to purchase (defaults to 1)
            
        Note:
            If user has insufficient balance, will purchase maximum possible amount
            and send appropriate notifications.
        """
        # Get recipient and gift information
        recipient_info, username = await get_recipient_info(app, chat_id)
        gift_price = await GiftPurchaser._get_gift_price(app, gift_id)
        current_balance = await get_user_balance(app)

        # Calculate maximum affordable quantity
        max_affordable = (
            min(quantity, current_balance // gift_price)
            if gift_price > 0
            else quantity
        )

        # Handle insufficient balance case
        if max_affordable == 0:
            await GiftPurchaser._handle_insufficient_balance(
                app,
                gift_id,
                gift_price,
                current_balance,
                quantity
            )
            return

        # Process the purchase
        await GiftPurchaser._purchase_gifts(
            app,
            chat_id,
            gift_id,
            max_affordable,
            recipient_info,
            username
        )

        # Notify if only partial quantity was purchased
        if max_affordable < quantity:
            await GiftPurchaser._notify_partial_purchase(
                app,
                gift_id,
                quantity,
                max_affordable,
                gift_price,
                current_balance
            )

    @staticmethod
    async def _get_gift_price(app: Client, gift_id: int) -> int:
        """
        Retrieve the price of a specific gift.
        
        Args:
            app: Telegram client instance
            gift_id: ID of the gift to check
            
        Returns:
            Price of the gift, or 0 if price cannot be determined
        """
        try:
            gifts = await app.get_available_gifts()
            return next(
                (gift.price for gift in gifts if gift.id == gift_id),
                0
            )
        except Exception:
            return 0

    @staticmethod
    async def _purchase_gifts(
        app: Client,
        chat_id: int,
        gift_id: int,
        quantity: int,
        recipient_info: str,
        username: str
    ) -> None:
        """
        Process multiple gift purchases for a recipient.
        
        Args:
            app: Telegram client instance
            chat_id: Recipient's chat ID
            gift_id: ID of the gift to send
            quantity: Number of gifts to purchase
            recipient_info: Formatted recipient information for logging
            username: Username of the recipient
        """
        for current_gift in range(1, quantity + 1):
            try:
                await app.send_gift(
                    chat_id=chat_id,
                    gift_id=gift_id,
                    hide_my_name=True
                )
                
                success(t(
                    "console.gift_sent",
                    current=current_gift,
                    total=quantity,
                    gift_id=gift_id,
                    recipient=recipient_info
                ))
                
                await send_notification(
                    app,
                    gift_id,
                    user_id=chat_id,
                    username=username,
                    current_gift=current_gift,
                    total_gifts=quantity,
                    success_message=True
                )
                
            except RPCError as ex:
                current_balance = await get_user_balance(app)
                await handle_gift_error(
                    app,
                    ex,
                    gift_id,
                    chat_id,
                    await GiftPurchaser._get_gift_price(app, gift_id),
                    current_balance
                )
                break

    @staticmethod
    async def _handle_insufficient_balance(
        app: Client,
        gift_id: int,
        gift_price: int,
        current_balance: int,
        requested_quantity: int
    ) -> None:
        """
        Handle cases where user has insufficient balance for gift purchase.
        
        Args:
            app: Telegram client instance
            gift_id: ID of the gift
            gift_price: Price per gift
            current_balance: User's current balance
            requested_quantity: Number of gifts user attempted to purchase
        """
        warn(t(
            "console.insufficient_balance_for_quantity",
            gift_id=gift_id,
            requested=requested_quantity,
            price=gift_price,
            balance=current_balance
        ))
        
        await send_notification(
            app,
            gift_id,
            balance_error=True,
            gift_price=gift_price * requested_quantity,
            current_balance=current_balance
        )

    @staticmethod
    async def _notify_partial_purchase(
        app: Client,
        gift_id: int,
        requested: int,
        purchased: int,
        gift_price: int,
        remaining_balance: int
    ) -> None:
        """
        Notify user about partial gift purchase due to insufficient balance.
        
        Args:
            app: Telegram client instance
            gift_id: ID of the gift
            requested: Originally requested quantity
            purchased: Actually purchased quantity
            gift_price: Price per gift
            remaining_balance: User's remaining balance
        """
        warn(t(
            "console.partial_purchase",
            gift_id=gift_id,
            purchased=purchased,
            requested=requested,
            remaining_needed=(requested - purchased) * gift_price,
            current_balance=remaining_balance
        ))
        
        await send_notification(
            app,
            gift_id,
            partial_purchase=True,
            purchased=purchased,
            requested=requested,
            remaining_cost=(requested - purchased) * gift_price,
            current_balance=remaining_balance
        )


# Convenience function for direct access to gift purchase
buy_gift = GiftPurchaser.buy_gift
