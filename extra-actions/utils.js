// util functions
// Some from Tridactyl
(function (lp$) {
    // lp$ is our local namespace
    function incrementUrl(url, count) {
        // Find the final number in a URL
        const matches = url.match(/(.*?)(\d+)(\D*)$/)

        // no number in URL - nothing to do here
        if (matches === null) {
            return null
        }

        const [, pre, number, post] = matches
        const newNumber = parseInt(number, 10) + count
        let newNumberStr = String(newNumber > 0 ? newNumber : 0)

        // Re-pad numbers that were zero-padded to be the same length:
        // 0009 + 1 => 0010
        if (number.match(/^0/)) {
            while (newNumberStr.length < number.length) {
                newNumberStr = "0" + newNumberStr
            }
        }

        return pre + newNumberStr + post
    }

    /** Return all frames that belong to the document (frames that belong to
     * extensions are ignored).
     *
     * @param doc   The document the frames should be fetched from
     */
    lp$.getAllDocumentFrames = function (doc = document) {
        if (!(doc instanceof HTMLDocument)) return []
        const frames = (Array.from(
            doc.getElementsByTagName("iframe"),) && [])
            .concat(Array.from(doc.getElementsByTagName("frame")))
        return frames.concat(
            frames.reduce((acc, f) => {
                // Errors could be thrown because of CSP
                let newFrames = []
                try {
                    const doc = f.contentDocument || f.contentWindow.document
                    newFrames = lp$.getAllDocumentFrames(doc)
                } catch (e) {}
                return acc.concat(newFrames)
            }, []),
        )
    }

    /* Get all the elements that match the given selector inside shadow DOM */
    function getShadowElementsBySelector(selector) {
        let elems = []
        document.querySelectorAll("*").forEach(elem => {
            if (elem.shadowRoot) {
                const srElems = elem.shadowRoot.querySelectorAll(selector)
                elems = elems.concat(...srElems)
            }
        })
        return elems
    }

    /** Get all elements that match the given selector
     *
     * @param selector   `the CSS selector to choose elements with
     * @param filters     filter to use (in thre given order) to further chose
     *                    items, or [] for all
     */
    lp$.getElementsBySelector = function (selector, filters=[]) {
        let elems = Array.from(document.querySelectorAll(selector))
        elems = elems.concat(...getShadowElementsBySelector(selector))
        const frameElems = lp$.getAllDocumentFrames().reduce((acc, frame) => {
            let newElems = []
            // Errors could be thrown by CSP
            try {
                const doc = frame.contentDocument || frame.contentWindow.document
                newElems = Array.from(doc.querySelectorAll(selector))
            } catch (e) {}
            return acc.concat(newElems)
        }, [])

        elems = elems.concat(frameElems)

        for (const filter of filters) {
            elems = elems.filter(filter)
        }

        return elems
    }

    lp$.urlincrement = function (count = 1) {
        const newUrl = incrementUrl(window.location.href, count)

        if (newUrl !== null) {
            window.location.href = newUrl
        }
    }

    lp$.mouseEvent = function ( element, type, modifierKeys = {}) {
        let events = []
        switch (type) {
            case "unhover":
                events = ["mousemove", "mouseout", "mouseleave"]
                break
            case "click":
                events = ["mousedown", "mouseup", "click"]
            case "hover":
                events = ["mouseover", "mouseenter", "mousemove"].concat(events)
                break
        }
        events.forEach(type => {
            const event = new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window,
                detail: 1, // usually the click count
                ...modifierKeys,
            })
            element.dispatchEvent(event)
        })
    }
})(window.LifereaPS = window.LifereaPS || {});
