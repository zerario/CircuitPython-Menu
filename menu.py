import displayio
import terminalio
import time

try:
    from typing import Any, TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False

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

    def value_str(self) -> str | None:
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

    if TYPE_CHECKING:
        @property
        def text(self) -> str:
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
        text_label, value_label = labels[selected]
        item_active = False
        self.highlight_label(text_label)

        while True:
            if self.encoder.pressed:
                if item_active:
                    item_active = False
                    self.highlight_label(text_label)
                    self.highlight_label(value_label, False)
                else:
                    activated = item.activate()
                    if isinstance(activated, ExitMenu):
                        return activated.value
                    elif activated:
                        item_active = True
                        self.highlight_label(text_label, False)
                        self.highlight_label(value_label)
                    else:
                        # item might have changed
                        self.refresh_value(value_label, item)
                time.sleep(self.DEBOUNCE_TIME)  # FIXME use adafruit lib?

            delta = self.encoder.delta()
            if delta and item_active:
                item.process_delta(delta)
                self.refresh_value(value_label, item)
            elif delta:
                self.highlight_label(text_label, False)

                selected += delta
                selected %= len(labels)
                item = self.items[selected]
                text_label, value_label = labels[selected]

                self.highlight_label(text_label, True)

                page_index = selected // self.lines
                if page_index != layout.showing_page_index:
                    layout.show_page(page_index=page_index)

    def highlight_label(self, label: Label | None, active: bool = True) -> None:
        assert label is not None  # annotation only exists to make calling easier
        label.color = BLACK if active else WHITE
        label.background_color = WHITE if active else BLACK

    def refresh_value(self, label: Label | None, item: AbstractMenuItem) -> None:
        assert label is not None  # annotation only exists to make calling easier
        value = item.value_str()
        assert value is not None
        label.text = value

    def create_label(self, text: str) -> Label:
        return Label(
            self.font,
            text=text,
            # initial selected item gets handled in run()
            color=WHITE,
            background_color=BLACK,
        )

    def get_labels(self) -> list[tuple[Label, Label | None]]:
        labels = []
        for item in self.items:
            value = item.value_str()
            row_labels = (
                self.create_label(item.text),
                None if value is None else self.create_label(value)
            )
            labels.append(row_labels)

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

    def value_str(self) -> None:
        return None

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

    def value_str(self) -> str:
        return f"{self.value}{self.suffix}"


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

    def value_str(self) -> str:
        return "[x]" if self.value else "[ ]"
