import tkinter as tk
from tkinter import messagebox, simpledialog

# Used for displaying a live preview frame in Tkinter
# Install: sudo apt install -y python3-pil python3-pil.imagetk
from PIL import Image, ImageTk


class GUI:
    """
    -----------------------------------------------------------------------------
    Author      : Joshua Torres
    Date        : 2/13/26
    Course      : Embedded System Design
    -----------------------------------------------------------------------------
    Description :
    Graphical user interface for the shopping cart.

    Responsibilities:
    - Display current cart contents, per-item pricing, and running total.
    - Provide buttons for common actions (remove one, void order, manager mode).
    - Show status messages (accepted scan, rejected scan, errors).
    - Present confirmation dialogs (e.g., "Remove last one?").

    Notes:
    - GUI should not compute totals or enforce authorization rules.
      It should request actions through the Controller and then re-render state.
    """

    def __init__(self, controller):
        """
        Create the Tkinter window and connect it to the controller.
        """
        self.controller = controller

        # Main window
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.title("VisionCart (Prototype)")

        # -------------------------
        # Scan cooldown state
        # -------------------------
        self.scan_cooldown_ms = 3000
        self.scan_cooldown_after_id = None
        self.scan_now_enabled = True

        # -------------------------
        # Scan input row (typed label)
        # -------------------------
        tk.Label(self.root, text="Scan label:").grid(row=0, column=0, sticky="w", padx=8, pady=6)

        self.scan_entry = tk.Entry(self.root, width=30)
        self.scan_entry.grid(row=0, column=1, padx=8, pady=6)

        # Enter key triggers Scan/Add
        self.scan_entry.bind("<Return>", lambda event: self.on_scan_clicked())
        self.scan_entry.focus_set()

        self.scan_button = tk.Button(self.root, text="Scan/Add", command=self.on_scan_clicked)
        self.scan_button.grid(row=0, column=2, padx=8, pady=6)

        # -------------------------
        # Scan Now / End Scan (AI)
        # -------------------------
        self.scan_now_button = tk.Button(self.root, text="Scan Now (AI)", command=self.on_scan_now_clicked)
        self.scan_now_button.grid(row=0, column=3, padx=8, pady=6)

        self.end_scan_button = tk.Button(self.root, text="End Scan", command=self.on_end_scan_clicked)
        self.end_scan_button.grid(row=0, column=4, padx=8, pady=6)

        # -------------------------
        # Camera preview panel
        # -------------------------
        tk.Label(self.root, text="Camera Preview:").grid(row=1, column=3, columnspan=2, sticky="w", padx=8)

        self.preview_label = tk.Label(self.root)
        self.preview_label.grid(row=2, column=3, columnspan=2, padx=8, pady=6, sticky="n")

        self.ai_result_label = tk.Label(self.root, text="AI: (press Scan Now)", fg="purple")
        self.ai_result_label.grid(row=3, column=3, columnspan=2, padx=8, pady=(0, 6), sticky="w")

        # Keep a reference so Tkinter doesn't garbage collect the image
        self._tk_preview_img = None
        self.preview_running = True

        # -------------------------
        # Cart list
        # -------------------------
        tk.Label(self.root, text="Cart:").grid(row=1, column=0, sticky="w", padx=8)

        self.cart_list = tk.Listbox(self.root, width=60, height=10)
        self.cart_list.grid(row=2, column=0, columnspan=3, padx=8, pady=6, sticky="we")

        # Buttons row
        self.remove_button = tk.Button(self.root, text="Remove One (selected)", command=self.on_remove_one_clicked)
        self.remove_button.grid(row=3, column=0, padx=8, pady=6, sticky="w")

        self.void_button = tk.Button(self.root, text="Void Order", command=self.on_void_clicked)
        self.void_button.grid(row=3, column=1, padx=8, pady=6, sticky="w")

        # Manager button (PIN -> persistent window)
        self.manager_button = tk.Button(self.root, text="Manager", command=self.on_manager_clicked)
        self.manager_button.grid(row=3, column=2, padx=8, pady=6, sticky="e")

        # Total + status
        self.total_label = tk.Label(self.root, text="TOTAL: $0.00", font=("Arial", 12, "bold"))
        self.total_label.grid(row=4, column=0, padx=8, pady=6, sticky="w")

        self.status_label = tk.Label(self.root, text="", fg="blue")
        self.status_label.grid(row=5, column=0, columnspan=5, padx=8, pady=6, sticky="w")

        # Make columns stretch nicely
        self.root.columnconfigure(1, weight=1)

        # Keep this defined even when cart is empty
        self.displayed_labels = []

        # --- Manager window state ---
        self.manager_window = None
        self.manager_search_var = tk.StringVar()
        self.manager_all_labels = []
        self.manager_filtered_labels = []

        # Initial render
        self.refresh()

        # Start preview loop
        self._update_preview()

    def run(self):
        """Start the Tkinter event loop."""
        self.root.mainloop()

    def refresh(self):
        """Refresh the cart list, total, and status from controller state."""
        state = self.controller.get_view_state()

        self.cart_list.delete(0, tk.END)
        self.displayed_labels = []

        for line in state["lines"]:
            name = line["name"]
            qty = line["qty"]
            unit = line["unit_price_cents"] / 100
            line_total = line["line_total_cents"] / 100
            label = line["label"]

            row_text = f"{name}  |  qty: {qty}  |  ${unit:.2f} each  |  line: ${line_total:.2f}"
            self.cart_list.insert(tk.END, row_text)
            self.displayed_labels.append(label)

        total = state["total_cents"] / 100
        self.total_label.config(text=f"TOTAL: ${total:.2f}")

        self.status_label.config(text=state.get("status", ""))

    # -------------------------
    # Live preview update loop
    # -------------------------
    def _update_preview(self):
        """
        Update the camera preview periodically.
        This does NOT run inference.
        """
        scanner = getattr(self.controller, "scanner", None)

        if scanner and hasattr(scanner, "capture_preview_frame"):
            try:
                frame = scanner.capture_preview_frame()

                # Picamera2 often gives (H,W,4) XBGR8888. Drop alpha.
                if frame.ndim == 3 and frame.shape[2] == 4:
                    frame = frame[:, :, :3]

                # Convert to RGB for PIL
                rgb = frame[:, :, ::-1]

                img = Image.fromarray(rgb)
                img = img.resize((320, 240))

                self._tk_preview_img = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self._tk_preview_img)

                # Show last AI result (updated when Scan Now is pressed)
                if hasattr(scanner, "last_label"):
                    if scanner.last_label:
                        self.ai_result_label.config(text=f"AI: {scanner.last_label} ({scanner.last_conf:.2f})")
                    else:
                        self.ai_result_label.config(text="AI: (no item / error / low confidence)")
            except Exception:
                pass
        # Change first parameter (lower = faster fps, more CPU)
        # 1000/N = FPS
        if self.preview_running:
            self.root.after(16, self._update_preview)

    # -------------------------
    # Typed Scan/Add (manual)
    # -------------------------
    def on_scan_clicked(self):
        """Simulated scan by typing a label (useful on PC/testing)."""
        label = self.scan_entry.get().strip()
        if not label:
            return

        self.controller.on_scan_input(label)
        self.scan_entry.delete(0, tk.END)
        self.scan_entry.focus_set()
        self.refresh()

    # -------------------------
    # Scan Now (AI) + cooldown
    # -------------------------
    def on_scan_now_clicked(self):
        """Run one AI scan, then force 3-second delay."""
        if not self.scan_now_enabled:
            return

        self.scan_now_enabled = False
        self.scan_now_button.config(state="disabled")

        self.controller.on_scan_now()
        self.refresh()

        self.scan_cooldown_after_id = self.root.after(self.scan_cooldown_ms, self._end_scan_cooldown)

    def _end_scan_cooldown(self):
        self.scan_cooldown_after_id = None
        self.scan_now_enabled = True
        self.scan_now_button.config(state="normal")

    def on_end_scan_clicked(self):
        """Cancel any pending cooldown and re-enable Scan Now."""
        if self.scan_cooldown_after_id is not None:
            self.root.after_cancel(self.scan_cooldown_after_id)
            self.scan_cooldown_after_id = None

        self.scan_now_enabled = True
        self.scan_now_button.config(state="normal")
        self.status_label.config(text="Scan stopped.")

    # -------------------------
    # Cart actions
    # -------------------------
    def on_remove_one_clicked(self):
        selection = self.cart_list.curselection()
        if not selection:
            self.status_label.config(text="Select an item in the cart first.")
            return

        index = selection[0]
        label = self.displayed_labels[index]

        status = self.controller.on_remove_one(label)

        if status == "confirm_remove_last":
            ok = messagebox.askokcancel("Confirm", "Remove the last one of this item?", parent=self.root)
            self.controller.confirm_remove_last(label, ok)

        self.refresh()

    def on_void_clicked(self):
        ok = messagebox.askokcancel("Confirm", "Void the entire order?", parent=self.root)
        if ok:
            self.controller.on_void_order()
            self.refresh()

    # -----------------------
    # Manager mode
    # -----------------------
    def on_manager_clicked(self):
        """Manager mode: PIN -> open persistent manager window."""
        # If already open, bring to front
        if self.manager_window is not None and self.manager_window.winfo_exists():
            self.manager_window.deiconify()
            self.manager_window.lift()
            self.manager_window.focus_force()
            return

        pin = simpledialog.askstring("Manager", "Enter manager PIN:", show="*", parent=self.root)
        if pin is None:
            return

        if pin != "1234":
            messagebox.showerror("Manager", "Incorrect PIN.", parent=self.root)
            return

        
        self.open_manager_window()

    def open_manager_window(self):
        """Create manager window with search + selectable inventory list + manager actions + add item."""
        self.manager_window = tk.Toplevel(self.root)
        self.manager_window.title("Manager Mode")
        self.manager_window.geometry("620x700")
        self.manager_window.minsize(620, 700)
        self.manager_window.transient(self.root)
        self.manager_window.lift()
        self.manager_window.focus_force()

        # Pull labels from inventory (no free-typing labels)
        self.manager_all_labels = sorted(list(self.controller.inventory.authorized_Items.keys()))
        self.manager_filtered_labels = self.manager_all_labels[:]

        # Search row
        tk.Label(self.manager_window, text="Search:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        search_entry = tk.Entry(self.manager_window, textvariable=self.manager_search_var, width=30)
        search_entry.grid(row=0, column=1, padx=8, pady=6, sticky="we")
        search_entry.focus_set()

        # Live filter on every keystroke
        self.manager_search_var.trace_add("write", lambda *args: self.update_manager_filter())

        # Listbox of labels (filtered)
        tk.Label(self.manager_window, text="Select item label:").grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.manager_listbox = tk.Listbox(self.manager_window, height=10)
        self.manager_listbox.grid(row=2, column=0, columnspan=2, padx=8, pady=6, sticky="nsew")

        self.manager_window.rowconfigure(2, weight=1)
        self.manager_window.columnconfigure(1, weight=1)

        self.update_manager_listbox()

        # Price entry
        tk.Label(self.manager_window, text="New price (cents):").grid(row=3, column=0, padx=8, pady=6, sticky="w")
        self.manager_price_entry = tk.Entry(self.manager_window, width=20)
        self.manager_price_entry.grid(row=3, column=1, padx=8, pady=6, sticky="w")

        # Row 4: Update + Close
        update_btn = tk.Button(self.manager_window, text="Update Price", command=self.on_manager_update_price)
        update_btn.grid(row=4, column=0, padx=8, pady=6, sticky="w")

        close_btn = tk.Button(self.manager_window, text="Close", command=self.manager_window.destroy)
        close_btn.grid(row=4, column=1, padx=8, pady=6, sticky="e")

        # Row 5: Enable/Disable
        enable_btn = tk.Button(self.manager_window, text="Enable", command=lambda: self.on_manager_set_enabled(True))
        enable_btn.grid(row=5, column=0, padx=8, pady=4, sticky="w")

        disable_btn = tk.Button(self.manager_window, text="Disable", command=lambda: self.on_manager_set_enabled(False))
        disable_btn.grid(row=5, column=1, padx=8, pady=4, sticky="w")

        # Row 6: AI Ready/Pending
        ready_btn = tk.Button(self.manager_window, text="Mark AI Ready", command=lambda: self.on_manager_set_ai_ready(True))
        ready_btn.grid(row=6, column=0, padx=8, pady=4, sticky="w")

        pending_btn = tk.Button(self.manager_window, text="Mark Pending", command=lambda: self.on_manager_set_ai_ready(False))
        pending_btn.grid(row=6, column=1, padx=8, pady=4, sticky="w")

        # Row 7: Delete
        delete_btn = tk.Button(self.manager_window, text="Delete Item", command=self.on_manager_delete_item)
        delete_btn.grid(row=7, column=0, padx=8, pady=6, sticky="w")

        # Optional: double-click a label to prefill current price
        self.manager_listbox.bind("<Double-Button-1>", lambda event: self.prefill_price_from_selection())

        # Row 8: Add Item header
        tk.Label(self.manager_window, text="Add New Item", font=("Arial", 10, "bold")).grid(
            row=8, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w"
        )

        # Row 9: Add Label
        tk.Label(self.manager_window, text="Label:").grid(row=9, column=0, padx=8, pady=4, sticky="w")
        self.add_label_entry = tk.Entry(self.manager_window, width=30)
        self.add_label_entry.grid(row=9, column=1, padx=8, pady=4, sticky="we")

        # Row 10: Add Name
        tk.Label(self.manager_window, text="Name:").grid(row=10, column=0, padx=8, pady=4, sticky="w")
        self.add_name_entry = tk.Entry(self.manager_window, width=30)
        self.add_name_entry.grid(row=10, column=1, padx=8, pady=4, sticky="we")

        # Row 11: Add Price
        tk.Label(self.manager_window, text="Price (cents):").grid(row=11, column=0, padx=8, pady=4, sticky="w")
        self.add_price_entry = tk.Entry(self.manager_window, width=30)
        self.add_price_entry.grid(row=11, column=1, padx=8, pady=4, sticky="w")

        # Row 12: Enabled checkbox
        self.add_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.manager_window, text="Enabled", variable=self.add_enabled_var).grid(
            row=12, column=1, padx=8, pady=4, sticky="w"
        )

        # Row 13: Add button
        add_btn = tk.Button(self.manager_window, text="Add Item", command=self.on_manager_add_item)
        add_btn.grid(row=13, column=0, padx=8, pady=8, sticky="w")

    def update_manager_filter(self):
        """Update filtered labels list based on the search text, then refresh listbox."""
        q = self.manager_search_var.get().strip().lower()
        if not q:
            self.manager_filtered_labels = self.manager_all_labels[:]
        else:
            filtered = []
            for lbl in self.manager_all_labels:
                item = self.controller.inventory.get_item(lbl)
                name = item.get("name", "") if item else ""
                haystack = (lbl + " " + name).lower()
                if q in haystack:
                    filtered.append(lbl)
            self.manager_filtered_labels = filtered

        self.update_manager_listbox()

    def update_manager_listbox(self):
        """Render filtered labels (with status) into the manager listbox."""
        if self.manager_window is None or not self.manager_window.winfo_exists():
            return

        self.manager_listbox.delete(0, tk.END)

        for lbl in self.manager_filtered_labels:
            item = self.controller.inventory.get_item(lbl)

            enabled = item.get("enabled", False) if item else False
            ai_ready = item.get("ai_ready", False) if item else False

            enabled_text = "enabled" if enabled else "DISABLED"
            ai_text = "AI-ready" if ai_ready else "PENDING"

            display = f"{lbl}  |  {enabled_text}  |  {ai_text}"
            self.manager_listbox.insert(tk.END, display)

        if self.manager_filtered_labels:
            self.manager_listbox.selection_set(0)

    def get_selected_manager_label(self):
        sel = self.manager_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx < 0 or idx >= len(self.manager_filtered_labels):
            return None
        return self.manager_filtered_labels[idx]

    def prefill_price_from_selection(self):
        label = self.get_selected_manager_label()
        if label is None:
            return
        item = self.controller.inventory.get_item(label)
        if item is None:
            return
        self.manager_price_entry.delete(0, tk.END)
        self.manager_price_entry.insert(0, str(item["price_cents"]))

    def on_manager_add_item(self):
        label = self.add_label_entry.get().strip()
        name = self.add_name_entry.get().strip()
        price_str = self.add_price_entry.get().strip()
        enabled = self.add_enabled_var.get()

        if not label or not name:
            messagebox.showerror("Manager", "Label and name are required.", parent=self.manager_window)
            return

        try:
            price_cents = int(price_str)
        except ValueError:
            messagebox.showerror("Manager", "Price must be an integer number of cents.", parent=self.manager_window)
            return

        result = self.controller.manager_add_item(label, name, price_cents, enabled)

        if result == "duplicate":
            messagebox.showerror("Manager", f"Item '{label}' already exists.", parent=self.manager_window)
            return
        if result != "ok":
            messagebox.showerror("Manager", "Invalid item fields.", parent=self.manager_window)
            return

        messagebox.showinfo("Manager", "Item added.", parent=self.manager_window)

        self.add_label_entry.delete(0, tk.END)
        self.add_name_entry.delete(0, tk.END)
        self.add_price_entry.delete(0, tk.END)
        self.add_enabled_var.set(True)

        self.manager_all_labels = sorted(list(self.controller.inventory.authorized_Items.keys()))
        self.update_manager_filter()
        self.refresh()

    def on_manager_update_price(self):
        label = self.get_selected_manager_label()
        if label is None:
            messagebox.showerror("Manager", "Select an item label first.", parent=self.manager_window)
            return

        price_str = self.manager_price_entry.get().strip()
        try:
            new_price_cents = int(price_str)
        except ValueError:
            messagebox.showerror("Manager", "Price must be an integer number of cents.", parent=self.manager_window)
            return

        result = self.controller.manager_update_price(label, new_price_cents)
        if result != "ok":
            messagebox.showerror("Manager", f"Could not update price for '{label}'.", parent=self.manager_window)
        else:
            messagebox.showinfo("Manager", "Price updated.", parent=self.manager_window)

        self.refresh()

    def on_manager_set_enabled(self, enabled: bool):
        label = self.get_selected_manager_label()
        if label is None:
            messagebox.showerror("Manager", "Select an item first.", parent=self.manager_window)
            return

        self.controller.manager_set_enabled(label, enabled)
        self.manager_all_labels = sorted(list(self.controller.inventory.authorized_Items.keys()))
        self.update_manager_filter()
        self.refresh()

    def on_manager_set_ai_ready(self, ai_ready: bool):
        label = self.get_selected_manager_label()
        if label is None:
            messagebox.showerror("Manager", "Select an item first.", parent=self.manager_window)
            return

        self.controller.manager_set_ai_ready(label, ai_ready)
        self.manager_all_labels = sorted(list(self.controller.inventory.authorized_Items.keys()))
        self.update_manager_filter()
        self.refresh()

    def on_manager_delete_item(self):
        label = self.get_selected_manager_label()
        if label is None:
            messagebox.showerror("Manager", "Select an item first.", parent=self.manager_window)
            return

        ok = messagebox.askokcancel("Confirm Delete", f"Delete '{label}' from inventory?", parent=self.manager_window)
        if not ok:
            return

        result = self.controller.manager_delete_item(label)
        if result == "in_cart":
            messagebox.showerror("Manager", "Cannot delete: item is in the current cart.", parent=self.manager_window)
            return
        if result != "ok":
            messagebox.showerror("Manager", "Delete failed.", parent=self.manager_window)
            return

        self.manager_all_labels = sorted(list(self.controller.inventory.authorized_Items.keys()))
        self.update_manager_filter()
        self.refresh()