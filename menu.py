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

    def get_texts(self) -> tuple[str, str | None]:
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
                time.sleep(self.DEBOUNCE_TIME)  # FIXME use adafruit lib?
                item = self.items[selected]
                if isinstance(item, FinalMenuItem):
                    return item.value
                elif item_active:
                    item_active = False
                    self.highlight_label(labels[selected][1], False)
                    self.highlight_label(labels[selected][0], True)
                elif not item_active:
                    item_active = True
                    self.highlight_label(labels[selected][0], False)
                    self.highlight_label(labels[selected][1], True)

            delta = self.encoder.delta()
            if delta and item_active:
                item = self.items[selected]
                item.process_delta(delta)
                for x, text in enumerate(item.get_texts()):
                    if text is not None:
                        label = labels[selected][x]
                        assert label is not None
                        label.text = text
            elif delta:
                self.highlight_label(labels[selected][0], False)
                selected = (selected + delta) % self.lines
                self.highlight_label(labels[selected][0], True)

    def highlight_label(self, label: Label | None, active: bool) -> None:
        if label is None:
            return
        label.color = BLACK if active else WHITE
        label.background_color = WHITE if active else BLACK

    def render(
        self, selected: tuple[int, int] = (0, 0)
    ) -> tuple[GridLayout, list[tuple[Label, Label | None]]]:
        layout = GridLayout(
            x=0,
            y=0,
            width=self.display.WIDTH,
            height=self.display.HEIGHT,
            grid_size=(2, self.lines),
        )
        labels = []

        for y, item in enumerate(self.items):
            row_labels = []

            for x, text in enumerate(item.get_texts()):
                if text is None:
                    row_labels.append(None)
                    continue

                is_selected = (x, y) == selected
                label = Label(
                    self.font,
                    text=text,
                    color=BLACK if is_selected else WHITE,
                    background_color=WHITE if is_selected else BLACK,
                )
                row_labels.append(label)
                layout.add_content(label, grid_position=(x, y), cell_size=(1, 1))

            labels.append(tuple(row_labels))

        return layout, labels


class FinalMenuItem(AbstractMenuItem):
    """A text item which quits the menu when selected.

    The menu's run() method will return the given value.

    Useful to build menus where a single selection gets taken too.
    """

    def __init__(self, text: str, value: Any) -> None:
        self.text = text
        self.value = value

    def get_texts(self) -> tuple[str, None]:
        return self.text, None

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
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)

    def get_texts(self) -> tuple[str, str]:
        return self.text, str(self.value)
