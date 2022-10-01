import displayio
import terminalio
import time
import math

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
UNSET = object()
BACK_SENTINEL = object()


class Action:

    pass


class ActivateAction(Action):

    pass


class IgnoreAction(Action):

    def __init__(self, *, changed: bool) -> None:
        self.changed = changed


class ExitAction(Action):

    def __init__(self, value: Any) -> None:
        self.value = value


class SubMenuAction(Action):

    def __init__(self, menu: "Menu") -> None:
        self.menu = menu


class AbstractMenuItem:
    def __init__(self, text: str, value: Any) -> None:
        self.text = text
        self.value = value
        self.menu: Menu | None = None  # gets set in Menu.__init__

    def process_delta(self, delta: int) -> None:
        raise NotImplementedError

    def value_str(self) -> str | None:
        raise NotImplementedError

    def activate(self) -> Action:
        """Called when the button was pressed on this item.

        A menu item can return different values here:

        - ActivateAction: Item is activatable (and now selected, process_delta
              will be called on rotations)
        - IgnoreAction: Item is not activatable (but might e.g. toggle its value)
        - ExitAction: The given value gets returned from run().
        - SubMenuAction: The sub-menu gets displayed.
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
        for item in items:
            item.menu = self

        self.font = terminalio.FONT
        self.font_width, self.font_height = self.font.get_bounding_box()
        self.lines = min(len(self.items), self.display.HEIGHT // self.font_height)

    def run(self):
        main_group = displayio.Group()
        self.display.display.show(main_group)

        labels = self.get_labels()
        layout = self.paginate(labels)
        main_group.append(layout)

        page_label = self.get_page_label()
        main_group.append(page_label)

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
                    action = item.activate()
                    if isinstance(action, SubMenuAction):
                        sub_ret = action.menu.run()
                        if sub_ret is not BACK_SENTINEL:
                            return sub_ret
                        self.display.display.show(main_group)
                    elif isinstance(action, ExitAction):
                        return action.value
                    elif isinstance(action, ActivateAction):
                        item_active = True
                        self.highlight_label(text_label, False)
                        self.highlight_label(value_label)
                    elif isinstance(action, IgnoreAction):
                        if action.changed:
                            self.refresh_value(value_label, item)
                    else:
                        assert False, action  # unreachable
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
                    page_label.text = self.page_label_str(page_index)

    def highlight_label(self, label: Label | None, active: bool = True) -> None:
        assert label is not None  # annotation only exists to make calling easier
        label.color = BLACK if active else WHITE
        label.background_color = WHITE if active else BLACK

    def refresh_value(self, label: Label | None, item: AbstractMenuItem) -> None:
        if label is None:
            return
        value = item.value_str()
        assert value is not None
        label.text = value

    def create_label(self, text: str, x: int = 0, y: int = 0) -> Label:
        return Label(
            self.font,
            text=text,
            # initial selected item gets handled in run()
            color=WHITE,
            background_color=BLACK,
            x=x,
            y=y,
        )

    def get_labels(self) -> list[tuple[Label, Label | None]]:
        labels = []
        for item in self.items:
            value = item.value_str()
            row_labels = (
                self.create_label(item.text),
                None if value is None else self.create_label(value),
            )
            labels.append(row_labels)

        return labels

    def get_page_label(self) -> Label:
        page_label_str = self.page_label_str(0)
        page_label = self.create_label(
            page_label_str,
            x=self.display.WIDTH - self.font_width * len(page_label_str),
            y=self.display.HEIGHT - self.font_height // 2,
        )
        return page_label

    def page_label_str(self, cur_page_index: int) -> str:
        page_count = math.ceil(len(self.items) / self.lines)
        digits = len(str(page_count))
        return f"[{cur_page_index + 1:{digits}}/{page_count:{digits}}]"

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

    def __init__(self, text: str, value: Any = None) -> None:
        super().__init__(text, value)

    def value_str(self) -> None:
        return None

    def activate(self) -> ExitAction:
        return ExitAction(self.value)

    def __repr__(self) -> str:
        return f"FinalMenuItem({repr(self.text)}, ...)"


class BackMenuItem(FinalMenuItem):
    """Go back from a sub-menu."""

    def __init__(self, text: str = "Back") -> None:
        super().__init__(text, value=BACK_SENTINEL)


class CallbackMenuItem(AbstractMenuItem):
    """A text item which calls a given callback (the value) if activated.

    The callback gets the menu instance as argument.
    """

    def value_str(self) -> None:
        return None

    def activate(self) -> IgnoreAction:
        assert self.menu is not None
        self.value(self.menu)
        return IgnoreAction(changed=False)


class IntMenuItem(AbstractMenuItem):
    def __init__(
        self,
        text: str,
        default: int = 0,
        minimum: int | None = None,
        maximum: int | None = None,
        suffix: str = "",
    ) -> None:
        super().__init__(text, default)
        if minimum is not None and default < minimum:
            raise ValueError(
                f"Invalid default value {default}, needs to be >= {minimum}"
            )
        if maximum is not None and default > maximum:
            raise ValueError(
                f"Invalid default value {default}, needs to be <= {maximum}"
            )

        self.minimum = minimum
        self.maximum = maximum
        self.suffix = suffix

    def activate(self) -> ActivateAction:
        return ActivateAction()

    def process_delta(self, delta: int) -> None:
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)

    def value_str(self) -> str:
        return f"{self.value}{self.suffix}"


class TimeMenuItem(AbstractMenuItem):
    def __init__(
        self, text: str, default: int = 0, maximum: int | None = None, step: int = 1
    ):
        super().__init__(text, default)
        self.maximum = maximum
        self.step = step

    def activate(self) -> ActivateAction:
        return ActivateAction()

    def process_delta(self, delta: int) -> None:
        self.value = utils.clamp(
            self.value + delta * self.step, lower=0, upper=self.maximum
        )

    def value_str(self) -> str:
        hours, remainder = divmod(self.value, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")

        if not parts:
            step_suffixes = {
                60: "m",
                3600: "h",
            }
            suffix = step_suffixes.get(self.step, "s")
            return f"0{suffix}"

        return " ".join(parts)


class ToggleMenuItem(AbstractMenuItem):
    def __init__(self, text: str, default: bool = False) -> None:
        super().__init__(text, default)

    def activate(self) -> IgnoreAction:
        self.value = not self.value
        return IgnoreAction(changed=True)

    def value_str(self) -> str:
        return "[x]" if self.value else "[ ]"


class SelectMenuItem(AbstractMenuItem):
    def __init__(
        self,
        text: str,
        values: list[Any],
        default: Any = UNSET,
        *,
        cycle_on_activate: bool = False,
    ) -> None:
        if default is UNSET:
            self.index = 0
            default = values[0]
        else:
            self.index = values.index(default)

        super().__init__(text, default)
        self.values = values
        self.cycle_on_activate = cycle_on_activate

    def activate(self) -> IgnoreAction | ActivateAction:
        if self.cycle_on_activate:
            self.process_delta(1)
            return IgnoreAction(changed=True)
        return ActivateAction()

    def process_delta(self, delta: int) -> None:
        self.index += delta
        self.index %= len(self.values)
        self.value = self.values[self.index]

    def value_str(self) -> str:
        return str(self.value)


class SubMenuItem(AbstractMenuItem):
    def __init__(self, text: str, items: list[AbstractMenuItem]) -> None:
        super().__init__(text, items)

    def activate(self) -> SubMenuAction:
        assert self.menu is not None
        return SubMenuAction(Menu(
            display=self.menu.display, encoder=self.menu.encoder, items=self.value
        ))

    def value_str(self) -> None:
        return None
