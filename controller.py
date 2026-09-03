from inventory import Inventory
from cart import Cart

class Controller:
    """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Application brain that connects Scanner -> Inventory -> Cart -> GUI.

    Responsibilities:
    - Handle scan events:
        - Verify item is authorized/enabled in Inventory
        - Apply confidence/stability gating (will implement after parts come in)
        - Add accepted items to Cart
        - Trigger feedback (sound/visual/hardware)
    - Handle UI actions:
        - Decrement item quantity (with confirm if last one)
        - Void item / void order
        - Soft reset
    - Handle manager mode actions:
        - Add new item
        - Change price
        - Apply discounts
        - Refund/void workflows (depending on scope)

    Notes:
    - Controller owns the business rules.
    - GUI should be mostly dumb: display state + forward button clicks.
    """
    
    """
    Initialize the controller with the core data models.

    inventory: the authorized catalog (prices + enabled status)
    cart: the current order quantities
    """
    def __init__(self, inventory: Inventory, cart: Cart, storage = None, scanner = None):
        self.inventory = inventory
        self.cart = cart
        self.storage = storage
        self.scanner = scanner
        self.last_status = ""

    """
    Handle a scan event.

    For now:
        - If label is authorized/enabled -> add to cart
        - Otherwise -> reject

    confidence is included now so this method will still work when AI is added.
    """
    def on_scan(self, label: str, confidence: float = 1.0) -> str:
        MIN_CONF = 0.30
        if confidence < MIN_CONF:
            self.last_status = f"Rejected: low confidence ({confidence:.2f})."
            return "rejected_low_conf"
        
        if not self.inventory.is_authorized(label):
            self.last_status = f"Rejected: '{label}' not in authorized inventory."
            return "rejected_not_authorized"

        self.cart.add(label)
        item = self.inventory.get_item(label)
        self.last_status = f"Added: {item['name']} (${item['price_cents']/100:.2f})"
        return "accepted"
    
    def _save_inventory(self) -> None:
        if self.storage:
            self.storage.save_items(self.inventory.authorized_Items)

    """
    Handle decrement request for a specific label.

    Uses Cart.remove_one which returns:
        - "not_in_cart"
        - "decremented"
        - "needs_confirm_last"
    """
    def on_remove_one(self, label: str) -> str:
        status = self.cart.remove_one(label)

        if status == "not_in_cart":
            self.last_status = f"Cannot remove: '{label}' not in cart."
            return "not_in_cart"

        if status == "decremented":
            self.last_status = f"Removed one '{label}'."
            return "decremented"

        # status == "needs_confirm_last"
        self.last_status = f"Confirm removal of last '{label}'."
        return "confirm_remove_last"

    """
    Called after GUI asks: "Remove last one?"

    ok = True  -> remove item completely
    ok = False -> do nothing
    """
    def confirm_remove_last(self, label: str, ok: bool) -> str:
        if not ok:
            self.last_status = "Removal cancelled."
            return "cancelled"

        removed = self.cart.remove_all(label)
        if removed:
            self.last_status = f"Removed last '{label}'."
            return "removed"
        else:
            self.last_status = f"Nothing to remove for '{label}'."
            return "not_in_cart"

    """
        Void the entire order (clear the cart).
    """
    def on_void_order(self) -> None:
        self.cart.clear()
        self.last_status = "Order voided."
        
    def manager_update_price(self, label: str, new_price_cents: int) -> str:
        """
        Manager action: update the price of an item in inventory.

        Returns:
        - "ok" if updated
        - "no_such_item" if label not found
        - "invalid_price" if price is invalid
        """
        # Basic validation first (controller-level sanity checks)
        if not isinstance(new_price_cents, int) or new_price_cents < 0:
            self.last_status = "Manager: invalid price."
            return "invalid_price"

        # Call Inventory to actually update
        updated = self.inventory.update_price(label, new_price_cents)
        if not updated:
            self.last_status = f"Manager: could not update price for '{label}'."
            return "no_such_item"

        item = self.inventory.get_item(label)
        self.last_status = f"Manager: price updated for {item['name']} to ${item['price_cents']/100:.2f}"
        
        self._save_inventory()
        return "ok"
    
    def manager_add_item(self, label: str, name: str, price_cents: int, enabled: bool = False, ai_ready: bool = False) -> str:
        """
        Manager action: add a new item to inventory.

        Returns:
        - "ok"
        - "invalid"
        - "duplicate"
        """
        # Validate price here too (extra safety)
        if not isinstance(price_cents, int) or price_cents < 0:
            self.last_status = "Manager: invalid price."
            return "invalid"

        # Detect duplicate early for a clearer message
        if self.inventory.get_item(label) is not None:
            self.last_status = f"Manager: item '{label}' already exists."
            return "duplicate"

        added = self.inventory.add_item(label, name, price_cents, enabled, ai_ready)
        if not added:
            self.last_status = "Manager: invalid item fields."
            return "invalid"

        item = self.inventory.get_item(label)
        self.last_status = f"Manager: added {item['name']} (${item['price_cents']/100:.2f})"
        
        self._save_inventory()
        
        return "ok"

    """
        Return a GUI-friendly snapshot of the current state.

        Output format example:
        {
          "lines": [
            {"label": "coke_can", "name": "Coke Can", "qty": 2,
             "unit_price_cents": 199, "line_total_cents": 398}
          ],
          "total_cents": 398,
          "status": "Added: Coke Can ($1.99)"
        }
    """
    def get_view_state(self) -> dict:
        lines = []
        total_cents = 0

        for label, qty in self.cart.quantities.items():
            item = self.inventory.get_item(label)
            # Safety: item should exist if it was authorized when added
            if item is None:
                continue

            unit = item["price_cents"]
            line_total = unit * qty
            total_cents += line_total

            lines.append({
                "label": label,
                "name": item["name"],
                "qty": qty,
                "unit_price_cents": unit,
                "line_total_cents": line_total
            })

        return {
            "lines": lines,
            "total_cents": total_cents,
            "status": self.last_status
        }
        
    def manager_set_enabled(self, label: str, enabled: bool) -> str:
        updated = self.inventory.set_enabled(label, enabled)
        if not updated:
            self.last_status = f"Manager: no such item '{label}'."
            return "no_such_item"
        state = "enabled" if enabled else "disabled"
        self.last_status = f"Manager: '{label}' {state}."
        
        self._save_inventory()
        
        return "ok"
    
    def manager_set_ai_ready(self, label: str, ai_ready: bool) -> str:
        updated = self.inventory.set_ai_ready(label, ai_ready)
        if not updated:
            self.last_status = f"Manager: no such item '{label}'."
            return "no_such_item"
        state = "AI-ready" if ai_ready else "pending AI training"
        self.last_status = f"Manager: '{label}' marked {state}."
        
        self._save_inventory()
        
        return "ok"
    
    def manager_delete_item(self, label: str) -> str:
        # Block delete if item currently in cart
        if self.cart.get_qty(label) > 0:
            self.last_status = f"Manager: cannot delete '{label}' because it is in the current cart."
            return "in_cart"

        deleted = self.inventory.delete_item(label)
        if not deleted:
            self.last_status = f"Manager: no such item '{label}'."
            return "no_such_item"

        self.last_status = f"Manager: deleted '{label}'."
        
        self._save_inventory()
        
        return "ok"
    
    def on_scan_input(self, raw_input: str) -> str:
        """
        Manual scan input (typed label) should ALWAYS be treated as a direct label.
        This keeps PC testing + debugging useful even when an AI scanner is active.

        If the user typed nothing, we can optionally fall back to the scanner.
        """
        label = (raw_input or "").strip()

        # If the user typed a label, trust it as a manual override.
        if label:
            return self.on_scan(label, 1.0)

        # If no label typed, optionally try scanner (or just say "empty").
        if self.scanner:
            label, conf = self.scanner.scan("")
            if not label:
                self.last_status = "No item detected."
                return "no_item"
            return self.on_scan(label, conf)

        self.last_status = "No scan label provided."
        return "empty"
    
    def on_scan_now(self) -> str:
        """
        Perform one scanner-based scan (camera/AI) and try to add to cart.
        Returns a status string.
        """
        if not self.scanner:
            self.last_status = "No scanner configured."
            return "no_scanner"

        label, conf = self.scanner.scan("")
        if not label:
            self.last_status = "No item detected."
            return "no_item"

        return self.on_scan(label, conf)
