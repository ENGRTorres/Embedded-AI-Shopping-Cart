class Cart:
  """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Represents the current order (what the customer is buying right now).

    Responsibilities:
    - Track quantities of items by label.
    - Add items when scans are accepted.
    - Remove one item at a time (decrement) and support removing all of an item.
    - Clear the entire cart (void order).
    - Compute totals using Inventory (and optional discounts).

    Notes:
    - Cart does NOT store prices. It stores labels -> quantities.
    - Confirmation behavior for removing the last item should be coordinated
      by the Controller/GUI (Cart can report that qty == 1).
  """

    
  # Initialize an empty cart.
  #  quantities maps item label -> quantity in current order.
  #  Example: {"coke_can": 2, "chips": 1} """
  def __init__(self):
      self.quantities = {}

  def add(self, label: str) -> None:      
    # Add one unit of the given label to the cart.
          if label in self.quantities:
              self.quantities[label] += 1
          else:
              self.quantities[label] = 1

  def get_qty(self, label: str) -> int:      
    # Return the quantity of label in the cart (0 if not present).
      return self.quantities.get(label, 0)

  """
  Attempt to remove one unit of label from the cart.

  Returns a status string:
    - "not_in_cart": label not in cart
    - "decremented": quantity was > 1 and was decremented
    - "needs_confirm_last": quantity is 1 and removal needs confirmation
  """
  def remove_one(self, label: str) -> str:
    if label not in self.quantities:
      return "not_in_cart"

    if self.quantities[label] > 1:
      self.quantities[label] -= 1
      return "decremented"

    # quantity is exactly 1
    return "needs_confirm_last"
  
  def contains(self, label: str) -> bool:
    """Return True if label is currently in the cart."""
    return self.get_qty(label) > 0

  """
  Remove the label completely from the cart.

  Returns True if the label existed and was removed, otherwise False.
  """
  def remove_all(self, label: str) -> bool:
    if label in self.quantities:
      del self.quantities[label]
      return True
      
    return False

  """
  Remove all items from the cart (void the current order).
  """
  def clear(self) -> None:
    self.quantities.clear()