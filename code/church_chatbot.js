console.log("🚀 CHURCH CHATBOT v12 (Clickable Cards) LOADED 🚀");

const DEFAULT_LOGO = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width: 60%; height: 60%; color: white;">
  <circle cx="12" cy="12" r="10"/>
  <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
  <line x1="9" y1="9" x2="9.01" y2="9"/>
  <line x1="15" y1="9" x2="15.01" y2="9"/>
</svg>`;

class ChurchChatbot extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.chatHistory = [];
        this.apiUrl = this.getAttribute('api-url') || '/chat';
        this.chatbotTitle = this.getAttribute('title') || 'Church Assistant';
        this.churchId = this.getAttribute('church-id') || null; // Support Multi-Tenancy
        this.greeting = this.getAttribute('greeting') || "Hello! 👋 I'm so glad you're here. I'm your digital assistant, ready to help you find service times, get connected, or answer any questions about our church family. How can I help you today?";
        this.logoContent = this.getAttribute('logo-svg') || DEFAULT_LOGO;
    }

    connectedCallback() {
        this.injectDependencies();
        this.render();
        this.cacheDomElements(); // Optimization: Cache once
        this.setupEventListeners();
    }

    cacheDomElements() {
        this.toggleBtn = this.shadowRoot.getElementById('chat-toggle');
        this.closeBtn = this.shadowRoot.getElementById('chat-close-btn');
        this.chatWindow = this.shadowRoot.getElementById('chat-window');
        this.sendBtn = this.shadowRoot.getElementById('send-btn');
        this.inputField = this.shadowRoot.getElementById('user-input'); // Correct ID
        this.chipsContainer = this.shadowRoot.getElementById('initial-chips');
        this.historyDiv = this.shadowRoot.getElementById('chat-history');
    }

    setupEventListeners() {
        // Toggle Logic
        const toggle = () => this.toggleChat();
        this.toggleBtn.addEventListener('click', toggle);
        this.closeBtn.addEventListener('click', toggle);

        // Send Logic
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        // Chips
        this.chipsContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.chip');
            if (btn) this.sendPreset(btn.getAttribute('data-msg'));
        });

        // GLOBAL CLICK INTERCEPTOR (Fix for "Refused to connect")
        // This catches ALL link clicks inside the shadow DOM and forces them to new tab.
        // GLOBAL CLICK INTERCEPTOR
        this.shadowRoot.addEventListener('click', (e) => {
            // A. Check for "Card Click" (User clicked box, not specific link)
            const card = e.target.closest('.interactive-card.has-link');
            const clickedLink = e.target.closest('a');

            if (card && !clickedLink) {
                // User clicked the card background -> Find the main link
                const mainLink = card.querySelector('a');
                if (mainLink) {
                    const href = mainLink.getAttribute('href');
                    if (href) {
                        e.preventDefault();
                        e.stopPropagation();
                        window.open(href, '_blank', 'noopener,noreferrer');
                        return;
                    }
                }
            }

            // B. Check for "Link Click" (Standard or inside card)
            if (clickedLink) {
                const href = clickedLink.getAttribute('href');
                if (href && (href.startsWith('http') || href.startsWith('//'))) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.open(href, '_blank', 'noopener,noreferrer');
                }
            }
        });
    }

    injectDependencies() {
        if (!window.marked) {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
            document.head.appendChild(script);
        }
    }

    render() {
        const style = `
        <style>
            :host {
                /* Inherit font or use default */
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                z-index: 99999;
                position: fixed;
                bottom: 0;
                right: 0;

                /* MODERN CLEAN EMERALD THEME */
                /* A professional, fresh church website look. No yellow. */
                --primary-gradient: linear-gradient(145deg, #065f46 0%, #047857 100%); /* Emerald 800 -> 700 */
                --primary-solid: #065f46;
                --accent-color: #059669; /* Emerald 600 */
                --accent-bg: #ecfdf5; /* Emerald 50 */
                
                --bg-chat: #ffffff; /* Pure White - Clean */
                --text-main: #1f2937; /* Gray 800 - Sharp & Modern */
                --text-muted: #6b7280; /* Gray 500 */
                --border-light: #e5e7eb; /* Gray 200 */
                
                --shadow-float: 0 10px 40px -10px rgba(6, 95, 70, 0.4); /* Deep emerald shadow */
                --shadow-soft: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); /* Subtle neutral shadow */

                --radius-xl: 20px; /* Slightly tighter, more professional */
                --radius-sm: 8px;
            }

            * { box-sizing: border-box; }

            /* 1. Toggle Button - Dark Green & Modern */
            #chat-toggle {
                position: fixed;
                bottom: 30px;
                right: 30px;
                width: 72px;
                height: 72px;
                background: var(--primary-gradient);
                color: white;
                border-radius: 50%;
                box-shadow: var(--shadow-float);
                display: flex;
                justify-content: center;
                align-items: center;
                cursor: pointer;
                z-index: 10000;
                overflow: hidden;
                transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            #chat-toggle:hover {
                transform: scale(1.1);
            }

            /* 2. Chat Window */
            #chat-window {
                position: fixed;
                bottom: 120px; /* Moved up to clear the toggle button (72px + 30px + padding) */
                right: 30px;
                width: 380px;
                height: 650px;
                max-height: calc(100vh - 140px); /* Adjusted max-height to keep it on screen */
                background: var(--bg-chat);
                border-radius: var(--radius-xl);
                box-shadow: var(--shadow-soft);
                display: none;
                flex-direction: column;
                overflow: hidden;
                z-index: 9999;
                opacity: 0;
                transform: translateY(20px);
                transition: opacity 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
                border: 1px solid rgba(255, 255, 255, 0.8);
            }

            #chat-window.open {
                opacity: 1;
                transform: translateY(0);
            }

            /* Header */
            #chat-header {
                background-color: var(--primary-solid);
                background: var(--primary-gradient);
                color: white;
                padding: 20px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-shrink: 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }

            .header-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .header-avatar {
                width: 40px;
                height: 40px;
                justify-content: center;
                display: flex;
                align-items: center;
                font-size: 20px;
                overflow: hidden;
                border-radius: 50%;
                background: rgba(255,255,255,0.2);
                border: none;
            }

            .header-text h3 {
                margin: 0;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }

            .header-text span {
                font-size: 13px;
                opacity: 0.95;
            }

            #chat-close-btn {
                cursor: pointer;
                opacity: 0.8;
                transition: opacity 0.2s;
            }

            #chat-close-btn:hover {
                opacity: 1;
            }

            /* Chat History */
            #chat-history {
                flex: 1;
                padding: 24px;
                overflow-y: auto;
                overflow-x: hidden; /* Prevent horizontal scroll on mobile */
                background: var(--bg-chat);
                display: flex;
                flex-direction: column;
                gap: 20px;
                scrollbar-width: thin;
                scrollbar-color: rgba(63, 98, 18, 0.2) transparent;
            }

            /* Messages */
            .msg-container {
                display: flex;
                align-items: flex-end;
                gap: 12px;
                opacity: 0;
                animation: fadeIn 0.3s forwards;
            }

            @keyframes fadeIn {
                to { opacity: 1; }
            }

            .user-container {
                flex-direction: row-reverse;
            }

            .bot-avatar-sml {
                width: 40px;
                height: 40px;
                background: var(--primary-solid); /* Use Primary Color */
                color: white;
                border: none;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                flex-shrink: 0;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            
            .bot-avatar-sml svg {
                width: 60%;
                height: 60%;
            }

            .msg {
                max-width: 82%; /* Slightly reduced to prevent edge cases */
                padding: 14px 18px;
                font-size: 14.5px;
                line-height: 1.55;
                position: relative;
                word-wrap: break-word;
                overflow-wrap: break-word; /* Modern wrapping */
            }

            .bot-msg {
                background: #f3f4f6; /* Gray 100 - Clean & Neutral */
                border: none; /* Cleaner look without border */
                border-radius: 20px 20px 20px 4px;
                color: var(--text-main);
                box-shadow: none; /* Flat design is more modern */
            }

            .user-msg {
                background: var(--primary-gradient);
                color: white;
                border-radius: 20px 20px 4px 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); /* Subtle shadow */
                font-weight: 400; /* Lighter font weight looks more premium */
            }

            .bot-msg p { margin: 0 0 10px 0; }
            .bot-msg p:last-child { margin-bottom: 0; }
            .bot-msg ul { margin: 8px 0; padding-left: 20px; }
            .bot-msg li { margin-bottom: 6px; }
            .bot-msg a { color: var(--accent-color); text-decoration: none; font-weight: 600; }
            .bot-msg a:hover { text-decoration: underline; color: var(--primary-solid); }
            .bot-msg strong { font-weight: 600; color: #111827; /* Gray 900 */ }

            /* Source Footer */
            /* Source Footer - Premium Look */
            .sources-footer {
                margin-top: 16px;
                border-top: 1px solid #f3f4f6;
                font-size: 11px;
                color: #9ca3af;
                display: flex;
                align-items: center;
                gap: 6px;
                background: #f9fafb; /* Slight contrast */
                margin-left: -18px; /* Bleed to edges */
                margin-right: -18px;
                margin-bottom: -14px; /* Fill bottom */
                padding: 10px 18px;
                border-radius: 0 0 20px 4px; /* Follow bubble shape */
            }
            .sources-footer span { font-weight: 500; letter-spacing: 0.3px; text-transform: uppercase; font-size: 10px; }
            .sources-footer a {
                color: var(--accent-color);
                font-weight: 600;
                text-decoration: none;
                transition: color 0.2s;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 140px;
            }
            .sources-footer a:hover {
                text-decoration: underline;
                color: var(--primary-solid);
            }

            /* Interactive Link Cards - PREMIUM GENERIC STYLE */
            .card-list {
                list-style: none;
                padding: 0;
                margin: 16px 0;
                display: flex;
                flex-direction: column;
                gap: 16px; /* More separation between cards */
            }

            .interactive-card {
                background: #ffffff;
                border: 1px solid #e5e7eb; /* Subtle neutral border */
                border-radius: 12px; /* Clean modern radius */
                padding: 0;
                margin: 0;
                cursor: default;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                display: flex;
                flex-direction: column;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                overflow: hidden; /* Clips the header background */
            }
            
            .interactive-card:hover {
                box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.1);
                transform: translateY(-2px);
                border-color: #d1d5db;
            }
            
            /* Make fully clickable cards look interactive */
            .interactive-card.has-link {
                cursor: pointer;
            }
            .interactive-card.has-link:hover {
                border-color: var(--accent-color); /* Green Border on Hover */
            }
            
            /* The Main Link (Header of the card) */
            /* The Main Link (Header of the card) */
            .interactive-card > a,
            .interactive-card > .card-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 18px 22px; 
                background: var(--primary-solid); /* Solid Green Header */
                color: white; /* White Text */
                text-decoration: none;
                font-weight: 700;
                font-size: 1.05em;
                width: 100%; 
                box-sizing: border-box; 
                border-bottom: 1px solid #e5e7eb;
                transition: opacity 0.2s;
            }
            .interactive-card > a { cursor: pointer; }
            .interactive-card > .card-header { cursor: default; }

            .interactive-card > a:hover {
                background: var(--primary-solid); 
                opacity: 0.9; /* Slight feedback */
                color: white; 
            }
            .interactive-card > a:hover span {
                text-decoration: underline; 
            }

            .interactive-card > a::after {
                content: "→";
                font-size: 18px;
                color: rgba(255, 255, 255, 0.8); /* White Arrow */
                transition: all 0.2s;
            }
            .interactive-card > a:hover::after {
                transform: translateX(4px);
                opacity: 1;
            }
            
            /* Nested Content (e.g. Service Times list) */
            .interactive-card .card-body {
                padding: 20px 22px; 
                background: #ffffff; /* White Box */
                display: flex;
                flex-direction: column;
                gap: 12px;
                color: #374151; 
                font-size: 0.95em;
                line-height: 1.6;
            }

            /* Reset nested lists to assume they are inside card-body */
            .interactive-card ul {
                list-style: none !important;
                padding: 0;
                margin: 0;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .interactive-card li {
                padding: 0;
                border: none;
                display: flex;
                flex-direction: column; /* Allow multi-line alignment */
                align-items: stretch; /* FORCE FULL WIDTH CHILDREN */
            }
            
            /* Custom generic bullet/icon replacement */
            .interactive-card li::before {
                content: ""; /* Remove dot */
                display: none;
            }

            /* Strong text in details (The Label) */
            .interactive-card strong {
                color: var(--primary-solid);
                font-weight: 600;
                min-width: 80px; /* Align values if labels are short */
                display: inline-block;
            }
            
            /* ... (Chips and rest of CSS) ... */
            
            /* ... */


            /* Chips */
            .chips-container {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-left: 48px;
                margin-top: 10px;
            }
            .chip {
                background: #ffffff;
                border: 1px solid var(--border-light);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
                color: var(--text-main);
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            .chip:hover {
                border-color: var(--accent-color);
                color: var(--primary-solid);
                background: white;
                transform: translateY(-1px);
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }
            .chip svg {
                margin-right: 6px;
                vertical-align: text-bottom;
                width: 14px; /* Slightly smaller icons */
                height: 14px;
            }

            /* Input Area */
            #chat-input-area {
                padding: 16px 20px;
                background: #ffffff;
                border-top: 1px solid var(--border-light);
                display: flex;
                gap: 12px;
                align-items: center;
                z-index: 10;
            }
            #user-input {
                flex: 1;
                padding: 14px 20px;
                border: 1px solid var(--border-light);
                background: #f9fafb; /* Gray 50 */
                border-radius: 24px;
                font-size: 15px;
                outline: none;
                transition: all 0.2s;
                font-family: inherit;
                color: var(--text-main);
            }
            #user-input:focus {
                background: #ffffff;
                border-color: var(--accent-color);
                box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); /* Soft Emerald glow */
            }
            #send-btn {
                width: 44px;
                height: 44px;
                border-radius: 50%;
                background: var(--primary-gradient);
                color: white;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: transform 0.2s ease;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            #send-btn:hover { transform: scale(1.05); }
            #send-btn svg { fill: currentColor; width: 22px; height: 22px; margin-left: 2px; }

            /* Typing Dots */
            #loading-dots { display: flex; gap: 4px; padding: 6px 0; }
            .dot {
                width: 6px; height: 6px; background: var(--text-muted); border-radius: 50%;
                animation: bounce 1.4s infinite ease-in-out both;
            }
            .dot:nth-child(1) { animation-delay: -0.32s; }
            .dot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes bounce {
                0%, 80%, 100% { transform: scale(0); }
                40% { transform: scale(1.0); }
            }
        </style>`;

        const html = `
        <!-- TOGGLE BUTTON -->
        <div id="chat-toggle" role="button" aria-label="Open Chat">
            ${this.logoContent}
        </div>

        <!-- CHAT WINDOW -->
        <div id="chat-window">
            <!-- Header -->
            <div id="chat-header">
                <div class="header-info">
                    <div class="header-avatar">
                        ${this.logoContent}
                    </div>
                    <div class="header-text">
                        <h3>${this.chatbotTitle}</h3>
                        <span>Digital Greeter</span>
                    </div>
                </div>
                <div id="chat-close-btn" role="button" aria-label="Close Chat">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </div>
            </div>

            <!-- History -->
            <div id="chat-history">
                <!-- Greeting -->
                <div class="msg-container bot-container">
                    <div class="bot-avatar-sml">
                        ${this.logoContent}
                    </div>
                    <div class="msg bot-msg">
                        <p>${this.greeting}</p>
                        <p>Select one of the options below or type out your own message and I'd be happy to help you!</p>
                    </div>
                </div>

                <!-- Chips -->
                <div class="chips-container" id="initial-chips">
                    <button class="chip" data-msg="What are your service times?">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#e0e7ff" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Service Times
                    </button>
                    <button class="chip" data-msg="Where are you located?">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#d1fae5" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> Location
                    </button>
                    <button class="chip" data-msg="How can I give?">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#ffe4e6" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg> Giving
                    </button>
                    <button class="chip" data-msg="I am new here!">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#fef3c7" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> I'm New
                    </button>
                     <button class="chip" data-msg="What events are coming up?">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#f3e8ff" stroke="#9333ea" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> Events
                    </button>
                     <button class="chip" data-msg="I have a prayer request">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="#ecfeff" stroke="#06b6d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg> Prayer
                    </button>
                </div>
            </div>

            <!-- Input -->
            <div id="chat-input-area">
                <input type="text" id="user-input" placeholder="Ask a question..." autocomplete="off">
                <button id="send-btn" aria-label="Send Message">
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
                </button>
            </div>
        </div>
        `;

        this.shadowRoot.innerHTML = style + html;
    }

    setupEventListeners() {
        // Bind UI elements
        this.chatWindow = this.shadowRoot.getElementById('chat-window');
        this.toggleBtn = this.shadowRoot.getElementById('chat-toggle');
        this.closeBtn = this.shadowRoot.getElementById('chat-close-btn');
        this.inputField = this.shadowRoot.getElementById('user-input');
        this.sendBtn = this.shadowRoot.getElementById('send-btn');
        this.chipsContainer = this.shadowRoot.getElementById('initial-chips');
        this.historyDiv = this.shadowRoot.getElementById('chat-history');

        // Toggle logic
        this.toggleBtn.onclick = () => this.toggleChat();
        this.closeBtn.onclick = () => this.toggleChat();

        // Send logic
        this.sendBtn.onclick = () => this.sendMessage();
        this.inputField.onkeypress = (e) => {
            if (e.key === 'Enter') this.sendMessage();
        };

        // Chips logic
        const chips = this.shadowRoot.querySelectorAll('.chip');
        chips.forEach(chip => {
            chip.onclick = () => {
                const msg = chip.getAttribute('data-msg');
                this.sendPreset(msg);
            };
        });
    }

    toggleChat() {
        const isHidden = getComputedStyle(this.chatWindow).display === 'none';
        if (isHidden) {
            this.chatWindow.style.display = 'flex';
            setTimeout(() => {
                this.chatWindow.classList.add('open');
                this.scrollToBottom();
                this.inputField.focus();
            }, 10);
        } else {
            this.chatWindow.classList.remove('open');
            setTimeout(() => { this.chatWindow.style.display = 'none'; }, 200);
        }
    }

    sendPreset(text) {
        this.inputField.value = text;
        this.sendMessage();
        // User requested chips remain visible and clickable multiple times
    }

    scrollToBottom() {
        this.historyDiv.scrollTo({ top: this.historyDiv.scrollHeight, behavior: 'smooth' });
    }

    async sendMessage() {
        const text = this.inputField.value.trim();
        if (!text) return;

        // 1. User Msg
        this.historyDiv.insertAdjacentHTML('beforeend', `
            <div class="msg-container user-container">
                <div class="msg user-msg">${text.replace(/</g, "&lt;")}</div>
            </div>`);
        this.chatHistory.push({ role: 'user', content: text });
        this.inputField.value = "";
        this.scrollToBottom();

        // 2. Loading
        const loadingId = "loading-" + Date.now();
        this.historyDiv.insertAdjacentHTML('beforeend', `
            <div class="msg-container bot-container" id="${loadingId}">
                <div class="bot-avatar-sml">
                    ${this.logoContent}
                </div>
                <div class="msg bot-msg" style="min-width: 60px;">
                        <div id="loading-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
                </div>
            </div>`);
        this.scrollToBottom();

        try {
            const response = await fetch(this.apiUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    history: this.chatHistory,
                    use_full_context: false,
                    church_id: this.churchId
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error("Server Error:", errorData);
                // Throw specific error if available
                if (errorData.error) throw new Error(errorData.error);
                throw new Error(`Server returned status: ${response.status}`);
            }

            const data = await response.json();
            const rawResponse = data.response;
            const sources = data.sources || []; // Array of URLs

            // Parse Markdown
            // Parse Markdown
            let formattedResponse = rawResponse;
            if (window.marked) {
                formattedResponse = window.marked.parse(rawResponse);
                // Safe way to force new tab for links (prevents 'refused to connect' inside iframe)
                formattedResponse = formattedResponse.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ');
                formattedResponse = this.postProcessHtml(formattedResponse);
            }

            // Remove Loading
            const loadingElem = this.shadowRoot.getElementById(loadingId);
            if (loadingElem) loadingElem.remove();

            // 3. Bot Msg
            let sourcesHtml = "";
            if (sources.length > 0) {
                sourcesHtml = `<div class="sources-footer">
                    <span>Source:</span>
                    ${sources.slice(0, 1).map(s => `<a href="${s}" target="_blank" title="${s}">${new URL(s).hostname + new URL(s).pathname}</a>`).join(", ")}
                </div>`;
            }

            this.historyDiv.insertAdjacentHTML('beforeend', `
                <div class="msg-container bot-container">
                    <div class="bot-avatar-sml">
                        ${this.logoContent}
                    </div>
                    <div class="msg bot-msg">
                        ${formattedResponse}
                        ${sourcesHtml}
                    </div>
                </div>`);

            this.chatHistory.push({ role: 'assistant', content: rawResponse });
            this.scrollToBottom();

        } catch (error) {
            console.error(error);
            const loadingElem = this.shadowRoot.getElementById(loadingId);
            if (loadingElem) loadingElem.remove();

            let cleanError = "I'm sorry, I'm having trouble connecting to the server right now.";

            // If internal error exposed (e.g. from Fallback App)
            if (error.message && (error.message.includes("Application Failed") || error.message.includes("API_KEY"))) {
                cleanError = `⚠️ **Server Error:** ${error.message}`;
            }

            this.historyDiv.insertAdjacentHTML('beforeend', `
                <div class="msg-container bot-container">
                    <div class="bot-avatar-sml" style="background: #ef4444;">!</div>
                    <div class="msg bot-msg">
                        ${cleanError}
                    </div>
                </div>`);
            this.scrollToBottom();
        }
    }

    /**
     * Transforms standard HTML lists containing links into styled interactive cards.
     */
    postProcessHtml(html) {
        const div = document.createElement('div');
        div.innerHTML = html;

        // Process lists into cards
        const uls = div.querySelectorAll('ul');
        uls.forEach(ul => {
            const items = Array.from(ul.children).filter(el => el.tagName === 'LI');
            if (items.length === 0) return;

            // Heuristic: Is this a "Card List"?
            const firstLink = items[0].querySelector('a');
            const firstStrong = items[0].querySelector('strong, b');

            if ((!firstLink || firstLink.closest('ul') !== ul) &&
                (!firstStrong || firstStrong.closest('ul') !== ul)) {
                return;
            }
            ul.classList.add('card-list');
            items.forEach(li => {
                li.classList.add('interactive-card');

                // HEURISTIC: Parent Card (Expandable) vs Leaf Card (Info)
                // Parent Card has a LINK in the title (e.g. Campus Name).
                // Leaf Card has no link (e.g. Service Time), just bold text.

                // HEURISTIC: Default Leaf if no sub-list. Force Leaf if Time Pattern.
                const hasSubList = li.querySelector('ul');
                let isLeaf = !hasSubList;
                const textContent = li.textContent;
                const timePattern = /\b(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Daily|Weekend|Service|Time|AM|PM)\b/i;
                if (hasSubList && timePattern.test(textContent)) isLeaf = true;

                // CASE 1: LEAF CARD (Service Times, Info) -> EVERYTHING is Header
                if (isLeaf) {
                    // Flatten accidental sub-lists (e.g. LLM nested list for times)
                    const subLists = li.querySelectorAll('ul');
                    subLists.forEach(sub => {
                        const items = Array.from(sub.querySelectorAll('li')).map(i => i.textContent.trim());
                        if (items.length > 0) {
                            const text = items.join(', '); // Join times with comma
                            const textNode = document.createTextNode(` ${text}`);
                            sub.parentNode.insertBefore(textNode, sub);
                        }
                        sub.remove();
                    });

                    // Remove stray colons at start of text nodes (cleanup)
                    Array.from(li.childNodes).forEach(node => {
                        if (node.nodeType === 3 && node.nodeValue.trim().startsWith(':')) {
                            node.nodeValue = node.nodeValue.replace(/^\s*:\s*/, ' ');
                        }
                    });

                    // --- LEAF CARD FORMATTING (Unified Style) ---

                    // Check if there is a link to promote to a Header
                    const link = li.querySelector('a');

                    if (link) {
                        // 1. Create Header (Green)
                        const headerDiv = document.createElement('div');
                        headerDiv.className = 'card-header';
                        headerDiv.appendChild(link); // Move link to header

                        // 2. Create Body (White) using remaining content
                        const bodyDiv = document.createElement('div');
                        bodyDiv.className = 'card-body';
                        bodyDiv.style.padding = "20px 22px";
                        bodyDiv.style.fontWeight = "500";
                        bodyDiv.style.display = "block";
                        bodyDiv.style.whiteSpace = "normal"; // Allow wrapping

                        // Capture formatting before regex
                        let htmlContent = li.innerHTML;

                        // Clean up leading separators ( - or : ) since link is gone
                        // This uses a regex on the raw HTML, which might be tricky if the link was first.
                        // Better approach: Move nodes to body first, then clean text nodes.

                        while (li.firstChild) {
                            bodyDiv.appendChild(li.firstChild);
                        }

                        // Clean leading text node in body
                        if (bodyDiv.firstChild && bodyDiv.firstChild.nodeType === 3) {
                            bodyDiv.firstChild.nodeValue = bodyDiv.firstChild.nodeValue.replace(/^[\s:-]+/, '');
                        }

                        // Apply Day Bolding directly to body content
                        const dayRegex = /\b(Sundays?|Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Daily|Weekends?)\b/gi;
                        bodyDiv.innerHTML = bodyDiv.innerHTML.replace(dayRegex, '<span style="font-weight: 800; color: #111827;">$1</span>');

                        // Reassemble LI
                        li.appendChild(headerDiv);
                        if (bodyDiv.innerText.trim().length > 0) {
                            li.appendChild(bodyDiv);
                        }
                    } else {
                        // NO LINK -> Pure Info Card (White Box)
                        const header = document.createElement('div');
                        header.className = 'card-body';
                        header.style.padding = "20px 22px";
                        header.style.fontWeight = "500";
                        header.style.display = "block";
                        header.style.whiteSpace = "normal";

                        let htmlContent = li.innerHTML;
                        const dayRegex = /\b(Sundays?|Mondays?|Tuesdays?|Wednesdays?|Thursdays?|Fridays?|Saturdays?|Daily|Weekends?)\b/gi;
                        htmlContent = htmlContent.replace(dayRegex, '<span style="font-weight: 800; color: #111827;">$1</span>');

                        header.innerHTML = htmlContent;
                        li.innerHTML = '';
                        li.appendChild(header);
                    }
                    return; // Done
                }

                // CASE 2: PARENT CARD (Campus) -> Split Header & Body
                let header = li.querySelector('a'); // Re-select for clarity

                // (Existing Logic for Parent Headers)
                if (!header || header.closest('ul') !== ul) {
                    const strong = li.querySelector(':scope > strong, :scope > b');
                    if (strong) {
                        header = document.createElement('div');
                        header.className = 'card-header';
                        header.innerHTML = `<span>${strong.innerHTML.replace(':', '')}</span>`;
                        strong.remove();
                        li.prepend(header);
                    } else if (header && header.parentNode !== li) {
                        li.prepend(header);
                    }
                } else if (header.parentNode !== li) {
                    li.prepend(header);
                }

                if (header) {
                    // Styled Header Content
                    if (header.tagName === 'A') {
                        const parts = header.innerText.split(':');
                        if (parts.length > 1) {
                            header.innerHTML = `<span><strong>${parts[0]}</strong>${parts.slice(1).join(':')}</span>`;
                        }
                    }

                    // Wrap Body Content
                    const body = document.createElement('div');
                    body.className = 'card-body';

                    // Move remaining children (including the sub-UL) to body
                    while (li.childNodes.length > 1) {
                        const child = li.childNodes[1];
                        if (child.nodeName === 'BR') child.remove();
                        else body.appendChild(child);
                    }
                    li.appendChild(body);

                    // Cleanup Empty Text/P Nodes in Body
                    Array.from(body.childNodes).forEach(node => {
                        if ((node.nodeName === 'P' && !node.innerText.trim()) ||
                            (node.nodeType === 3 && !node.nodeValue.trim())) {
                            node.remove();
                        } else if (node.nodeName === 'P' || node.nodeType === 3) {
                            // CSS cleanup for text
                            if (node.style) { node.style.margin = '0'; node.style.marginBottom = '6px'; }
                        }
                    });
                }

                // Final Check: Does this card have a link? If so, make it clickable.
                if (li.querySelector('a')) {
                    li.classList.add('has-link');
                }
            });
        });

        // Loop for links removed: Handled by Global Interceptor
        return div.innerHTML;
    }
}

customElements.define('church-chatbot', ChurchChatbot);
