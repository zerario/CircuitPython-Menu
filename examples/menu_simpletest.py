# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2023 Zerario <derg@zerario.dev>
#
# SPDX-License-Identifier: Unlicense

import board
import busio
import displayio
import rotaryio
import digitalio
import adafruit_displayio_sh1107

import menu

displayio.release_displays()

# TODO: Adjust those to your board
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_ROTATION = 0
i2c = busio.I2C(scl=board.IO34, sda=board.IO39)
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C, reset=board.IO21)
display = adafruit_displayio_sh1107.SH1107(
    display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, rotation=DISPLAY_ROTATION
)

enc = rotaryio.IncrementalEncoder(board.IO1, board.IO3, divisor=2)
button = digitalio.DigitalInOut(board.IO2)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP


MENU_ITEMS = [
    menu.TitleMenuItem("==== Demo ==="),
    menu.PercentageMenuItem("Awesome", default=50),
    menu.TimeMenuItem("Duration"),
    menu.IntMenuItem("Threshold", default=42),
    menu.SubMenuItem(
        "Print...",
        [
            menu.CallbackMenuItem("BEEP", lambda menu: print("BEEP!")),
            menu.CallbackMenuItem("BOOP", lambda menu: print("BOOP!")),
        ],
    ),
    menu.FinalMenuItem("Exit"),
]

main_menu = menu.Menu(
    items=MENU_ITEMS,
    display=display,
    width=DISPLAY_WIDTH,
    height=DISPLAY_HEIGHT,
    encoder=enc,
    button=button,
)

main_menu.run()
print(main_menu.serialize())
