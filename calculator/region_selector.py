import tkinter as tk
from PIL import ImageGrab

class ScreenSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)  # transparency
        self.root.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.root.mainloop()

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline="red", width=2
        )

    def on_move(self, event):
        curr_x = self.canvas.canvasx(event.x)
        curr_y = self.canvas.canvasy(event.y)

        self.canvas.coords(
            self.rect,
            self.start_x, self.start_y,
            curr_x, curr_y
        )

    def on_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        right = max(self.start_x, end_x)
        bottom = max(self.start_y, end_y)

        print("\nSelected region:")
        print(f"({int(left)}, {int(top)}, {int(right)}, {int(bottom)})")

        # Optional: Save the captured region to test
        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        img.save("selected_region.png")
        print("Saved as selected_region.png")

        self.root.destroy()


if __name__ == "__main__":
    ScreenSelector()
