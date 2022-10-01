import displayio
import terminalio
import time

try:
    from typing import Any
except ImportError:
    pass

from adafruit_display_text.label import Label
from adafruit_displayio_layout.layouts.grid_layout import GridLayout

import hardware as hw
import utils


BLACK = 0x000000
WHITE = 0xFFFFFF


class AbstractMenuItem:
    def process_delta(self, delta: int) -> None:
        raise NotImplementedError


class Menu:

    DEBOUNCE_TIME = 0.25

    def __init__(
        self, display: hw.Display, encoder: hw.Encoder, items: list[AbstractMenuItem]
    ) -> None:
        self.display = display
        self.encoder = encoder
        self.items = items
        self.font = terminalio.FONT
        _, font_height = self.font.get_bounding_box()
        self.lines = min(len(self.items), self.display.HEIGHT // font_height)

    def run(self):
        main_group = displayio.Group()
        self.display.display.show(main_group)

        layout, labels = self.render()
        main_group.append(layout)
        selected = 0
        item_active = False

        while True:
            if self.encoder.pressed:
                item = self.items[selected]
                if isinstance(item, FinalMenuItem):
                    return item.value
                else:
                    item_active = not item_active
                    time.sleep(self.DEBOUNCE_TIME)  # FIXME use adafruit lib?

            delta = self.encoder.delta()
            if delta and item_active:
                item = self.items[selected]
                item.process_delta(delta)
                labels[selected].text = str(item)
            elif delta:
                labels[selected].color = WHITE
                labels[selected].background_color = BLACK
                selected = (selected + delta) % self.lines
                labels[selected].color = BLACK
                labels[selected].background_color = WHITE

    def render(self, selected: int = 0) -> tuple[GridLayout, list[Label]]:
        layout = GridLayout(
            x=0,
            y=0,
            width=self.display.WIDTH,
            height=self.display.HEIGHT,
            grid_size=(1, self.lines),
        )
        labels = []

        for i, item in enumerate(self.items):
            label = Label(
                self.font,
                text=str(item),
                color=BLACK if i == selected else WHITE,
                background_color=WHITE if i == selected else BLACK,
            )
            labels.append(label)
            layout.add_content(label, grid_position=(0, i), cell_size=(1, 1))

        return layout, labels


class FinalMenuItem(AbstractMenuItem):
    """A text item which quits the menu when selected.

    The menu's run() method will return the given value.

    Useful to build menus where a single selection gets taken too.
    """

    def __init__(self, text: str, value: Any) -> None:
        self.text = text
        self.value = value

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"FinalMenuItem({repr(self.text)}, ...)"


class IntMenuItem(AbstractMenuItem):
    def __init__(self, text: str, default: int, minimum: int, maximum: int) -> None:
        if not minimum <= default <= maximum:
            raise ValueError(
                f"Invalid default value {default}, needs to be between {minimum} and {maximum}"
            )
        self.text = text
        self.value = default
        self.minimum = minimum
        self.maximum = maximum

    def process_delta(self, delta: int) -> None:
        print(delta)
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)
        print(self.value)

    def __str__(self) -> str:
        return f"{self.text}: {self.value}"
