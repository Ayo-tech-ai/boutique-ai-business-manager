"""
Agent-facing tool functions for the Boutique AI Business Manager.

These wrap BoutiqueService methods with:
- string-to-number coercion (tolerates models that stringify numeric args)
- rich docstrings that double as instructions to the LLM
"""

from typing import Optional


def _to_int(value, field_name):
    """Safely converts a value to int, tolerating string input from
    models that stringify arguments (e.g. some Groq models)."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "null", "none"):
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a whole number for {field_name}.")
    return int(value)


def _to_float(value, field_name):
    """Safely converts a value to float, same tolerance as _to_int."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "null", "none"):
            return None
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Could not interpret '{value}' as a number for {field_name}.")
    return float(value)


def build_tool_functions(boutique_service):
    """
    Factory that binds tool functions to a specific BoutiqueService
    instance. Returns a dict of {name: function} ready to wrap in
    FunctionTool.

    This indirection exists because Streamlit reruns the script on
    every interaction — binding via closure avoids relying on a
    module-level global that could go stale across reruns.
    """

    def log_sale(
        item_name: str,
        quantity_sold: Optional[str] = None,
        sale_price: Optional[str] = None,
        size: Optional[str] = None,
        color: Optional[str] = None,
        customer_name: Optional[str] = None,
        payment_method: Optional[str] = None,
        confirmed_item_id: Optional[str] = None,
    ):
        """
        Log a boutique sale and update stock levels.

        Use this whenever the owner tells you an item was sold.

        NOTE: quantity_sold, sale_price, and confirmed_item_id are
        accepted as text and converted internally to numbers.

        If size or color is not given but the item name alone is
        ambiguous (multiple variants exist), ask the owner to clarify
        before logging — do not guess which variant was sold.

        If the tool result has needs_clarification = True, do NOT
        create a new item and do NOT guess. Show the owner the
        possible_matches in plain terms (never mention item IDs) and
        ask a simple yes/no: is this the same item, just missing
        detail, or a different item? Once confirmed, call this tool
        again passing that item's item_id as confirmed_item_id
        silently — do not ask the owner for the ID.

        If sale_price is not provided, ask for it — never assume the
        item's list price was the actual price sold at.

        The result includes 'low_stock_alert' (True/False) — if True,
        proactively mention the remaining stock is low, without being
        asked.

        Args:
            item_name: Name of the item sold (e.g. "Ankara Wrap Dress").
            quantity_sold: Number of units sold.
            sale_price: Actual price sold at.
            size: Size of the item, if applicable.
            color: Color of the item, if applicable.
            customer_name: Name of the customer, if mentioned.
            payment_method: e.g. "cash", "transfer", "POS".
            confirmed_item_id: Exact inventory item_id to sell against,
                only used after the owner has confirmed a clarification.
        """
        parsed_qty = _to_int(quantity_sold, "quantity_sold")
        parsed_price = _to_float(sale_price, "sale_price")
        parsed_confirmed_id = _to_int(confirmed_item_id, "confirmed_item_id")

        if parsed_qty is None:
            raise ValueError("quantity_sold is required to log a sale.")
        if parsed_price is None:
            raise ValueError("sale_price is required to log a sale.")

        return boutique_service.log_sale(
            item_name=item_name,
            quantity_sold=parsed_qty,
            sale_price=parsed_price,
            size=size,
            color=color,
            customer_name=customer_name,
            payment_method=payment_method,
            confirmed_item_id=parsed_confirmed_id,
        )

    def log_expense(
        description: str,
        amount: Optional[str] = None,
        category: Optional[str] = None,
    ):
        """
        Log a business expense.

        Use this whenever the owner mentions spending money on the
        business — restocking fabric, delivery fees, marketing, etc.

        NOTE: If the expense is specifically for adding new stock of
        an existing or new item, prefer log_restock or
        add_or_update_item instead — this keeps inventory numbers
        accurate. Use log_expense for costs that do NOT map to a
        specific inventory item (e.g. "delivery fee", "Instagram ads",
        "shop rent").

        Args:
            description: What the expense was for.
            amount: How much was spent.
            category: e.g. "Logistics", "Marketing", "Rent".
        """
        parsed_amount = _to_float(amount, "amount")
        if parsed_amount is None:
            raise ValueError("amount is required to log an expense.")

        return boutique_service.log_expense(
            description=description,
            amount=parsed_amount,
            category=category,
        )

    def log_restock(
        item_name: str,
        quantity_added: Optional[str] = None,
        size: Optional[str] = None,
        color: Optional[str] = None,
        cost_price: Optional[str] = None,
        confirmed_item_id: Optional[str] = None,
    ):
        """
        Log new stock arriving for an EXISTING inventory item.

        Use this when the owner says they've restocked or received
        more units of something already in inventory. If the item
        doesn't exist yet, tell the owner and use add_or_update_item
        to create it first.

        If the tool result has needs_clarification = True, ask the
        owner (in plain terms, never mentioning item IDs) to confirm
        which existing item this refers to, then call this tool
        again with that item's item_id as confirmed_item_id.

        Args:
            item_name: Name of the item being restocked.
            quantity_added: Number of new units added.
            size: Size, if the item has size variants.
            color: Color, if the item has color variants.
            cost_price: Cost price per unit for this restock batch.
            confirmed_item_id: Exact inventory item_id to restock,
                only used after the owner has confirmed a clarification.
        """
        parsed_qty = _to_int(quantity_added, "quantity_added")
        parsed_cost = _to_float(cost_price, "cost_price")
        parsed_confirmed_id = _to_int(confirmed_item_id, "confirmed_item_id")

        if parsed_qty is None:
            raise ValueError("quantity_added is required to log a restock.")

        return boutique_service.log_restock(
            item_name=item_name,
            quantity_added=parsed_qty,
            size=size,
            color=color,
            cost_price=parsed_cost,
            confirmed_item_id=parsed_confirmed_id,
        )

    def add_or_update_item(
        item_name: Optional[str] = None,
        category: Optional[str] = None,
        size: Optional[str] = None,
        color: Optional[str] = None,
        cost_price: Optional[str] = None,
        selling_price: Optional[str] = None,
        quantity_in_stock: Optional[str] = None,
        low_stock_threshold: Optional[str] = None,
        confirmed_item_id: Optional[str] = None,
    ):
        """
        Create a new inventory item, or update fields on an existing one.

        Use this when the owner introduces a brand-new item, or wants
        to change price, category, or threshold on an existing item.

        item_name is required UNLESS confirmed_item_id is provided —
        once the owner has confirmed which existing item a
        clarification refers to, call this again with
        confirmed_item_id and item_name can be omitted.

        An item is matched by EXACT item_name + size + color. If no
        exact match exists but similar items are found
        (needs_clarification = True), do NOT create a new item — show
        the owner the possible_matches in plain terms (never mention
        item IDs) and ask if this is the same item, just missing
        detail. Once confirmed, call this tool again with that item's
        item_id as confirmed_item_id to update it directly.

        When creating a brand-new item, if the owner did not mention
        a starting quantity, ASK for it before considering the item
        fully set up — do not assume 0 or report a stock count you
        were not explicitly told.

        Args:
            item_name: Name of the item (e.g. "Ankara Wrap Dress").
                Required unless confirmed_item_id is given.
            category: e.g. "Dress", "Bag", "Shoe".
            size: Size, if applicable.
            color: Color, if applicable.
            cost_price: What the boutique paid per unit.
            selling_price: List/asking price per unit.
            quantity_in_stock: Current stock count (only set directly
                for corrections — use log_restock for normal restocking).
            low_stock_threshold: Stock level to trigger low stock
                alerts. Defaults to 3 for new items.
            confirmed_item_id: Exact inventory item_id to update, only
                used after the owner has confirmed a clarification.
        """
        return boutique_service.add_or_update_item(
            item_name=item_name,
            category=category,
            size=size,
            color=color,
            cost_price=_to_float(cost_price, "cost_price"),
            selling_price=_to_float(selling_price, "selling_price"),
            quantity_in_stock=_to_int(quantity_in_stock, "quantity_in_stock"),
            low_stock_threshold=_to_int(low_stock_threshold, "low_stock_threshold"),
            confirmed_item_id=_to_int(confirmed_item_id, "confirmed_item_id"),
        )

    def check_inventory(item_name: Optional[str] = None, low_stock_only: Optional[str] = None):
        """
        Check current inventory levels.

        Use this when the owner asks what's in stock, how many of an
        item remain, or wants to see what's running low.

        Args:
            item_name: Optional partial name to filter by (e.g.
                "dress" matches "Ankara Wrap Dress"). Omit to see all.
            low_stock_only: Pass "true" to only show items at or below
                their low stock threshold. Omit or "false" for all.
        """
        is_low_stock_only = (
            str(low_stock_only).strip().lower() in ("true", "yes", "1")
            if low_stock_only else False
        )

        return boutique_service.check_inventory(
            item_name=item_name,
            low_stock_only=is_low_stock_only,
        )

    def get_sales_summary(start_date: str, end_date: str):
        """
        Get total sales, revenue, and best sellers over a date range.

        Convert relative periods (e.g. "this week", "last month") into
        exact YYYY-MM-DD start and end dates BEFORE calling this tool.

        Args:
            start_date: Start of range, YYYY-MM-DD.
            end_date: End of range, YYYY-MM-DD.
        """
        return boutique_service.get_sales_summary(start_date=start_date, end_date=end_date)

    def get_customer_history(customer_name: str):
        """
        Get a customer's purchase history, most recent first.

        Use this when the owner asks what a specific customer has
        bought before, or wants to follow up with a repeat customer.

        Args:
            customer_name: Name of the customer.
        """
        history = boutique_service.get_customer_history(customer_name)
        return {
            "customer_name": customer_name,
            "purchase_count": len(history),
            "purchases": history,
        }

    return {
        "log_sale": log_sale,
        "log_expense": log_expense,
        "log_restock": log_restock,
        "add_or_update_item": add_or_update_item,
        "check_inventory": check_inventory,
        "get_sales_summary": get_sales_summary,
        "get_customer_history": get_customer_history,
    }
