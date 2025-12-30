(function () {
    const DESKTOP_BREAKPOINT = 900;

    const leftWrapper = document.getElementById("left-wrapper");
    const rightWrapper = document.getElementById("right-wrapper");
    const leftCol = document.getElementById("left");
    const rightCol = document.getElementById("right");
    const centerCol = document.getElementById("center");

    const toggleLeftBtn = document.getElementById("toggle-left");
    const toggleRightBtn = document.getElementById("toggle-right");

    const resizeLeftHandle = document.getElementById("resize-left");
    const resizeRightHandle = document.getElementById("resize-right");

    const shareLink = document.querySelector(".share-link");
    const copyLink = document.querySelector(".copy-link");

    if (!centerCol) return;

    /* ===========================
       LOCAL STORAGE HELPERS
       =========================== */

    function saveLayout() {
        if (window.innerWidth < DESKTOP_BREAKPOINT) return;

        const data = {
            leftWidth: leftCol ? leftCol.style.width : null,
            rightWidth: rightCol ? rightCol.style.width : null,
            leftCollapsed: leftWrapper && leftWrapper.classList.contains("collapsed"),
            rightCollapsed: rightWrapper && rightWrapper.classList.contains("collapsed"),
        };
        localStorage.setItem("layoutPrefs", JSON.stringify(data));
    }

    function loadLayout() {
        if (window.innerWidth < DESKTOP_BREAKPOINT) return;

        let data = JSON.parse(localStorage.getItem("layoutPrefs") || "null");
        if (!data) return;

        if (leftCol && data.leftWidth) leftCol.style.width = data.leftWidth;
        if (rightCol && data.rightWidth) rightCol.style.width = data.rightWidth;

        if (leftWrapper && data.leftCollapsed) {
            leftWrapper.classList.add("collapsed");
            leftCol.style.display = "none";
            toggleLeftBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
        }

        if (rightWrapper && data.rightCollapsed) {
            rightWrapper.classList.add("collapsed");
            rightCol.style.display = "none";
            toggleRightBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
        }
    }

    /* ===========================
       TOGGLE LEFT
       =========================== */

    if (toggleLeftBtn && leftWrapper && leftCol) {
        toggleLeftBtn.addEventListener("click", function () {
            const collapsed = leftWrapper.classList.toggle("collapsed");
            if (collapsed) {
                leftCol.style.display = "none";
                toggleLeftBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
            } else {
                leftCol.style.display = "block";
                toggleLeftBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
            }
            saveLayout();
        });
    }

    /* ===========================
       TOGGLE RIGHT
       =========================== */

    if (toggleRightBtn && rightWrapper && rightCol) {
        toggleRightBtn.addEventListener("click", function () {
            const collapsed = rightWrapper.classList.toggle("collapsed");
            if (collapsed) {
                rightCol.style.display = "none";
                toggleRightBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
            } else {
                rightCol.style.display = "block";
                toggleRightBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
            }
            saveLayout();
        });
    }

    /* ===========================
       RESIZE HANDLES (DESKTOP ONLY)
       =========================== */

    let resizing = null;

    function isDesktop() {
        return window.innerWidth >= DESKTOP_BREAKPOINT;
    }

    function onMouseMove(e) {
        if (!resizing || !isDesktop()) return;

        if (resizing === "left") {
            const totalLeft = leftWrapper.getBoundingClientRect().left;
            let newWidth = e.clientX - totalLeft;
            newWidth = Math.max(80, Math.min(400, newWidth));
            leftCol.style.width = newWidth + "px";
        }

        if (resizing === "right") {
            const rightRect = rightWrapper.getBoundingClientRect();
            const totalRight = rightRect.right;
            let newWidth = totalRight - e.clientX;
            newWidth = Math.max(80, Math.min(400, newWidth));
            rightCol.style.width = newWidth + "px";
        }
    }

    function onMouseUp() {
        if (resizing) {
            resizing = null;
            saveLayout();
        }
    }

    if (resizeLeftHandle) {
        resizeLeftHandle.addEventListener("mousedown", function (e) {
            if (!isDesktop()) return;
            resizing = "left";
            e.preventDefault();
        });
    }

    if (resizeRightHandle) {
        resizeRightHandle.addEventListener("mousedown", function (e) {
            if (!isDesktop()) return;
            resizing = "right";
            e.preventDefault();
        });
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);

    /* ===========================
       SHARE & COPY
       =========================== */

    if (shareLink) {
        shareLink.addEventListener("click", function (e) {
            e.preventDefault();
            if (navigator.share) {
                navigator.share({
                    url: window.location.href,
                    title: document.title
                });
            } else {
                alert("Le partage n'est pas supporté sur ce navigateur.");
            }
        });
    }

    if (copyLink) {
        copyLink.addEventListener("click", function (e) {
            e.preventDefault();
            navigator.clipboard.writeText(window.location.href);
        });
    }

    /* ===========================
       LOAD LAYOUT ON START
       =========================== */

    window.addEventListener("load", function () {
        if (isDesktop()) loadLayout();
    });

    window.addEventListener("resize", function () {
        if (isDesktop()) loadLayout();
    });
})();

