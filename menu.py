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


class ExitMenu:
    def __init__(self, value: Any):
        self.value = value


class AbstractMenuItem:
    def process_delta(self, delta: int) -> None:
        raise NotImplementedError

    def get_texts(self) -> tuple[str, str | None]:
        raise NotImplementedError

    def activate(self) -> bool | ExitMenu:
        """Called when the button was pressed on this item.

        A menu item can return three different values here:

        - True: Item is activatable (and now selected, process_delta will be
          called on rotations)
        - False: Item is not activatable (but might e.g. toggle its value)
        - An instance of ExitMenu: The given value gets returned from run().
        """
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
        item = self.items[selected]
        row_labels = labels[selected]
        item_active = False
        self.highlight_labels(row_labels, True)

        while True:
            if self.encoder.pressed:
                if item_active:
                    item_active = False
                    self.highlight_labels(row_labels, True, False)
                else:
                    activated = item.activate()
                    if isinstance(activated, ExitMenu):
                        return activated.value
                    elif activated:
                        item_active = True
                        self.highlight_labels(row_labels, False, True)
                    else:
                        # item might have changed
                        self.refresh_labels(row_labels, item)
                time.sleep(self.DEBOUNCE_TIME)  # FIXME use adafruit lib?

            delta = self.encoder.delta()
            if delta and item_active:
                item.process_delta(delta)
                self.refresh_labels(row_labels, item)
            elif delta:
                self.highlight_labels(row_labels, False)

                selected += delta
                selected %= len(labels)
                item = self.items[selected]
                row_labels = labels[selected]

                self.highlight_labels(row_labels, True)

                page_index = selected // self.lines
                if page_index != layout.showing_page_index:
                    layout.show_page(page_index=page_index)

    def highlight_labels(
        self,
        labels: tuple[Label, Label | None],
        left_active: bool,
        right_active: bool = False,
    ) -> None:
        labels[0].color = BLACK if left_active else WHITE
        labels[0].background_color = WHITE if left_active else BLACK
        if labels[1] is not None:
            labels[1].color = BLACK if right_active else WHITE
            labels[1].background_color = WHITE if right_active else BLACK

    def refresh_labels(
        self, labels: tuple[Label, Label | None], item: AbstractMenuItem
    ) -> None:
        for x, text in enumerate(item.get_texts()):
            if text is not None:
                label = labels[x]
                assert label is not None
                label.text = text

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

    def activate(self) -> ExitMenu:
        # Exit the menu on activation
        return ExitMenu(self.value)

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

    def activate(self) -> bool:
        return True

    def process_delta(self, delta: int) -> None:
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)

    def get_texts(self) -> tuple[str, str]:
        return self.text, f"{self.value}{self.suffix}"


class SecondsMenuItem(IntMenuItem):
    def __init__(
        self, text: str, default: int = 0, minimum: int = 0, maximum: int | None = None
    ):
        super().__init__(text, default, minimum, maximum, suffix="s")


class ToggleMenuItem(AbstractMenuItem):
    def __init__(self, text: str, default: bool = False) -> None:
        self.text = text
        self.value = default

    def activate(self) -> bool:
        self.value = not self.value
        return False

    def get_texts(self) -> tuple[str, str]:
        return self.text, "[x]" if self.value else "[ ]"
