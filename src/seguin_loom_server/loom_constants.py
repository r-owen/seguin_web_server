__all__ = ["BAUD_RATE", "TERMINATOR_STR", "TERMINATOR_BYTES"]

# terminator str for commands and replies
TERMINATOR_STR = "\r"
TERMINATOR_BYTES = TERMINATOR_STR.encode()

# baud rate of loom's FTDI serial port
BAUD_RATE = 9600
