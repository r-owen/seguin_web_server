const MaxFiles = 10

// Keys are the possible values of the LoomConnectionState.state messages
// Values are entries in ConnectionStateEnum
const ConnectionStateTranslationDict = {
    0: "disconnected",
    1: "connected",
    2: "connecting",
    3: "disconnecting",
}

const SeverityColors = {
    1: "#ffffff",
    2: "yellow",
    3: "red",
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
        var gotoNextPickElt = document.getElementById("goto_next_pick")
        var shaftsRaisedElt = document.getElementById("shafts_raised")
        if ((this.pick_number > 0) && (this.pick_number <= this.picks.length)) {
            const pick = this.picks[this.pick_number - 1]
            gotoNextPickElt.style.backgroundColor = this.color_table[pick.color]
            var shaftsRaisedText = ""
            for (let i = 0; i < pick.are_shafts_up.length; ++i) {
                if (pick.are_shafts_up[i]) {
                    shaftsRaisedText += " " + (i + 1)
                }
            }
            shaftsRaisedElt.textContent = shaftsRaisedText
        } else {
            gotoNextPickElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
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
                    canvas.height - blockSize * (1 + pickOffset),
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
        this.loomConnectionState = ConnectionStateEnum.disconnected
        this.loomConnectionStateReason = ""
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

        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        jumpToPickResetElt.addEventListener("click", this.handleJumpToPickReset.bind(this))

        var oobCommandForm = document.getElementById("oob_command_form")
        oobCommandForm.addEventListener("submit", this.handleOutOfBandCommand.bind(this))

        var pickNumberElt = document.getElementById("pick_number")
        pickNumberElt.addEventListener("input", this.handleJumpInput.bind(this))

        var repeatNumberElt = document.getElementById("repeat_number")
        repeatNumberElt.addEventListener("input", this.handleJumpInput.bind(this))

        var patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))

        var gotoNextPickElt = document.getElementById("goto_next_pick")
        gotoNextPickElt.addEventListener("click", this.handleGotoNextPick.bind(this))

        var weaveDirectionElt = document.getElementById("weave_direction")
        weaveDirectionElt.addEventListener("click", this.handleWeaveDirection.bind(this))
    }

    /*
    Process a reply from the loom server (data read from the web socket)
    */
    handleServerReply(event) {
        var messageElt = document.getElementById("message")
        messageElt.textContent = event.data.substring(0, 80) + "..."
        var commandProblemElt = document.getElementById("command_problem")

        const datadict = JSON.parse(event.data)
        var resetCommandProblemMessage = true
        if (datadict.type == "CurrentPickNumber") {
            if (!this.weavingPattern) {
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.weavingPattern.pick_number = datadict.pick_number
            this.weavingPattern.repeat_number = datadict.repeat_number
            this.weavingPattern.display()
            this.displayPick()
        } else if (datadict.type == "LoomConnectionState") {
            this.loomConnectionState = ConnectionStateTranslationDict[datadict.state]
            this.loomConnectionStateReason = datadict.reason
            this.displayLoomState()
        } else if (datadict.type == "LoomState") {
            resetCommandProblemMessage = false
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
        } else if (datadict.type == "CommandProblem") {
            resetCommandProblemMessage = false
            var color = SeverityColors[datadict.severity]
            if (color == null) {
                color = "#ffffff"
            }
            commandProblemElt.textContent = datadict.message
            commandProblemElt.style.color = color
        } else if (datadict.type == "WeaveDirection") {
            this.weaveForward = datadict.forward
            this.displayDirection()
        } else {
            console.log("Unknown message type", datadict.type)
        }
        if (resetCommandProblemMessage) {
            commandProblemElt.textContent = ""
            commandProblemElt.style.color = "#ffffff"
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
    Display the loom state (a combination of loomConnectionState and loomState)
    */
    displayLoomState(reason) {
        var text = this.loomConnectionState
        var text_color = "black"
        if (this.loomConnectionState != ConnectionStateEnum.connected) {
            text_color = "red"  // loom must be connected to weave
        }
        if (this.loomConnectionStateReason != "") {
            text = text + " " + this.loomConnectionStateReason
        }
        if ((this.loomState != null) && (this.loomConnectionState == ConnectionStateEnum.connected)) {
            if (this.loomState.error) {
                text = "error"
                text_color = "red"
            } else {
                text_color = "black"  // redundant
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
    Display the current pick and repeat.
    */
    displayPick() {
        var repeatNumberElt = document.getElementById("repeat_number")
        var pickNumberElt = document.getElementById("pick_number")
        var totalPicksElt = document.getElementById("total_picks")
        resetPickAndRepeatNumber()
        var pickNumber = ""
        var totalPicks = "?"
        var repeatNumber = ""
        if (this.weavingPattern) {
            pickNumber = this.weavingPattern.pick_number
            repeatNumber = this.weavingPattern.repeat_number
            totalPicks = this.weavingPattern.picks.length
        }
        pickNumberElt.value = pickNumber
        repeatNumberElt.value = repeatNumber
        totalPicksElt.textContent = ` of ${totalPicks}; repeat `
    }

    /*
    Handle the pattern_menu select menu.
    
    Send the "select_pattern" or "clear_pattern_names" command.
    */
    async handlePatternMenu(event) {
        var patternMenu = document.getElementById("pattern_menu")
        var message
        if (patternMenu.value == "Clear Recents") {
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
    Handle jump_to_pick form submit.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPick(event) {
        var pickNumberElt = document.getElementById("pick_number")
        var repeatNumberElt = document.getElementById("repeat_number")
        // Handle blanks by using the current default, if any
        var pickNumber = 0
        var repeatNumber = 0
        if (this.weavingPattern) {
            pickNumber = this.weavingPattern.pick_number
            repeatNumber = this.weavingPattern.repeat_number
        }
        if (pickNumberElt.value != "") {
            pickNumber = Number(pickNumberElt.value)
        }
        if (repeatNumberElt.value != "") {
            repeatNumber = Number(repeatNumberElt.value)
        }
        var message = { "type": "jump_to_pick", "pick_number": pickNumber, "repeat_number": repeatNumber }
        await this.ws.send(JSON.stringify(message))
        event.preventDefault()
    }

    /*
    Handle user editing of pick_number and repeat_number.
    */
    async handleJumpInput(event) {
        var jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        var pickNumberElt = document.getElementById("pick_number")
        var repeatNumberElt = document.getElementById("repeat_number")
        if (this.weavingPattern) {
            var disable = true
            if (pickNumberElt.value != this.weavingPattern.pick_number) {
                pickNumberElt.style.backgroundColor = "pink"
                disable = false
            } else {
                pickNumberElt.style.backgroundColor = "white"
            }
            if (repeatNumberElt.value != this.weavingPattern.repeat_number) {
                repeatNumberElt.style.backgroundColor = "pink"
                disable = false
            } else {
                repeatNumberElt.style.backgroundColor = "white"
            }
            jumpToPickSubmitElt.disabled = disable
            jumpToPickResetElt.disabled = disable
        } else {
            resetPickAndRepeatNumber()
        }
        event.preventDefault()
    }

    /*
    Handle Reset buttin in the "jump_to_pick" form.
    
    Reset pick number and repeat number to current values.
    */
    async handleJumpToPickReset(event) {
        var pickNumberElt = document.getElementById("pick_number")
        var repeatNumberElt = document.getElementById("repeat_number")
        var pickNumber = ""
        var repeatNumber = ""
        if (this.weavingPattern) {
            var pickNumber = this.weavingPattern.pick_number
            var repeatNumber = this.weavingPattern.repeat_number
        }
        pickNumberElt.value = pickNumber
        repeatNumberElt.value = repeatNumber
        resetPickAndRepeatNumber()
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
    Handle goto_next_pick button clicks.
    
    Send the goto_next_pick command to the loom server.
    */
    async handleGotoNextPick(event) {
        var message = { "type": "goto_next_pick" }
        await this.ws.send(JSON.stringify(message))
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

function resetPickAndRepeatNumber() {
    var pickNumberElt = document.getElementById("pick_number")
    var repeatNumberElt = document.getElementById("repeat_number")
    var jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
    var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
    jumpToPickSubmitElt.disabled = true
    jumpToPickResetElt.disabled = true
    pickNumberElt.style.backgroundColor = "white"
    repeatNumberElt.style.backgroundColor = "white"

}

loomClient = new LoomClient()
loomClient.init()
