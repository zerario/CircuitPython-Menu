Introduction
============


.. image:: https://readthedocs.org/projects/circuitpython-menu/badge/?version=latest
    :target: https://circuitpython-menu.readthedocs.io/
    :alt: Documentation Status


.. image:: https://github.com/zerario/CircuitPython_menu/workflows/Build%20CI/badge.svg
    :target: https://github.com/zerario/CircuitPython_menu/actions
    :alt: Build Status


.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code Style: Black

Interactive CircuitPython menu library using RotaryIO and DisplayIO


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.

Installing from PyPI
=====================

.. note:: This library is not available on PyPI yet. Install documentation is included
   as a standard element. Stay tuned for PyPI availability!

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/circuitpython-menu/>`_.
To install for current user:

.. code-block:: shell

    pip3 install circuitpython-menu

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install circuitpython-menu

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .venv
    source .env/bin/activate
    pip3 install circuitpython-menu

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install menu

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Usage Example
=============

.. code-block:: python
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

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://circuitpython-menu.readthedocs.io/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/zerario/CircuitPython_menu/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
