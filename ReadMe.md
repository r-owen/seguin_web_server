# Web server that controls a Séguin dobby loom.

The intent is to allow the user to control a loom using any device that has a web client, such as a tablet or phone.

This is preliminary code that only talks to a loom simulator.
I'm still thinking about how to handle the serial communication with asyncio
(use a 3rd party library or roll my own based on pyserial).

## Instructions

* Start the web server:

    fastapi

* Connect to the web server with any modern web browser.
  The following instructions all refer to the resulting web page.
* Upload one or more weaving pattern files (.wif or .dtx files).
  You can push the "Upload Patterns" button or drop the files onto the web page
  (basically anywhere on the page, but make sure the page is gray before you drop the files).
* Select the desired pattern using the "Pattern" menu.
  You are now ready to weave.
* The pattern display window shows woven fabric below and potential future fabric above.
  The direction button just to the right shows the weaving direction: a green down arrow indicates weaving and a red up arrow indicates unweaving. Press the button to change the direction.
* To advance to the next shed type "n" followed by carriage return in the "Command mock loom" box.
  (You can also change directions with "d" and toggle the error state of the loom simulator with "e".)
* The server will automatically repeat patterns if you weave or unweave beyond the end. See below for details.
* All the controls have help. Hover the mouse over a control to see it, or on a touch screen press and hold on a control.

## Automatic Pattern Repeat

If you advance past the end of the pattern, the display returns to pick 0 (no shafts up) and the repeat number is increased. The fact that no shafts are raised is meant to be a signal to you that you have reached the end. Continue advancing to weave the next repeat.

Unweaving works much the same way (an extra advance is needed to unweave past the beginning of one repeat and start unweaving the next repeat), but you cannot unweave past pick 0 of repeat 0.

## Remembering Patterns

The web server keeps track of the most recent 25 patterns you have loaded. The most recent pick number and number of repeats are shown when you select a pattern.

However, at present this information is only contained in memory. Thus it will be lost if the server loses power or is shut down. Thus it is safest to write down where you are at the end of a weaving session.

## Road Map

* Add distribution files so the package can be served on PyPI.
* Add support for talking to a real loom.
  This will take some time as I don't own a loom yet (I have a request in to buy one).
* Add support for other languages.
* Use a database to store patterns and the current pick.
