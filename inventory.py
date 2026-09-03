class Inventory:
    """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Stores the authorized catalog of items that can be scanned/added to the cart. A nested 
    dictionary will be used for fast item lookup.

    Responsibilities:
    - Maintain item data (label, display name, price, enabled/authorized).
    - Provide fast lookup by label for scan events.
    - Support manager operations (add item, change price, enable/disable item).

    Notes:
    - Inventory is the single source of truth for pricing.
      The Cart stores only quantities; totals are computed using Inventory prices.

    Typical keys per item (minimum):
    - label (str): unique identifier used by the scanner/AI, e.g. "coke_can"
    - name (str): display name for GUI
    - price_cents (int): price stored in cents to avoid float rounding issues
    - enabled (bool): whether the item is authorized/active
    """
    
    # def __init__(self):
    #     self.authorized_Items = {
    #         "coke_can": {"name": "Coke Can", "price_cents": 199, "enabled": True, "ai_ready": True},
    #         "polar_seltzer": {"name": "Polar Seltzer", "price_cents": 199, "enabled": True, "ai_ready": True},
    #         "boston_tea_party_tea": {"name": "Boston Tea Party Commemorative Earl Grey", "price_cents": 500, "enabled": True, "ai_ready": True}
    #     }
    
    def __init__(self, items: dict = None):
        default_items = {
            "coke_can": {"name": "Coke Can", "price_cents": 199, "enabled": True, "ai_ready": True},
            "polar_seltzer": {"name": "Polar Seltzer", "price_cents": 199, "enabled": True, "ai_ready": True},
            "boston_tea_party_tea_earl": {"name": "Boston Tea Party Commemorative Earl Grey", "price_cents": 500, "enabled": True, "ai_ready": True}
        }

        # If items were loaded from JSON, use them; otherwise use defaults
        self.authorized_Items = items if isinstance(items, dict) and items else default_items
    
    def is_authorized(self, label: str) -> bool:
        # Authorized means: exists AND enabled AND AI-ready
        return (
            label in self.authorized_Items
            and self.authorized_Items[label].get("enabled", False)
            and self.authorized_Items[label].get("ai_ready", False)
        )
    
    def get_item(self, label: str):
        # Return the item dict for a label, or None if label is not found
        return self.authorized_Items.get(label)
    
    # Update the price (in cents) for an existing authorized item.
    # Returns True if update succeeded, otherwise False.
    def update_price(self, label: str, new_price_cents: int) -> bool:
        # label must exist
        if label not in self.authorized_Items:
            return False

        # basic validation
        if not isinstance(new_price_cents, int):
            return False
        if new_price_cents < 0:
            return False

        self.authorized_Items[label]["price_cents"] = new_price_cents
        return True
    
    def add_item(self, label: str, name: str, price_cents: int, enabled: bool = False, ai_ready: bool = False) -> bool:
        """
        Add a new authorized item to the inventory.

        Returns True if added, False if invalid or label already exists.
        """
        if not isinstance(label, str) or not label.strip():
            return False
        if not isinstance(name, str) or not name.strip():
            return False
        if not isinstance(price_cents, int) or price_cents < 0:
            return False

        label = label.strip()
        name = name.strip()

        # Simple label rule: no spaces (encourage snake_case)
        if " " in label:
            return False

        # Prevent duplicates
        if label in self.authorized_Items:
            return False

        self.authorized_Items[label] = {
        "name": name,
        "price_cents": price_cents,
        "enabled": bool(enabled),
        "ai_ready": bool(ai_ready)
        
        }
        return True
    
    def set_enabled(self, label: str, enabled: bool) -> bool:
        """Enable/disable an item (stop selling it without deleting)."""
        if label not in self.authorized_Items:
            return False
        self.authorized_Items[label]["enabled"] = bool(enabled)
        return True

    def set_ai_ready(self, label: str, ai_ready: bool) -> bool:
        """Mark item as AI-ready (model trained/deployed) or pending."""
        if label not in self.authorized_Items:
            return False
        self.authorized_Items[label]["ai_ready"] = bool(ai_ready)
        return True

    def delete_item(self, label: str) -> bool:
        """
        Permanently delete an item from inventory.
        Returns True if deleted, False if label not found.
        """
        if label not in self.authorized_Items:
            return False
        del self.authorized_Items[label]
        return True