import json
import os

class Storage:
    """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Handles persistence (saving/loading) of Inventory and optional order history.

    Prototype behavior:
    - May be unused initially (in-memory only).

    Future behavior:
    - Save Inventory to JSON (simple) or SQLite (more robust).
    - Load Inventory at startup so manager changes persist across reboots.
    - Optionally record completed orders for refund functionality.

    Notes:
    - Keep file/database details inside this class so other modules stay clean.
    """

    def __init__(self, filename: str = "inventory.json"):
        # This saves in the current working directory (same folder I run main.py from)
        self.filename = filename

    def load_items(self) -> dict:
        """
        Load the inventory dict from JSON.
        Returns {} if the file does not exist.
        """
        if not os.path.exists(self.filename):
            return {}

        with open(self.filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure it’s a dict
        if not isinstance(data, dict):
            return {}

        return data

    def save_items(self, items: dict) -> None:
        """
        Save the inventory dict to JSON.
        """
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, sort_keys=True)