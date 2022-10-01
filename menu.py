import displayio
import terminalio
import time

try:
    from typing import Any
except ImportError:
    pass

from adafruit_display_text.label import Label
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
from adafruit_displayio_layout.layouts.page_layout import PageLayout

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

        labels = self.get_labels()
        layout = self.paginate(labels)
        main_group.append(layout)
        selected = 0
        item_active = False
        self.highlight_label(labels[0][0], True)

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

                selected += delta
                selected %= len(labels)

                self.highlight_label(labels[selected][0], True)

                page_index = selected // self.lines
                if page_index != layout.showing_page_index:
                    layout.show_page(page_index=page_index)

    def highlight_label(self, label: Label | None, active: bool) -> None:
        if label is None:
            return
        label.color = BLACK if active else WHITE
        label.background_color = WHITE if active else BLACK

    def get_labels(self) -> list[tuple[Label, Label | None]]:
        labels = []
        for item in self.items:
            row_labels = []
            for text in item.get_texts():
                if text is None:
                    row_labels.append(None)
                    continue

                label = Label(
                    self.font,
                    text=text,
                    # initial selected item gets handled in run()
                    color=WHITE,
                    background_color=BLACK,
                )
                row_labels.append(label)

            labels.append(tuple(row_labels))

        return labels

    def paginate(self, labels: list[tuple[Label, Label | None]]) -> PageLayout:
        page_layout = PageLayout(0, 0)

        for page_labels in utils.chunk(labels, self.lines):
            layout = GridLayout(
                x=0,
                y=0,
                width=self.display.WIDTH,
                height=self.display.HEIGHT,
                grid_size=(2, self.lines),
            )
            page_layout.add_content(layout)
            for y, col_labels in enumerate(page_labels):
                for x, label in enumerate(col_labels):
                    if label is not None:
                        layout.add_content(
                            label, grid_position=(x, y), cell_size=(1, 1)
                        )

        return page_layout


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
    def __init__(
        self,
        text: str,
        default: int = 0,
        minimum: int | None = None,
        maximum: int | None = None,
        suffix: str = "",
    ) -> None:
        if minimum is not None and default < minimum:
            raise ValueError(
                f"Invalid default value {default}, needs to be >= {minimum}"
            )
        if maximum is not None and default > maximum:
            raise ValueError(
                f"Invalid default value {default}, needs to be <= {maximum}"
            )

        self.text = text
        self.value = default
        self.minimum = minimum
        self.maximum = maximum
        self.suffix = suffix

    def process_delta(self, delta: int) -> None:
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)

    def get_texts(self) -> tuple[str, str]:
        return self.text, f"{self.value}{self.suffix}"


class SecondsMenuItem(IntMenuItem):
    def __init__(
        self, text: str, default: int = 0, minimum: int = 0, maximum: int | None = None
    ):
        super().__init__(text, default, minimum, maximum, suffix="s")
