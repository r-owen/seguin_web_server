const MaxFiles = 10

// Keys are the possible values of the ConnectionState.state messages
// Values are entries in ConnectionStateEnum
const ConnectionStateTranslationDict = {
    0: "disconnected",
    1: "connected",
    2: "connecting",
    3: "disconnecting",
}

var ConnectionStateEnum = {}
for (let i = 0; i < Object.keys(ConnectionStateTranslationDict).length; ++i) {
    var name = ConnectionStateTranslationDict[i]
    ConnectionStateEnum[name] = name
}
Object.freeze(ConnectionStateEnum)

const numericCollator = new Intl.Collator(undefined, { numeric: true })

/*
A minimal weaving pattern, including display code.

Javascript version of the python class of the same name,
with the same attributes but different methods.

Parameters
----------
datadict : dict object
    Data from a Python ReducedPattern dataclass.
*/
class ReducedPattern {
    constructor(datadict) {
        this.name = datadict.name
        this.color_table = datadict.color_table
        this.warp_colors = datadict.warp_colors
        this.threading = datadict.threading
        this.picks = []
        this.pick_number = datadict.pick_number
        this.repeat_number = datadict.repeat_number
        datadict.picks.forEach((pickdata) => {
            this.picks.push(new Pick(pickdata))
        })
    }

    /*
    Display a portion of weavingPattern on the "canvas" element.

    Center the current pick vertically.
    */
    display() {
        var pickColorElt = document.getElementById("pick_color")
        var shaftsRaisedElt = document.getElementById("shafts_raised")
        if ((this.pick_number > 0) && (this.pick_number < this.picks.length)) {
            const pick = this.picks[this.pick_number]
            pickColorElt.style.backgroundColor = this.color_table[pick.color]
            var shaftsRaisedText = ""
            for (let i = 0; i < pick.are_shafts_up.length; ++i) {
                if (pick.are_shafts_up[i]) {
                    shaftsRaisedText += " " + (i + 1)
                }
            }
            shaftsRaisedElt.textContent = shaftsRaisedText
        } else {
            pickColorElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
            shaftsRaisedElt.textContent = ""
        }
        var canvas = document.getElementById("canvas")
        var ctx = canvas.getContext("2d")
        const numEnds = this.warp_colors.length
        const numPicks = this.picks.length
        const blockSize = Math.min(
            Math.max(Math.round(canvas.width / numEnds), 5),
            Math.max(Math.round(canvas.height / numPicks), 5))
        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockSize))
        const numPicksToShow = Math.min(numPicks, Math.floor(canvas.height / blockSize))
        var startPick = this.pick_number - Math.round(numPicksToShow / 2)
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        for (let pickOffset = 0; pickOffset < numPicksToShow; pickOffset++) {
            const pick = startPick + pickOffset
            if (pick < 0 || pick >= this.picks.length) {
                continue
            }
            if (pick >= this.pick_number) {
                ctx.globalAlpha = 0.5
            } else {
                ctx.globalAlpha = 1.0
            }

            for (let end = 0; end < numEndsToShow; end++) {
                const shaft = this.threading[end]
                const blockColorInd = (this.picks[pick].are_shafts_up[shaft]) ?
                    this.warp_colors[end] : this.picks[pick].color
                ctx.fillStyle = this.color_table[blockColorInd]
                ctx.fillRect(
                    canvas.width - blockSize * (end + 1),
                    canvas.height - blockSize * pickOffset,
                    blockSize,
                    blockSize)
            }
        }
    }
}

/*
Data for a pick
*/
class Pick {
    constructor(datadict) {
        this.color = datadict.color
        this.are_shafts_up = datadict.are_shafts_up
    }
}


/*
Compare the names of two Files, taking numbers into account.

To sort file names in a FileList you must first 
convert the FileList to an Array::

    // myFileList is a FileList (which cannot be sorted)
    fileArr = Array.from(myFileList)
    fileArr.sort(compareFiles)
*/
function compareFiles(a, b) {
    // 
    return numericCollator.compare(a.name, b.name)
}

/*
This version does not work, because "this" is the wrong thing in callbacks.
But it could probably be easily made to work by adding a
"addEventListener method that takes an id, an event name, and a function
and uses "bind" in the appropriate fashion.

The result might be a nice -- each assignment would be a single line.
*/

class LoomClient {
    constructor() {
        this.ws = new WebSocket("ws")
        this.weavingPattern = null
        this.weaveForward = true
        this.connectionState = ConnectionStateEnum.disconnected
        this.loomState = null
        // this.init()
    }

    init() {
        this.ws.onmessage = this.handleServerReply.bind(this)
        this.ws.onclose = handleWebsocketClosed

        // Assign event handlers for file drag-and-drop
        const dropAreaElt = document.getElementById("body");

        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, preventDefaults)
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, highlight)
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, unhighlight)
        })

        function highlight(event) {
            dropAreaElt.style.backgroundColor = "#E6E6FA"
        }

        function unhighlight(event) {
            dropAreaElt.style.backgroundColor = "#FFFFFF"
        }

        dropAreaElt.addEventListener("drop", this.handleDrop.bind(this))

        var fileInputElt = document.getElementById("file_input")
        fileInputElt.addEventListener("change", this.handleFileInput.bind(this))

        var jumpToPickForm = document.getElementById("jump_to_pick_form")
        jumpToPickForm.addEventListener("submit", this.handleJumpToPick.bind(this))

        var oobCommandForm = document.getElementById("oob_command_form")
        oobCommandForm.addEventListener("submit", this.handleOutOfBandCommand.bind(this))

        var patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))

        var weaveDirectionElt = document.getElementById("weave_direction")
        weaveDirectionElt.addEventListener("click", this.handleWeaveDirection.bind(this))
    }

    /*
    Process a reply from the loom server (data read from the web socket)
    */
    handleServerReply(event) {
        var messageElt = document.getElementById("message")
        messageElt.textContent = event.data.substring(0, 80) + "..."

        const datadict = JSON.parse(event.data)
        if (datadict.type == "ConnectionState") {
            this.connectionState = ConnectionStateTranslationDict[datadict.state]
            this.displayLoomState()
        } else if (datadict.type == "CurrentPickNumber") {
            if (!this.weavingPattern) {
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.weavingPattern.pick_number = datadict.pick_number
            this.weavingPattern.repeat_number = datadict.repeat_number
            this.weavingPattern.display()
            this.displayPick()
        } else if (datadict.type == "LoomState") {
            this.loomState = datadict
            this.displayLoomState()
        } else if (datadict.type == "ReducedPattern") {
            this.weavingPattern = new ReducedPattern(datadict)
            this.weavingPattern.display()
            var patternMenu = document.getElementById("pattern_menu")
            patternMenu.value = this.weavingPattern.name
        } else if (datadict.type == "PatternNames") {
            /*
            Why this code is so odd:
            • The <hr> separator is not part of option list, and there is no good way
              to add a separator in javascript, so I preserve the old one.
            • The obvious solution is to remove the old names, then insert new ones.
              Unfortunately that loses the <hr> separator.
            • So I insert the new names, then remove the old ones. Ugly, but at least
              on macOS Safari 18.1.1 this preserves the separator. If the separator
              is lost on other systems, the menu is still usable.
     
            Also there is subtlety in the case that there is no current weavingPattern
            (in which case the menu should be shown as blank).
            I wanted to avoid the hassle of adding a blank option now,
            which would then have to be purged on the next call to select_pattern.
            Fortunately not bothring to add a blank entry works perfectly!
            At the end the menu value is set to "", which shows as blank,
            and there is no blank option that has to be purged later.
            */
            var patternMenu = document.getElementById("pattern_menu")
            var patternNames = datadict.names
            var menuOptions = patternMenu.options
            var currentName = this.weavingPattern ? this.weavingPattern.name : ""

            // This preserves the separator if called with no names
            if (patternNames.length == 0) {
                patternNames.push("")
            }

            // Save this value for later deletion of old pattern names
            var num_old_pattern_names = patternMenu.options.length - 1

            // Insert new pattern names
            for (let i = 0; i < patternNames.length; i++) {
                var patternName = patternNames[i]
                var option = new Option(patternName)
                menuOptions.add(option, 0)
            }

            // Purge old pattern names
            for (let i = patternNames.length; i < patternNames.length + num_old_pattern_names; i++) {
                menuOptions.remove(patternNames.length)
            }
            patternMenu.value = currentName
        } else if (datadict.type == "WeaveDirection") {
            this.weaveForward = datadict.forward
            this.displayDirection()
        } else {
            console.log("Unknown message type", datadict.type)
        }
    }

    // Display the weave direction -- the value of the global "weaveForward" 
    displayDirection() {
        var weaveDirectionElt = document.getElementById("weave_direction")
        if (this.weaveForward) {
            weaveDirectionElt.textContent = "↓"
            weaveDirectionElt.style.color = "green"
        } else {
            weaveDirectionElt.textContent = "↑"
            weaveDirectionElt.style.color = "red"
        }
    }

    /*
    Display the loom state (a combination of connectionState and loomState)
    */
    displayLoomState() {
        var text = this.connectionState
        var text_color = "#000"
        if ((this.loomState != null) && (this.connectionState == ConnectionStateEnum.connected)) {
            if (this.loomState.error) {
                text = "error"
                text_color = "red"
            } else {
                if (this.loomState.shed_closed && this.loomState.cycle_complete) {
                    text = "shed closed and cycle complete"
                } else if (this.loomState.shed_closed) {
                    text = "shed closed"
                } else if (this.loomState.cycle_complete) {
                    text = "cycle complete"
                } else {
                    text = "shed not closed, cycle not complete"
                }
            }
        }
        var statusElt = document.getElementById("status")
        statusElt.textContent = text
        statusElt.style.color = text_color
    }


    /*
    Display the current and next pick.
    The current pick is read from global ``weavingPattern``, if defined, else 0.
    The next pick is an argument (since it is not stored in a global).
    
    Parameters
    ----------
    next_pick : int
      The (1-based) number of the next pick
    */
    displayPick() {
        var repeatNumberElt = document.getElementById("repeat_number")
        var pickNumberElt = document.getElementById("pick_number")
        if (this.weavingPattern) {
            repeatNumberElt.textContent = "Repeat " + this.weavingPattern.repeat_number
            pickNumberElt.textContent = this.weavingPattern.pick_number + " of " + this.weavingPattern.picks.length
        } else {
            pickNumberElt.textContent = " "
            repeatNumberElt.textContent = " "
        }
    }

    /*
    Handle the pattern_menu select menu.
    
    Send the "select_pattern" or "clear_pattern_names" command.
    */
    async handlePatternMenu(event) {
        var patternMenu = document.getElementById("pattern_menu")
        var message
        if (patternMenu.value == "Clear Menu") {
            message = { "type": "clear_pattern_names" }
        } else {
            message = { "type": "select_pattern", "name": patternMenu.value }
        }
        await this.ws.send(JSON.stringify(message))
    }

    /*
    Handle pattern files dropped on drop area (likely the whole page)
    */
    async handleDrop(event) {
        await this.handleFileList(event.dataTransfer.files)
    }

    /*
    Handle pattern files from the file_list button
    */
    async handleFileInput(event) {
        await this.handleFileList(event.target.files)
    }

    /*
    Handle pattern file upload from the button and drag-and-drop
    (the latter after massaging the data with handleDrop).
    
    Send the "file" and "select_pattern" commands.
    */
    async handleFileList(fileList) {
        if (fileList.length > MaxFiles) {
            console.log("Cannot upload more than", MaxFiles, "files at once")
            return
        }
        if (fileList.length == 0) {
            return
        }

        // Sort the file names; this requires a bit of extra work
        // because FileList doesn't support sort.

        var fileArray = Array.from(fileList)
        fileArray.sort(compareFiles)

        for (let i = 0; i < fileArray.length; i++) {
            var file = fileArray[i]
            var data = await readTextFile(file)
            var fileCommand = { "type": "file", "name": file.name, "data": data }
            await this.ws.send(JSON.stringify(fileCommand))
        }

        // Select the first file uploaded
        var file = fileArray[0]
        var selectPatternCommand = { "type": "select_pattern", "name": file.name }
        await this.ws.send(JSON.stringify(selectPatternCommand))
    }


    /*
    Handle values from the "jump_to_pick" input element.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPick(event) {
        var inputElt = document.getElementById("jump_to_pick")
        var message = { "type": "jump_to_pick", "pick_number": Number(inputElt.value) }
        await this.ws.send(JSON.stringify(message))
        inputElt.value = ""
        event.preventDefault()
    }

    /*
    Handle out of band commands from the "outOfBandCommand" input element.
    
    Send the "oobcommand" command.
    */
    async handleOutOfBandCommand(event) {
        var inputElt = document.getElementById("outOfBandCommand")
        var message = { "type": "oobcommand", "command": inputElt.value }
        await this.ws.send(JSON.stringify(message))
        inputElt.value = ""
        event.preventDefault()
    }

    /*
    Handle weave_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleWeaveDirection(event) {
        var weaveDirectionElt = document.getElementById("weave_direction")
        var newForward = (weaveDirectionElt.textContent == "↑") ? true : false
        var message = { "type": "weave_direction", "forward": newForward }
        await this.ws.send(JSON.stringify(message))
    }
}

/*
Handle websocket close
*/
async function handleWebsocketClosed(event) {
    console.log("web socket closed", event)
    var statusElt = document.getElementById("status")
    statusElt.textContent = `lost connection to server: ${event.reason}`
    statusElt.style.color = "red"
}

//
function preventDefaults(event) {
    event.preventDefault()
    event.stopPropagation()
}

// Async wrapper around FileReader.readAsText
// from https://masteringjs.io/tutorials/fundamentals/filereader#:~:text=The%20FileReader%20class%27%20async%20API%20isn%27t%20ideal,for%20usage%20with%20async%2Fawait%20or%20promise%20chaining.
function readTextFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = res => {
            resolve(res.target.result)
        }
        reader.onerror = err => reject(err)

        reader.readAsText(file)
    })
}

loomClient = new LoomClient()
loomClient.init()
