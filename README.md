# Web server that controls a Séguin dobby loom.

The intent is to allow the user to control a loom using any device that has a web client, such as a tablet or phone.

This is preliminary code that only talks to a loom simulator
and I have not yet served this code on PyPY so some of these instructions are aspirational.

## Installing and Running the Web Server

* You need to run the server on a computer that you can connect to the loom.
  A laptop or Raspberry Pi (probably 4 or better) should be fine.
* Install Python 3.11 or later on that computer.
* Install this package on that computer:

    pip install seguin_loom_server

* Connect your computer to the loom with a USB cable.
* Turn on the loom.
* Run the web server:

    run_seguin_loom
  
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
* The direction button just to the right of the pattrn display shows the weaving direction.
  A green down arrow indicates weaving and a red up arrow indicates unweaving.
  Press the button to change the direction (or press the "UNW" button on the loom's control panel).
* To advance the loom simulator to the next shed, use the "Command mock loom" field:
  type "n" followed by carriage return.
  You can also change directions with "d" and toggle the error state of the loom simulator with "e".
* The server will automatically repeat patterns if you weave or unweave beyond the end. See below for details.
* All the controls have help.
  If you have a mouse or trackpad, hover the pointer over a control to see help.
  If you have a touch screen, press and hold on a control until the help appears.

## Automatic Pattern Repeat

If you advance past the end of the pattern, the display returns to pick 0 (no shafts up) and the repeat number is increased.
The fact that no shafts are raised is meant as a warning that you have reached the end.
Continue advancing to weave the next repeat.

Unweaving also requires an extra advance to unweave past the beginning of one repeat and start unweaving the next repeat.

## Remembering Patterns

The web server keeps track of the most recent 25 patterns you have loaded (including the most recent pick number and number of repeats, which are restored when you select a pattern).

However, at present this information is only contained in memory. It will be lost if the server loses power (or if you shut it down). Thus it is safest to write down where you are at the end of a weaving session.

## Road Map

* Add support for talking to a real loom (though I will not be able to properly test this until I can buy a loom).
* Add support for other languages.
* Use a database to store patterns and the current pick.

## Developer Tips

* Run "pre-commit install" before working on this package.
