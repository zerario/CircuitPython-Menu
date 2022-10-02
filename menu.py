import displayio
import terminalio
import digitalio
import rotaryio
import time
import math
import fontio

try:
    from typing import Any
except ImportError:
    pass

from adafruit_display_text.label import Label
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
from adafruit_displayio_layout.layouts.page_layout import PageLayout

import utils


BLACK = 0x000000
WHITE = 0xFFFFFF
UNSET = object()
BACK_SENTINEL = object()
UNSERIALIZABLE = object()


class Action:

    pass


class ActivationChangeAction(Action):

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
        self.active = False
        self.selectable = True

        # get set via init_menu()
        self.menu: Menu | None = None
        self.drawable: displayio.Group | None = None

    def init_menu(self, menu: "Menu") -> None:
        """Attach the item to the given menu."""
        self.menu = menu
        self.drawable = self._init_value_drawable()

    def handle_delta(self, delta: int) -> None:
        raise NotImplementedError

    def _init_value_drawable(self) -> displayio.Group | None:
        """Get the drawable for this menu item."""
        raise NotImplementedError

    def update_value(self) -> None:
        """Called when the drawable should be updated after value change."""
        raise NotImplementedError

    def update_value_highlight(self) -> None:
        """Called when the drawable should be updated after selecting/deselecting."""
        raise NotImplementedError

    def handle_press(self) -> Action:
        """Called when the button was pressed on this item.

        A menu item can return different values here:

        - ActivationChangeAction: Item was set to active or inactive.
        - IgnoreAction: Item is not activatable (but might e.g. toggle its value).
        - ExitAction: The given value gets returned from run().
        - SubMenuAction: The sub-menu gets displayed.
        """
        self.active = not self.active
        return ActivationChangeAction()

    def serialize(self) -> Any:
        """Get the data behind this item in a serializable format."""
        return self.value


class TextMenuItem(AbstractMenuItem):

    """Menu item showing as a text label.

    Subclasses can override value_str() to customize the displayed string.
    """

    drawable: Label

    def value_str(self) -> str | None:
        raise NotImplementedError

    def _init_value_drawable(self) -> Label | None:
        text = self.value_str()
        if text is None:
            return None

        assert self.menu is not None
        return Label(self.menu.font, text=text, color=WHITE, background_color=BLACK)

    def update_value(self) -> None:
        if self.drawable is None:
            return
        text = self.value_str()
        assert text is not None
        self.drawable.text = text

    def update_value_highlight(self) -> None:
        if self.drawable is None:
            return
        self.drawable.color = BLACK if self.active else WHITE
        self.drawable.background_color = WHITE if self.active else BLACK


class Menu:

    DEBOUNCE_TIME = 0.25

    def __init__(
        self,
        items: list[AbstractMenuItem],
        display: displayio.Display,
        width: int,
        height: int,
        encoder: rotaryio.IncrementalEncoder,
        button: digitalio.DigitalInOut,
        button_pressed_value=False,
    ) -> None:
        if not items:
            raise ValueError("Empty menus are not allowed")

        self.display = display
        self.width = width
        self.height = height

        self.encoder = encoder
        self.encoder_last_position = self.encoder.position

        self.button = button
        self.button_pressed_value = button_pressed_value

        self.items = items
        self.font = terminalio.FONT
        self.font_width, self.font_height = self.font.get_bounding_box()
        self.lines = min(len(self.items), self.height // self.font_height)

        for item in items:
            item.init_menu(self)
        self.display_group = displayio.Group()
        self.drawables = self.get_drawables()
        self.layout = self.paginate(self.drawables)
        self.display_group.append(self.layout)

        self.page_label = self.get_page_label()
        self.display_group.append(self.page_label)

        self.selected = 0
        while not self.item.selectable:
            # FIXME make sure there is at least one selectable item
            self.selected += 1

        self.highlight_label(True)

    def copy_with_items(self, items: list[AbstractMenuItem]) -> "Menu":
        """Get a new menu based on this one, with the given items."""
        return Menu(
            items,
            display=self.display,
            width=self.width,
            height=self.height,
            encoder=self.encoder,
            button=self.button,
            button_pressed_value=self.button_pressed_value,
        )

    @property
    def item(self) -> AbstractMenuItem:
        return self.items[self.selected]

    def show(self):
        self.display.show(self.display_group)

    def hide(self):
        """Show CircuitPython REPL again."""
        self.display.show(None)  # type: ignore[arg-type]

    def serialize(self) -> dict[str, Any]:
        """Get a dict of all item values in this menu.

        Items which are not serializable will get returned as UNSERIALIZABLE.
        """
        return {item.text: item.serialize() for item in self.items}

    def run(self):
        self.show()

        while True:
            self.handle_rotation()
            if self.button.value != self.button_pressed_value:
                continue

            action = self.item.handle_press()

            if isinstance(action, ExitAction):
                self.hide()
                return action.value
            elif isinstance(action, ActivationChangeAction):
                self.item.update_value_highlight()
                self.highlight_label(not self.item.active)
            elif isinstance(action, IgnoreAction):
                if action.changed:
                    self.item.update_value()
            elif isinstance(action, SubMenuAction):
                # just in case someone decides to use this as deactivation action
                assert not self.item.active
                self.highlight_label(True)

                sub_ret = action.menu.run()
                if sub_ret is not BACK_SENTINEL:
                    # Exit the entire menu from a sub-menu
                    self.hide()
                    return sub_ret

                # We got back from the sub-menu, so we need to redraw.
                self.show()
            else:
                assert False, action  # unreachable

            time.sleep(self.DEBOUNCE_TIME)  # FIXME use adafruit lib?

    def handle_rotation(self):
        delta = self.encoder_last_position - self.encoder.position
        self.encoder_last_position = self.encoder.position

        if delta and self.item.active:
            self.item.handle_delta(delta)
            self.item.update_value()
        elif delta:
            self.highlight_label(False)

            self.selected += delta
            self.selected %= len(self.items)
            while not self.item.selectable:
                self.selected += 1 if delta > 0 else -1
                self.selected %= len(self.items)

            self.highlight_label(True)

            page_index = self.selected // self.lines
            if page_index != self.layout.showing_page_index:
                self.layout.show_page(page_index=page_index)
                self.page_label.text = self.page_label_str(page_index)

    def highlight_label(self, active: bool) -> None:
        text_label, _ = self.drawables[self.selected]
        text_label.color = BLACK if active else WHITE
        text_label.background_color = WHITE if active else BLACK

    def get_drawables(self) -> list[tuple[Label, displayio.Group | None]]:
        drawables = []
        for item in self.items:
            text_label = Label(
                self.font,
                text=item.text,
                color=WHITE if item.selectable else BLACK,
                background_color=BLACK if item.selectable else WHITE,
            )

            drawables.append((text_label, item.drawable))

        return drawables

    def get_page_label(self) -> Label:
        page_label_str = self.page_label_str(0)
        page_label = Label(
            self.font,
            text=page_label_str,
            color=WHITE,
            background_color=BLACK,
            x=self.width - self.font_width * len(page_label_str),
            y=self.height - self.font_height // 2,
        )
        return page_label

    def page_label_str(self, cur_page_index: int) -> str:
        page_count = math.ceil(len(self.items) / self.lines)
        digits = len(str(page_count))
        return f"[{cur_page_index + 1:{digits}}/{page_count:{digits}}]"

    def paginate(
        self, drawables: list[tuple[Label, displayio.Group | None]]
    ) -> PageLayout:
        page_layout = PageLayout(0, 0)

        for page_drawables in utils.chunk(drawables, self.lines):
            layout = GridLayout(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                grid_size=(2, self.lines),
            )
            page_layout.add_content(layout)
            for y, (text_label, value_drawable) in enumerate(page_drawables):
                if value_drawable is None:
                    text_span = 2
                else:
                    text_span = 1
                    layout.add_content(
                        value_drawable,
                        grid_position=(1, y),
                        cell_size=(1, 1),
                    )

                layout.add_content(
                    text_label,
                    grid_position=(0, y),
                    cell_size=(text_span, 1),
                )

        return page_layout


class NoValueMenuItem(AbstractMenuItem):

    """Base class for menu items with no user-visible value."""

    def _init_value_drawable(self) -> None:
        return None

    def serialize(self) -> Any:
        return UNSERIALIZABLE


class FinalMenuItem(NoValueMenuItem):
    """A text item which quits the menu when selected.

    The menu's run() method will return the given value.

    Useful to build menus where a single selection gets taken too.
    """

    def __init__(self, text: str, value: Any = None) -> None:
        super().__init__(text, value)

    def handle_press(self) -> ExitAction:
        return ExitAction(self.value)


class BackMenuItem(FinalMenuItem):
    """Go back from a sub-menu."""

    def __init__(self, text: str = "Back") -> None:
        super().__init__(text, value=BACK_SENTINEL)


class CallbackMenuItem(NoValueMenuItem):
    """A text item which calls a given callback (the value) if pressed.

    The callback gets the menu instance as argument.
    """

    def handle_press(self) -> IgnoreAction:
        assert self.menu is not None
        self.value(self.menu)
        return IgnoreAction(changed=False)


class IntMenuItem(TextMenuItem):
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

    def handle_delta(self, delta: int) -> None:
        self.value = utils.clamp(self.value + delta, self.minimum, self.maximum)

    def value_str(self) -> str:
        return f"{self.value}{self.suffix}"


class PercentageMenuItem(IntMenuItem):

    def __init__(self, text: str, default: int = 0) -> None:
        super().__init__(text=text, default=default, minimum=0, maximum=100, suffix="%")


class TimeMenuItem(TextMenuItem):
    # FIXME improve typing for floats
    def __init__(
        self,
        text: str,
        default: int | float = 0,
        maximum: int | float | None = None,
        step: int | float = 1,
    ):
        super().__init__(text, default)
        self.maximum = maximum
        self.step = step

    def handle_delta(self, delta: int) -> None:
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


class ToggleMenuItem(TextMenuItem):
    def __init__(self, text: str, default: bool = False) -> None:
        super().__init__(text, default)

    def handle_press(self) -> IgnoreAction:
        self.value = not self.value
        return IgnoreAction(changed=True)

    def value_str(self) -> str:
        return "[x]" if self.value else "[ ]"


class SelectMenuItem(TextMenuItem):
    def __init__(
        self,
        text: str,
        values: list[Any],
        default: Any = UNSET,
        *,
        cycle_on_press: bool = False,
    ) -> None:
        if default is UNSET:
            self.index = 0
            default = values[0]
        else:
            self.index = values.index(default)

        super().__init__(text, default)
        self.values = values
        self.cycle_on_press = cycle_on_press

    def handle_press(self) -> IgnoreAction | ActivationChangeAction:
        if self.cycle_on_press:
            self.handle_delta(1)
            return IgnoreAction(changed=True)
        return super().handle_press()

    def handle_delta(self, delta: int) -> None:
        self.index += delta
        self.index %= len(self.values)
        self.value = self.values[self.index]

    def value_str(self) -> str:
        return str(self.value)


class SubMenuItem(NoValueMenuItem):

    def init_menu(self, menu: "Menu", *, add_back: bool = True) -> None:
        super().init_menu(menu)
        if add_back:
            self.value.append(BackMenuItem())
        self.submenu = menu.copy_with_items(self.value)

    def handle_press(self) -> SubMenuAction:
        return SubMenuAction(self.submenu)

    def serialize(self) -> Any:
        return self.submenu.serialize()


class TitleMenuItem(NoValueMenuItem):
    def __init__(self, text: str) -> None:
        super().__init__(text, value=None)
        self.selectable = False
