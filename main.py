from inventory import Inventory
from cart import Cart
from controller import Controller
from gui import GUI
from storage import Storage
from scanner import FakeScanner, EdgeImpulseCppScanner

"""
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Entry point for the Inventory Kiosk application.

    Creates and connects:
    - Inventory (catalog)
    - Cart (current order)
    - Scanner (simulated now, AI later)
    - Controller (business logic)
    - GUI (display + input)
    
    Commands:
    - scan <label>
    - remove <label>
    - confirm <label> yes/no
    - void
    - show
    - quit

    Starts the GUI event loop.
"""
    
    
def print_state(state: dict) -> None:
    """Pretty-print the controller view state."""
    print("\n=== CART ===")
    if not state["lines"]:
        print("(empty)")
    else:
        for line in state["lines"]:
            name = line["name"]
            qty = line["qty"]
            unit = line["unit_price_cents"] / 100
            line_total = line["line_total_cents"] / 100
            print(f"- {name} x{qty} @ ${unit:.2f} = ${line_total:.2f}")

    total = state["total_cents"] / 100
    print(f"TOTAL: ${total:.2f}")

    if state["status"]:
        print(f"STATUS: {state['status']}")
    print("============\n")

def main():
    storage = Storage("inventory.json")
    loaded_items = storage.load_items()
    inventory = Inventory(loaded_items)

    USE_AI = True  # set False on Windows

    labels = [
        "background",
        "boston_tea_party_tea_earl",
        "polar_seltzer_lime",
        "polar_seltzer_rasp_lime",
    ]

    if USE_AI:
        scanner = EdgeImpulseCppScanner(
        model_path="/home/josh-torres/Desktop/Inventory/model.tflite",
        runner_path="/home/josh-torres/Desktop/Inventory/tflite_infer"
    )
    else:
        scanner = FakeScanner()

    
    cart = Cart()
    controller = Controller(inventory, cart, storage, scanner)

    gui = GUI(controller)
    gui.run()
    
    if hasattr(scanner, "close"):
        scanner.close()

    #print("Inventory Kiosk (console test)")
    #print("scan coke_can | remove coke_can | confirm coke_can yes | void | show | quit")

    # while True:
    #     cmd = input("> ").strip()
    #     if not cmd:
    #         continue

    #     parts = cmd.split()
    #     action = parts[0].lower()

    #     if action == "quit":
    #         break

    #     elif action == "scan" and len(parts) == 2:
    #         label = parts[1]
    #         controller.on_scan(label)

    #     elif action == "remove" and len(parts) == 2:
    #         label = parts[1]
    #         status = controller.on_remove_one(label)
    #         if status == "confirm_remove_last":
    #             print("Need confirmation: type confirm <label> yes or confirm <label> no")

    #     elif action == "confirm" and len(parts) == 3:
    #         label = parts[1]
    #         ok = parts[2].lower() == "yes"
    #         controller.confirm_remove_last(label, ok)

    #     elif action == "void":
    #         controller.on_void_order()

    #     elif action == "show":
    #         pass  # just fall through and print state
    #     elif action == "price" and len(parts) == 3:
    #         label = parts[1]
    #         try:
    #             new_price_cents = int(parts[2])
    #         except ValueError:
    #             print("Price must be an integer number of cents (example: 250).")
    #         else:
    #             controller.manager_update_price(label, new_price_cents)

    #     else:
    #         print("Unknown command. Use: scan/remove/confirm/void/show/quit")

    #     state = controller.get_view_state()
    #     print_state(state)

if __name__ == "__main__":
    main()