"""
BoutiqueService — SQLite data layer for the Boutique AI Business Manager.

Handles customers, inventory, sales, expenses, and restocks.
All timestamps are stored in WAT (West Africa Time, UTC+1) rather than
relying on SQLite's default UTC, since the target users operate in Lagos.
"""

import sqlite3
from datetime import datetime, timezone, timedelta

WAT = timezone(timedelta(hours=1))


def now_wat_str():
    """Returns current Lagos (WAT, UTC+1) time as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S")


def init_db(database_name):
    """Creates all boutique tables if they don't already exist."""
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        instagram_handle TEXT,
        created_at TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        category TEXT,
        size TEXT,
        color TEXT,
        cost_price REAL,
        selling_price REAL,
        quantity_in_stock INTEGER DEFAULT 0,
        low_stock_threshold INTEGER DEFAULT 3,
        created_at TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER REFERENCES inventory(item_id),
        customer_id INTEGER REFERENCES customers(customer_id),
        quantity_sold INTEGER NOT NULL,
        sale_price REAL NOT NULL,
        payment_method TEXT,
        sale_date TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        category TEXT,
        amount REAL NOT NULL,
        expense_date TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restocks (
        restock_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER REFERENCES inventory(item_id),
        quantity_added INTEGER NOT NULL,
        cost_price REAL,
        restock_date TIMESTAMP
    );
    """)

    connection.commit()
    connection.close()


class BoutiqueService:

    def __init__(self, database_name):
        self.database_name = database_name

    def get_connection(self):
        return sqlite3.connect(self.database_name)

    # ---------------- CUSTOMERS ----------------

    def find_or_create_customer(self, name, phone=None, instagram_handle=None):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM customers WHERE LOWER(name) = LOWER(?)",
            (name,)
        )
        row = cursor.fetchone()

        if row:
            customer_id = row["customer_id"]
        else:
            cursor.execute(
                """
                INSERT INTO customers (name, phone, instagram_handle, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, phone, instagram_handle, now_wat_str())
            )
            connection.commit()
            customer_id = cursor.lastrowid

        connection.close()
        return customer_id

    def get_customer_history(self, name):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT s.sale_id, s.quantity_sold, s.sale_price, s.payment_method,
                   s.sale_date, i.item_name, i.size, i.color
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            JOIN inventory i ON s.item_id = i.item_id
            WHERE LOWER(c.name) = LOWER(?)
            ORDER BY s.sale_date DESC
            """,
            (name,)
        )
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    def get_all_customers(self, limit=20):
        """Returns recent customers."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute("""
            SELECT customer_id, name, phone, instagram_handle, created_at
            FROM customers
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    # ---------------- INVENTORY ----------------

    def find_item(self, item_name, size=None, color=None):
        """Finds an inventory item by EXACT name+size+color match
        (NULL-aware). Returns the row dict or None."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        query = "SELECT * FROM inventory WHERE LOWER(item_name) = LOWER(?)"
        params = [item_name]

        if size:
            query += " AND LOWER(size) = LOWER(?)"
            params.append(size)
        else:
            query += " AND size IS NULL"

        if color:
            query += " AND LOWER(color) = LOWER(?)"
            params.append(color)
        else:
            query += " AND color IS NULL"

        cursor.execute(query, params)
        row = cursor.fetchone()
        connection.close()
        return dict(row) if row else None

    def find_possible_matches(self, item_name, size=None, color=None):
        """Finds same-name items where size/color partially match or
        are missing on the existing record — candidates for 'is this
        the same item?' clarification. Excludes exact matches."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM inventory WHERE LOWER(item_name) = LOWER(?)",
            (item_name,)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        connection.close()

        candidates = []
        for row in rows:
            size_compatible = (
                row["size"] is None or size is None or
                row["size"].lower() == (size or "").lower()
            )
            color_compatible = (
                row["color"] is None or color is None or
                row["color"].lower() == (color or "").lower()
            )
            is_exact = (
                (row["size"] or "").lower() == (size or "").lower() and
                (row["color"] or "").lower() == (color or "").lower()
            )
            if size_compatible and color_compatible and not is_exact:
                candidates.append(row)

        return candidates

    def add_or_update_item(self, item_name=None, category=None, size=None,
                            color=None, cost_price=None, selling_price=None,
                            quantity_in_stock=None, low_stock_threshold=None,
                            confirmed_item_id=None):
        """Creates a new inventory item, or updates an existing one.

        If confirmed_item_id is given, updates that exact row directly —
        item_name is not required in this path. Otherwise, item_name is
        required and used to find/create the item by exact match."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        if confirmed_item_id:
            row = cursor.execute(
                "SELECT * FROM inventory WHERE item_id = ?", (confirmed_item_id,)
            ).fetchone()
            existing = dict(row) if row else None
            if not existing:
                connection.close()
                return {
                    "success": False,
                    "message": f"No item found with id {confirmed_item_id}."
                }
        else:
            if not item_name:
                connection.close()
                return {
                    "success": False,
                    "message": "item_name is required when confirmed_item_id is not provided."
                }
            existing = self.find_item(item_name, size, color)

            if not existing:
                candidates = self.find_possible_matches(item_name, size, color)
                if candidates:
                    connection.close()
                    return {
                        "success": False,
                        "needs_clarification": True,
                        "possible_matches": candidates,
                        "message": f"No exact match for '{item_name}' with the "
                                    f"given size/color, but found similar "
                                    f"existing item(s). Ask the owner to confirm "
                                    f"whether this is the same item before "
                                    f"creating a new one."
                    }

        if existing:
            updates = {}
            if size is not None: updates["size"] = size
            if color is not None: updates["color"] = color
            if category is not None: updates["category"] = category
            if cost_price is not None: updates["cost_price"] = cost_price
            if selling_price is not None: updates["selling_price"] = selling_price
            if quantity_in_stock is not None: updates["quantity_in_stock"] = quantity_in_stock
            if low_stock_threshold is not None: updates["low_stock_threshold"] = low_stock_threshold

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                values = list(updates.values()) + [existing["item_id"]]
                cursor.execute(f"UPDATE inventory SET {set_clause} WHERE item_id = ?", values)
                connection.commit()

            item_id = existing["item_id"]
            action = "updated"
        else:
            cursor.execute(
                """
                INSERT INTO inventory
                (item_name, category, size, color, cost_price, selling_price,
                 quantity_in_stock, low_stock_threshold, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_name, category, size, color,
                 cost_price or 0, selling_price or 0,
                 quantity_in_stock or 0, low_stock_threshold or 3,
                 now_wat_str())
            )
            connection.commit()
            item_id = cursor.lastrowid
            action = "created"

        connection.close()
        return {"success": True, "item_id": item_id, "action": action}

    def check_inventory(self, item_name=None, low_stock_only=False):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        query = "SELECT * FROM inventory WHERE 1=1"
        params = []

        if item_name:
            query += " AND LOWER(item_name) LIKE LOWER(?)"
            params.append(f"%{item_name}%")

        if low_stock_only:
            query += " AND quantity_in_stock <= low_stock_threshold"

        query += " ORDER BY item_name"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    # ---------------- SALES ----------------

    def log_sale(self, item_name, quantity_sold, sale_price, size=None,
                 color=None, customer_name=None, payment_method=None,
                 confirmed_item_id=None):
        if confirmed_item_id:
            connection = self.get_connection()
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT * FROM inventory WHERE item_id = ?", (confirmed_item_id,)
            ).fetchone()
            connection.close()
            item = dict(row) if row else None
        else:
            item = self.find_item(item_name, size, color)

        if not item:
            if not confirmed_item_id:
                possible_matches = self.find_possible_matches(item_name, size, color)
                if possible_matches:
                    return {
                        "success": False,
                        "needs_clarification": True,
                        "possible_matches": possible_matches,
                        "message": f"No exact match for '{item_name}' with the "
                                    f"given size/color, but found similar "
                                    f"existing item(s). Ask the owner to confirm "
                                    f"which one this is before logging the sale."
                    }
            return {
                "success": False,
                "needs_clarification": False,
                "message": f"No inventory item found matching '{item_name}'"
                            f"{f' (size {size})' if size else ''}"
                            f"{f' (color {color})' if color else ''}. "
                            f"Add it to inventory first."
            }

        if item["quantity_in_stock"] < quantity_sold:
            return {
                "success": False,
                "message": f"Only {item['quantity_in_stock']} units of "
                            f"{item['item_name']} in stock — cannot sell {quantity_sold}."
            }

        customer_id = None
        if customer_name:
            customer_id = self.find_or_create_customer(customer_name)

        connection = self.get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO sales (item_id, customer_id, quantity_sold,
                                sale_price, payment_method, sale_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item["item_id"], customer_id, quantity_sold, sale_price,
             payment_method, now_wat_str())
        )

        new_stock = item["quantity_in_stock"] - quantity_sold
        cursor.execute(
            "UPDATE inventory SET quantity_in_stock = ? WHERE item_id = ?",
            (new_stock, item["item_id"])
        )

        connection.commit()
        connection.close()

        low_stock_alert = new_stock <= item["low_stock_threshold"]

        return {
            "success": True,
            "item_name": item["item_name"],
            "size": item["size"],
            "color": item["color"],
            "quantity_sold": quantity_sold,
            "sale_price": sale_price,
            "customer_name": customer_name,
            "remaining_stock": new_stock,
            "low_stock_alert": low_stock_alert,
            "low_stock_threshold": item["low_stock_threshold"],
            "message": "Sale logged successfully."
        }

    def get_sales_summary(self, start_date, end_date):
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS num_sales,
                   COALESCE(SUM(quantity_sold), 0) AS total_units_sold,
                   COALESCE(SUM(sale_price), 0) AS total_revenue
            FROM sales
            WHERE DATE(sale_date) BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )
        totals = dict(cursor.fetchone())

        cursor.execute(
            """
            SELECT i.item_name, SUM(s.quantity_sold) AS units_sold
            FROM sales s
            JOIN inventory i ON s.item_id = i.item_id
            WHERE DATE(s.sale_date) BETWEEN ? AND ?
            GROUP BY i.item_name
            ORDER BY units_sold DESC
            LIMIT 5
            """,
            (start_date, end_date)
        )
        best_sellers = [dict(row) for row in cursor.fetchall()]

        connection.close()

        totals["best_sellers"] = best_sellers
        totals["start_date"] = start_date
        totals["end_date"] = end_date
        return totals

    def get_recent_sales(self, limit=10):
        """Returns the most recent sales with product and customer details."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT s.sale_id, s.quantity_sold, s.sale_price, s.payment_method,
                   s.sale_date, i.item_name, i.size, i.color,
                   c.name as customer_name
            FROM sales s
            JOIN inventory i ON s.item_id = i.item_id
            LEFT JOIN customers c ON s.customer_id = c.customer_id
            ORDER BY s.sale_date DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    # ---------------- EXPENSES ----------------

    def log_expense(self, description, amount, category=None):
        connection = self.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO expenses (description, category, amount, expense_date) VALUES (?, ?, ?, ?)",
            (description, category, amount, now_wat_str())
        )
        connection.commit()
        connection.close()
        return {"success": True, "message": "Expense logged successfully."}

    def get_recent_expenses(self, limit=10):
        """Returns recent expenses."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute("""
            SELECT expense_id, description, category, amount, expense_date
            FROM expenses
            ORDER BY expense_date DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]

    # ---------------- RESTOCKS ----------------

    def log_restock(self, item_name, quantity_added, size=None, color=None,
                     cost_price=None, confirmed_item_id=None):
        if confirmed_item_id:
            connection = self.get_connection()
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT * FROM inventory WHERE item_id = ?", (confirmed_item_id,)
            ).fetchone()
            connection.close()
            item = dict(row) if row else None
        else:
            item = self.find_item(item_name, size, color)

        if not item:
            if not confirmed_item_id:
                possible_matches = self.find_possible_matches(item_name, size, color)
                if possible_matches:
                    return {
                        "success": False,
                        "needs_clarification": True,
                        "possible_matches": possible_matches,
                        "message": f"No exact match for '{item_name}', but found "
                                    f"similar existing item(s). Ask the owner to "
                                    f"confirm which one this is before restocking."
                    }
            return {
                "success": False,
                "message": f"No inventory item found matching '{item_name}'. "
                            f"Use add_or_update_item to create it first."
            }

        connection = self.get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO restocks (item_id, quantity_added, cost_price, restock_date)
            VALUES (?, ?, ?, ?)
            """,
            (item["item_id"], quantity_added, cost_price, now_wat_str())
        )

        new_stock = item["quantity_in_stock"] + quantity_added
        cursor.execute(
            "UPDATE inventory SET quantity_in_stock = ? WHERE item_id = ?",
            (new_stock, item["item_id"])
        )

        connection.commit()
        connection.close()

        return {
            "success": True,
            "item_name": item["item_name"],
            "quantity_added": quantity_added,
            "new_stock_level": new_stock,
            "message": "Restock logged successfully."
        }

    def get_recent_restocks(self, limit=10):
        """Returns recent restocks with item names."""
        connection = self.get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute("""
            SELECT r.restock_id, r.quantity_added, r.cost_price, r.restock_date,
                   i.item_name, i.size, i.color
            FROM restocks r
            JOIN inventory i ON r.item_id = i.item_id
            ORDER BY r.restock_date DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        connection.close()
        return [dict(row) for row in rows]
