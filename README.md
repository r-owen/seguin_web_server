# Web server that controls a Séguin dobby loom.

This server is intended to allow you to control your loom from any phone, tablet or other device that has wifi and a web browser.

This server must run on a computer that is connected (via a USB cable) to your loom.
This code has only been tested on macOS but should also work on any flavor of linux, and may also run on Windows.

Warning: this software has not yet been tested on a real loom.
I will do that once I have access to a loom (I am trying to order one now).

## Installing and Running the Web Server

* You need to run the server on a computer that you can connect to the loom.
  A macOS laptop or Raspberry Pi (probably 4 or better) should be fine.
  A Windows computer may also work.
* Install Python 3.11 or later on that computer.
* Install this package on that computer:

    pip install seguin_loom_server

* You will need to determine the name of the port that your computer is using to connect to the loom.
  To do this on macOS or linux:

  * Run the command `ls /dev/tty.usb*` to see USB ports already in use.
  * Connect your computer to the loom with a USB cable
  * Turn on the loom and wait a bit to let it connect.
  * Run the command `ls /dev/tty.usb*` again. There should be one new entry, which is the name you are looking for.

* Run the web server:

    run_seguin_loom *port_name*
  
* You may stop the web server by typing ctrl-C (possibly twice). Your uploaded patterns will be lost.

## Running the Loom

* Connect to the web server with any modern web browser. In the resulting window:
* Upload one or more weaving pattern files (.wif or .dtx files).
  You can push the "Upload Patterns" button or drop the files onto the web page
  (basically anywhere on the page, but make sure the page is gray before you drop the files).
* Select the desired pattern using the "Pattern" menu.
  You can switch patterns at any time, and the server remembers where you left off for each of them.
  This allows you to load several treadlings for one threading (each as a separate pattern file) and switch between them at will.

You are now ready to weave.

* The pattern display shows woven fabric below and potential future fabric above.
  (This is the opposite of the usual US drawdown).
* There are two buttons to the right of the pattern display:

    * The upper button shows the current pick color (blank if pick 0).
      Press it to advance to the next pick. 
      You may also press the loom's pedal (which is usually more convenient) or the "PICK"" button on the loom's control panel.
  
    * The lower button shows whether you are weaving (green down arrow) or unweaving (red up arrow).
      The arrow points in the direction cloth is moving through the loom.
      Press this button to change the direction.
      You may also press the "UNW" button on the loom's control panel.

* To jump to a different pick and/or repeat:

    * Enter the desired value in the pick and repeat boxes.
      The boxes will turn pink and the Jump and Reset buttons will be enabled.
    * Press the "Jump" button (or type carriage return) to jump.
      Note: if a box is empty when you press "Jump", it will not change that value.
    * Press the "Reset" button to reset the displayed values.
    * Advancing to the next pick or choosing a new pattern will also reset the displayed values.

* The server will automatically repeat patterns if you weave or unweave beyond the end. See below for details.
* All the controls have help, though it is only visible if you have a pointer (not on a phone or other touchscreen-only device).
  Hover over the control to see the help.

## Automatic Pattern Repeat

If you advance past the end of the pattern, the display returns to pick 0 (no shafts up) and the repeat number is increased.
The fact that no shafts are raised is meant as a warning that you have reached the end.
Continue advancing to weave the next repeat.

Unweaving also requires an extra advance, to unweave past the beginning of one repeat and start unweaving the next repeat.

## Remembering Patterns

The web server keeps track of the most recent 25 patterns you have loaded (including the most recent pick number and number of repeats, which are restored when you select a pattern).

However, at present this information is only contained in memory. It will be lost if the server loses power (or if you shut it down). Thus it is safest to write down where you are at the end of a weaving session.

## Road Map

* Test this software on a real loom.
* Make the design look better on a phone.
* Add support for other languages.
* Use a database to store patterns and the current pick.

## Developer Tips

* Download the source code from [github](https://github.com/r-owen/seguin_loom_server.git), or make a fork and download that.
* Inside the directory, issue the following commands:

    * `pip install -e .` to install an editable version of the package.
    * `pre-commit install` to activate the pre-commit hooks.

* You may run a mock loom by starting the server with: `run_seguin_loom mock`
* The web page will show a few extra controls for debugging.
