const DEFAULT_LOGO = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:60%;height:60%;color:white"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>`;

const CHIPS = [
    ["What are your service times?", "Service Times", `<svg viewBox="0 0 24 24" fill="#e0e7ff" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`],
    ["Where are you located?", "Location", `<svg viewBox="0 0 24 24" fill="#d1fae5" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`],
    ["How can I give?", "Giving", `<svg viewBox="0 0 24 24" fill="#ffe4e6" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`],
    ["I am new here!", "I'm New", `<svg viewBox="0 0 24 24" fill="#fef3c7" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`],
    ["What events are coming up?", "Events", `<svg viewBox="0 0 24 24" fill="#f3e8ff" stroke="#9333ea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`],
    ["I have a prayer request", "Prayer", `<svg viewBox="0 0 24 24" fill="#ecfeff" stroke="#06b6d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`],
];

const TIME_HINT = /\b(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Daily|Weekend|Service|Time|AM|PM)\b/i;

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function boldDays(html) {
    return html.replace(/\b(Sundays?|Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Daily|Weekends?)\b/gi, '<span style="font-weight:800;color:#111827;">$1</span>');
}

function trimLeading(node) {
    while (node.firstChild) {
        const child = node.firstChild;
        if (child.nodeType === Node.TEXT_NODE) {
            child.nodeValue = child.nodeValue.replace(/^[\s\u00A0:-]+/, "");
            if (!child.nodeValue.trim()) {
                child.remove();
                continue;
            }
        } else if (child.tagName === "BR" || (child.tagName === "P" && !child.innerText.trim())) {
            child.remove();
            continue;
        }
        break;
    }
}

class ChurchChatbot extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this.chatHistory = [];
        this.apiUrl = this.getAttribute("api-url") || "/chat";
        this.chatbotTitle = this.getAttribute("title") || "Church Assistant";
        this.churchId = this.getAttribute("church-id") || null;
        this.apiKey = this.getAttribute("api-key") || null;
        this.debug = this.hasAttribute("debug");
        this.greeting = this.getAttribute("greeting") || "Hello! I'm so glad you're here. I'm your digital assistant, ready to help you find service times, get connected, or answer any questions about our church family. How can I help you today?";
        this.logoContent = this.getAttribute("logo-svg") || DEFAULT_LOGO;
    }

    connectedCallback() {
        this.loadMarked();
        this.render();
        this.cacheDomElements();
        this.setupEventListeners();
    }

    loadMarked() {
        if (window.marked) {
            this.markedReady = Promise.resolve();
            return;
        }
        this.markedReady = new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
            script.onload = () => resolve();
            script.onerror = () => resolve();
            document.head.appendChild(script);
        });
    }

    cacheDomElements() {
        const root = this.shadowRoot;
        this.toggleBtn = root.getElementById("chat-toggle");
        this.closeBtn = root.getElementById("chat-close-btn");
        this.chatWindow = root.getElementById("chat-window");
        this.sendBtn = root.getElementById("send-btn");
        this.inputField = root.getElementById("user-input");
        this.chipsContainer = root.getElementById("initial-chips");
        this.historyDiv = root.getElementById("chat-history");
    }

    setupEventListeners() {
        this.toggleBtn.addEventListener("click", () => this.toggleChat());
        this.closeBtn.addEventListener("click", () => this.toggleChat());
        this.sendBtn.addEventListener("click", () => this.sendMessage());
        this.inputField.addEventListener("keydown", (event) => {
            if (event.key === "Enter") this.sendMessage();
        });
        this.chipsContainer.addEventListener("click", (event) => {
            const chip = event.target.closest(".chip");
            if (chip) this.sendPreset(chip.getAttribute("data-msg"));
        });
        this.shadowRoot.addEventListener("click", (event) => this.openExternalLink(event));
    }

    openExternalLink(event) {
        const card = event.target.closest(".interactive-card.has-link");
        const clickedLink = event.target.closest("a");
        const link = clickedLink || (card && card.querySelector("a"));
        if (!link) return;
        const href = link.getAttribute("href");
        if (!href || !(href.startsWith("http") || href.startsWith("//"))) return;
        event.preventDefault();
        event.stopPropagation();
        window.open(href, "_blank", "noopener,noreferrer");
    }

    render() {
        const chips = CHIPS.map(([message, label, icon]) =>
            `<button class="chip" data-msg="${escapeHtml(message)}">${icon} ${label}</button>`
        ).join("");

        this.shadowRoot.innerHTML = `
        <style>
            :host {
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                z-index: 99999;
                position: fixed;
                bottom: 0;
                right: 0;
                --primary-gradient: linear-gradient(145deg, #065f46 0%, #047857 100%);
                --primary-solid: #065f46;
                --accent-color: #059669;
                --bg-chat: #ffffff;
                --text-main: #1f2937;
                --text-muted: #6b7280;
                --border-light: #e5e7eb;
                --shadow-float: 0 10px 40px -10px rgba(6, 95, 70, 0.4);
                --shadow-soft: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                --radius-xl: 20px;
            }
            * { box-sizing: border-box; }
            #chat-toggle {
                position: fixed; bottom: 30px; right: 30px; width: 72px; height: 72px;
                background: var(--primary-gradient); color: white; border-radius: 50%;
                box-shadow: var(--shadow-float); display: flex; justify-content: center; align-items: center;
                cursor: pointer; z-index: 10000; overflow: hidden;
                transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            }
            #chat-toggle:hover { transform: scale(1.1); }
            #chat-window {
                position: fixed; bottom: 120px; right: 30px; width: 380px; height: 650px;
                max-height: calc(100vh - 140px); background: var(--bg-chat); border-radius: var(--radius-xl);
                box-shadow: var(--shadow-soft); display: none; flex-direction: column; overflow: hidden;
                z-index: 9999; opacity: 0; transform: translateY(20px);
                transition: opacity 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
                border: 1px solid rgba(255, 255, 255, 0.8);
            }
            #chat-window.open { opacity: 1; transform: translateY(0); }
            #chat-header {
                background: var(--primary-gradient); color: white; padding: 20px;
                display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            }
            .header-info { display: flex; align-items: center; gap: 12px; }
            .header-avatar, .bot-avatar-sml {
                border-radius: 50%; display: flex; align-items: center; justify-content: center;
                overflow: hidden; color: white; flex-shrink: 0;
            }
            .header-avatar {
                width: 40px; height: 40px; background: rgba(255, 255, 255, 0.2); font-size: 20px;
            }
            .header-text h3 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: 0.3px; }
            .header-text span { font-size: 13px; opacity: 0.95; }
            #chat-close-btn { cursor: pointer; opacity: 0.8; }
            #chat-close-btn:hover { opacity: 1; }
            #chat-history {
                flex: 1; padding: 24px; overflow-y: auto; overflow-x: hidden; background: var(--bg-chat);
                display: flex; flex-direction: column; gap: 20px;
                scrollbar-width: thin; scrollbar-color: rgba(63, 98, 18, 0.2) transparent;
            }
            .msg-container { display: flex; align-items: flex-end; gap: 12px; opacity: 0; animation: fadeIn 0.3s forwards; }
            @keyframes fadeIn { to { opacity: 1; } }
            .user-container { flex-direction: row-reverse; }
            .bot-avatar-sml {
                width: 40px; height: 40px; background: var(--primary-solid); font-size: 16px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            .bot-avatar-sml svg { width: 60%; height: 60%; }
            .msg {
                max-width: 82%; padding: 14px 18px; font-size: 14.5px; line-height: 1.55;
                position: relative; overflow-wrap: break-word;
            }
            .bot-msg {
                background: #f3f4f6; border-radius: 20px 20px 20px 4px; color: var(--text-main);
            }
            .user-msg {
                background: var(--primary-gradient); color: white; border-radius: 20px 20px 4px 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .bot-msg p { margin: 0 0 10px 0; }
            .bot-msg p:last-child { margin-bottom: 0; }
            .bot-msg ul { margin: 8px 0; padding-left: 20px; }
            .bot-msg li { margin-bottom: 6px; }
            .bot-msg a { color: var(--accent-color); text-decoration: none; font-weight: 600; }
            .bot-msg a:hover { text-decoration: underline; color: var(--primary-solid); }
            .bot-msg strong { font-weight: 600; color: #111827; }
            .sources-footer {
                margin-top: 16px; border-top: 1px solid #f3f4f6; font-size: 11px; color: #9ca3af;
                display: flex; align-items: center; gap: 6px; background: #f9fafb;
                margin-left: -18px; margin-right: -18px; margin-bottom: -14px; padding: 10px 18px;
                border-radius: 0 0 20px 4px;
            }
            .sources-footer span { font-weight: 500; letter-spacing: 0.3px; text-transform: uppercase; font-size: 10px; }
            .sources-footer a {
                color: var(--accent-color); font-weight: 600; text-decoration: none;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px;
            }
            .sources-footer a:hover { text-decoration: underline; color: var(--primary-solid); }
            .card-list {
                list-style: none; padding: 0; margin: 16px 0; display: flex; flex-direction: column; gap: 16px;
            }
            .interactive-card {
                background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; margin: 0;
                display: flex; flex-direction: column; overflow: hidden;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            .interactive-card:hover {
                box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.1); transform: translateY(-2px); border-color: #d1d5db;
            }
            .interactive-card.has-link { cursor: pointer; }
            .interactive-card.has-link:hover { border-color: var(--accent-color); }
            .interactive-card > a, .interactive-card > .card-header {
                display: flex; align-items: center; justify-content: space-between;
                padding: 18px 22px; background: var(--primary-solid); color: #ffffff; text-decoration: none;
                font-weight: 700; font-size: 1.05em; width: 100%; border-bottom: 1px solid #e5e7eb;
            }
            .interactive-card > a { cursor: pointer; }
            .interactive-card > .card-header { cursor: default; }
            .interactive-card > a:hover { opacity: 0.9; color: #ffffff; }
            .interactive-card > a:hover span { text-decoration: underline; }
            .interactive-card > a::after {
                content: "→"; font-size: 18px; color: rgba(255, 255, 255, 0.8); transition: transform 0.2s;
            }
            .interactive-card > a:hover::after { transform: translateX(4px); color: #ffffff; }
            .interactive-card > a, .interactive-card > .card-header,
            .interactive-card > a *, .interactive-card > .card-header * { color: #ffffff !important; }
            .interactive-card .card-body {
                padding: 12px 22px 20px; background: #ffffff; display: flex; flex-direction: column; gap: 12px;
                color: #374151; font-size: 0.95em; line-height: 1.6; text-align: left; white-space: normal;
            }
            .interactive-card .card-body * { text-align: left; text-indent: 0; margin-left: 0; padding-left: 0; }
            .interactive-card ul {
                list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px;
            }
            .interactive-card li { padding: 0; border: none; display: flex; flex-direction: column; align-items: stretch; }
            .interactive-card strong { color: var(--primary-solid); font-weight: 600; min-width: 80px; display: inline-block; }
            .chips-container { display: flex; flex-wrap: wrap; gap: 8px; margin-left: 48px; margin-top: 10px; }
            .chip {
                background: #ffffff; border: 1px solid var(--border-light); padding: 8px 16px; border-radius: 20px;
                font-size: 13px; font-weight: 500; color: var(--text-main); cursor: pointer;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); transition: all 0.2s ease;
            }
            .chip:hover {
                border-color: var(--accent-color); color: var(--primary-solid); transform: translateY(-1px);
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }
            .chip svg { margin-right: 6px; vertical-align: text-bottom; width: 14px; height: 14px; }
            #chat-input-area {
                padding: 16px 20px; background: #ffffff; border-top: 1px solid var(--border-light);
                display: flex; gap: 12px; align-items: center;
            }
            #user-input {
                flex: 1; padding: 14px 20px; border: 1px solid var(--border-light); background: #f9fafb;
                border-radius: 24px; font-size: 15px; outline: none; font-family: inherit; color: var(--text-main);
            }
            #user-input:focus { background: #ffffff; border-color: var(--accent-color); box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); }
            #send-btn {
                width: 44px; height: 44px; border-radius: 50%; background: var(--primary-gradient); color: white;
                border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            #send-btn:hover { transform: scale(1.05); }
            #send-btn svg { fill: currentColor; width: 22px; height: 22px; margin-left: 2px; }
            #loading-dots { display: flex; gap: 4px; padding: 6px 0; }
            .dot {
                width: 6px; height: 6px; background: var(--text-muted); border-radius: 50%;
                animation: bounce 1.4s infinite ease-in-out both;
            }
            .dot:nth-child(1) { animation-delay: -0.32s; }
            .dot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        </style>
        <div id="chat-toggle" role="button" aria-label="Open Chat">${this.logoContent}</div>
        <div id="chat-window">
            <div id="chat-header">
                <div class="header-info">
                    <div class="header-avatar">${this.logoContent}</div>
                    <div class="header-text">
                        <h3>${escapeHtml(this.chatbotTitle)}</h3>
                        <span>Digital Greeter</span>
                    </div>
                </div>
                <div id="chat-close-btn" role="button" aria-label="Close Chat">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </div>
            </div>
            <div id="chat-history">
                <div class="msg-container bot-container">
                    <div class="bot-avatar-sml">${this.logoContent}</div>
                    <div class="msg bot-msg">
                        <p>${escapeHtml(this.greeting)}</p>
                        <p>Select one of the options below or type out your own message and I'd be happy to help you!</p>
                    </div>
                </div>
                <div class="chips-container" id="initial-chips">${chips}</div>
            </div>
            <div id="chat-input-area">
                <input type="text" id="user-input" placeholder="Ask a question..." autocomplete="off">
                <button id="send-btn" aria-label="Send Message"><svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
            </div>
        </div>`;
    }

    toggleChat() {
        const isHidden = getComputedStyle(this.chatWindow).display === "none";
        if (isHidden) {
            this.chatWindow.style.display = "flex";
            setTimeout(() => {
                this.chatWindow.classList.add("open");
                this.scrollToBottom();
                this.inputField.focus();
            }, 10);
            return;
        }
        this.chatWindow.classList.remove("open");
        setTimeout(() => { this.chatWindow.style.display = "none"; }, 200);
    }

    sendPreset(text) {
        this.inputField.value = text;
        this.sendMessage();
    }

    scrollToBottom() {
        this.historyDiv.scrollTo({ top: this.historyDiv.scrollHeight, behavior: "smooth" });
    }

    appendMessage(className, innerHtml) {
        this.historyDiv.insertAdjacentHTML("beforeend", `
            <div class="msg-container ${className}">
                ${className.startsWith("bot") ? `<div class="bot-avatar-sml">${this.logoContent}</div>` : ""}
                <div class="msg ${className.startsWith("bot") ? "bot-msg" : "user-msg"}">${innerHtml}</div>
            </div>`);
        this.scrollToBottom();
    }

    async sendMessage() {
        const text = this.inputField.value.trim();
        if (!text) return;

        const historyPayload = this.chatHistory.slice(-8);
        this.appendMessage("user-container", escapeHtml(text));
        this.chatHistory.push({ role: "user", content: text });
        this.inputField.value = "";

        const loadingId = `loading-${Date.now()}`;
        this.historyDiv.insertAdjacentHTML("beforeend", `
            <div class="msg-container bot-container" id="${loadingId}">
                <div class="bot-avatar-sml">${this.logoContent}</div>
                <div class="msg bot-msg" style="min-width:60px"><div id="loading-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>
            </div>`);
        this.scrollToBottom();

        try {
            await this.markedReady;
            const headers = { "Content-Type": "application/json" };
            if (this.apiKey) headers["X-API-Key"] = this.apiKey;
            const response = await fetch(this.apiUrl, {
                method: "POST",
                headers,
                body: JSON.stringify({ message: text, history: historyPayload, church_id: this.churchId }),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                if (this.debug) console.error("Server Error:", errorData);
                const message = errorData.error?.message
                    || (typeof errorData.error === "string" ? errorData.error : "")
                    || (typeof errorData.detail === "string" ? errorData.detail : "");
                throw new Error(message || `Server returned status: ${response.status}`);
            }

            const data = await response.json();
            this.shadowRoot.getElementById(loadingId)?.remove();
            this.appendMessage("bot-container", `${this.formatReply(data.response || "")}${this.sourceHtml(data.sources)}`);
            this.chatHistory.push({ role: "assistant", content: data.response || "" });
        } catch (error) {
            console.error(error);
            this.shadowRoot.getElementById(loadingId)?.remove();
            const shown = error.message && (error.message.includes("Application Failed") || error.message.includes("API_KEY"))
                ? `Server Error: ${error.message}`
                : "I'm sorry, I'm having trouble connecting to the server right now.";
            this.historyDiv.insertAdjacentHTML("beforeend", `
                <div class="msg-container bot-container">
                    <div class="bot-avatar-sml" style="background:#ef4444">!</div>
                    <div class="msg bot-msg">${escapeHtml(shown)}</div>
                </div>`);
            this.scrollToBottom();
        }
    }

    formatReply(raw) {
        if (!window.marked) return escapeHtml(raw).replace(/\n/g, "<br>");
        const html = window.marked.parse(raw).replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ');
        return this.postProcessHtml(html);
    }

    sourceHtml(sources) {
        const source = (sources || [])[0];
        if (!source) return "";
        let label = source;
        try {
            const url = new URL(source);
            label = url.hostname + url.pathname;
        } catch (_error) {
            label = source;
        }
        return `<div class="sources-footer"><span>Source:</span> <a href="${escapeHtml(source)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a></div>`;
    }

    postProcessHtml(html) {
        const root = document.createElement("div");
        root.innerHTML = html;
        root.querySelectorAll("ul").forEach((list) => {
            const items = [...list.children].filter((el) => el.tagName === "LI");
            if (!items.length) return;
            const link = items[0].querySelector("a");
            const strong = items[0].querySelector("strong, b");
            const linkedHere = link && link.closest("ul") === list;
            const strongHere = strong && strong.closest("ul") === list;
            if (!linkedHere && !strongHere) return;
            list.classList.add("card-list");
            items.forEach((item) => this.formatCard(item, list));
        });
        return root.innerHTML;
    }

    formatCard(item, list) {
        item.classList.add("interactive-card");
        const nested = item.querySelector("ul");
        if (!nested || TIME_HINT.test(item.textContent)) {
            this.formatLeaf(item);
            return;
        }
        this.formatParent(item, list);
    }

    formatLeaf(item) {
        item.querySelectorAll("ul").forEach((sub) => {
            const text = [...sub.querySelectorAll("li")].map((entry) => entry.textContent.trim()).filter(Boolean).join(", ");
            if (text) sub.parentNode.insertBefore(document.createTextNode(` ${text}`), sub);
            sub.remove();
        });
        [...item.childNodes].forEach((node) => {
            if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim().startsWith(":")) {
                node.nodeValue = node.nodeValue.replace(/^\s*:\s*/, " ");
            }
        });

        const link = item.querySelector("a");
        if (!link) {
            const body = document.createElement("div");
            body.className = "card-body";
            body.innerHTML = boldDays(item.innerHTML);
            item.replaceChildren(body);
            return;
        }

        const header = document.createElement("div");
        header.className = "card-header";
        header.appendChild(link);
        const body = document.createElement("div");
        body.className = "card-body";
        while (item.firstChild) body.appendChild(item.firstChild);
        trimLeading(body);
        body.innerHTML = boldDays(body.innerHTML);
        item.appendChild(header);
        if (body.innerText.trim()) item.appendChild(body);
    }

    formatParent(item, list) {
        let header = item.querySelector("a");
        if (!header || header.closest("ul") !== list) {
            const strong = item.querySelector(":scope > strong, :scope > b");
            if (strong) {
                header = document.createElement("div");
                header.className = "card-header";
                header.innerHTML = `<span>${strong.innerHTML.replace(":", "")}</span>`;
                strong.remove();
                item.prepend(header);
            } else if (header && header.parentNode !== item) {
                item.prepend(header);
            }
        } else if (header.parentNode !== item) {
            item.prepend(header);
        }
        if (!header) return;

        if (header.tagName === "A") {
            const parts = header.innerText.split(":");
            if (parts.length > 1) {
                header.innerHTML = `<span><strong>${escapeHtml(parts[0])}</strong>${escapeHtml(parts.slice(1).join(":"))}</span>`;
            }
        }

        const body = document.createElement("div");
        body.className = "card-body";
        while (item.childNodes.length > 1) {
            const child = item.childNodes[1];
            if (child.nodeName === "BR") child.remove();
            else body.appendChild(child);
        }
        trimLeading(body);
        [...body.childNodes].forEach((node) => {
            if ((node.nodeName === "P" && !node.innerText.trim()) || (node.nodeType === Node.TEXT_NODE && !node.nodeValue.trim())) {
                node.remove();
            }
        });
        item.appendChild(body);
        if (item.querySelector("a")) item.classList.add("has-link");
    }
}

customElements.define("church-chatbot", ChurchChatbot);
