/**
 * widget.js — BDU CIMS Chat Widget (v2 — XSS-fixed)
 * Embeddable floating chat bubble with safe text rendering.
 *
 * Changes from v1:
 *  - XSS FIX: innerHTML replaced with safe rendering (textContent + sanitized markdown)
 *  - API URL: relative path (no hardcoded localhost)
 *  - Better error handling
 */

const API_URL = "/chat";

(function () {
    // Prevent duplicate injections
    if (document.getElementById('bdu-cims-host')) return;

    // --- Safe text rendering (XSS prevention) ---
    function sanitizeAndRender(text) {
        // Convert newlines to <br> safely, escape HTML entities
        const div = document.createElement('div');
        const lines = text.split('\n');
        lines.forEach((line, index) => {
            // Process each line for basic markdown
            const lineEl = document.createElement('span');

            // Handle bold: **text** → <strong>text</strong>
            const parts = line.split(/(\*\*[^*]+\*\*)/g);
            parts.forEach(part => {
                if (part.startsWith('**') && part.endsWith('**')) {
                    const strong = document.createElement('strong');
                    strong.textContent = part.slice(2, -2);
                    lineEl.appendChild(strong);
                } else {
                    lineEl.appendChild(document.createTextNode(part));
                }
            });

            div.appendChild(lineEl);
            if (index < lines.length - 1) {
                div.appendChild(document.createElement('br'));
            }
        });
        return div;
    }

    // --- HOST & SHADOW DOM ---
    const host = document.createElement('div');
    host.id = 'bdu-cims-host';
    host.style.position = 'fixed';
    host.style.bottom = '20px';
    host.style.right = '20px';
    host.style.zIndex = '999999';
    host.style.fontFamily = 'Segoe UI, Roboto, Helvetica, Arial, sans-serif';
    document.body.appendChild(host);

    const shadow = host.attachShadow({ mode: 'open' });

    // --- STYLES ---
    const style = `
        /* ANIMATIONS */
        @keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }
        
        /* CHAT BUTTON */
        .chat-btn { 
            background: #00346a; color: white; border: none; 
            width: 60px; height: 60px; border-radius: 50%; 
            cursor: pointer; font-size: 28px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex; align-items: center; justify-content: center;
        }
        .chat-btn:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(0,0,0,0.25); }

        /* CHAT WINDOW */
        .window { 
            display: none; position: absolute; bottom: 80px; right: 0; 
            width: 380px; height: 600px; background: white; 
            border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.15); 
            flex-direction: column; overflow: hidden; 
            border: 1px solid rgba(0,0,0,0.1);
            animation: slideIn 0.3s ease-out;
            transition: width 0.3s, height 0.3s, max-width 0.3s;
        }

        /* EXPANDED MODE (50% Width, 70% Height) */
        .window.expanded {
            width: 50vw;
            height: 70vh;
            max-width: 900px;
        }

        /* HEADER */
        .header { 
            background: #00346a; color: white; padding: 15px 20px; 
            font-weight: 600; display: flex; justify-content: space-between; align-items: center; 
        }
        .header-controls span { cursor: pointer; margin-left: 15px; font-size: 18px; opacity: 0.8; }
        .header-controls span:hover { opacity: 1; }

        /* MESSAGES AREA */
        .msgs { 
            flex: 1; padding: 20px; overflow-y: auto; background: #f8f9fa; 
            display: flex; flex-direction: column; gap: 12px; 
        }
        
        /* BUBBLE */
        .msg { 
            padding: 12px 16px; border-radius: 12px; max-width: 85%; 
            font-size: 15px; line-height: 1.5; word-wrap: break-word;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .bot { background: white; border: 1px solid #eee; align-self: flex-start; color: #1a1a1a; }
        .user { background: #00346a; color: white; align-self: flex-end; }
        
        /* SOURCE TAG (Appears at bottom) */
        .source-tag {
            font-size: 11px; color: #666; margin-top: 8px; 
            display: block; font-style: italic; border-top: 1px solid #eee; padding-top: 6px;
        }

        /* TYPING ANIMATION (The 3 dots) */
        .typing-indicator span {
            display: inline-block; width: 6px; height: 6px; background-color: #888; 
            border-radius: 50%; animation: pulse 1.5s infinite; margin: 0 2px;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

        /* SUGGESTION BUTTONS */
        .suggestions { 
            display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0; 
            justify-content: center;
        }
        .suggestion-btn {
            background: #f0f0f0; border: 1px solid #ddd; 
            padding: 8px 14px; border-radius: 20px; 
            cursor: pointer; font-size: 13px; color: #333;
            transition: all 0.2s;
        }
        .suggestion-btn:hover {
            background: #00346a; color: white; border-color: #00346a;
            transform: translateY(-2px);
        }

        /* INPUT AREA */
        .input-area { padding: 15px; background: white; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { 
            flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; 
            outline: none; transition: border 0.2s; background: #f9f9f9;
        }
        input:focus { border-color: #00346a; background: white; }
        input:disabled { opacity: 0.6; cursor: not-allowed; }
        button { background: none; border: none; cursor: pointer; font-size: 20px; color: #00346a; }
        button:disabled { opacity: 0.4; cursor: not-allowed; }
    `;

    shadow.innerHTML = `<style>${style}</style>
    <div class="window" id="win">
        <div class="header">
            <span>🎓 CIMS Assistant</span>
            <div class="header-controls">
                <span id="expand" title="Expand">⤢</span>
                <span id="minimize" title="Close">✖</span>
            </div>
        </div>
        <div class="msgs" id="list">
            <div class="msg bot">
                I'm CIMS. 👋 How can I assist you with BDU admissions, courses, or campus information?
            </div>
            <div class="suggestions" id="suggestions">
                <button class="suggestion-btn" data-query="All courses offered at BDU">📚 All Courses</button>
                <button class="suggestion-btn" data-query="What are the fee details?">💰 Fee Details</button>
                <button class="suggestion-btn" data-query="How do I apply for admission?">📝 Admission Process</button>
                <button class="suggestion-btn" data-query="Contact details">📞 Contact</button>
            </div>
        </div>
        <div class="input-area">
            <input type="text" id="inp" placeholder="Type your question..." autocomplete="off">
            <button id="send">➤</button>
        </div>
    </div>
    <button class="chat-btn" id="btn">💬</button>`;

    // --- LOGIC ---
    const win = shadow.getElementById('win');
    const list = shadow.getElementById('list');
    const inp = shadow.getElementById('inp');
    const btn = shadow.getElementById('btn');
    let isExpanded = false;

    // Toggle Window
    btn.onclick = () => {
        if (win.style.display === 'flex') {
            win.style.display = 'none';
        } else {
            win.style.display = 'flex';
            setTimeout(() => inp.focus(), 100);
        }
    };
    shadow.getElementById('minimize').onclick = () => win.style.display = 'none';

    // Expand 
    shadow.getElementById('expand').onclick = () => {
        isExpanded = !isExpanded;
        if (isExpanded) win.classList.add('expanded');
        else win.classList.remove('expanded');
    };

    // Suggestion button handlers
    const suggestionBtns = shadow.querySelectorAll('.suggestion-btn');
    suggestionBtns.forEach(btn => {
        btn.onclick = () => {
            inp.value = btn.dataset.query;
            send();
            shadow.getElementById('suggestions').style.display = 'none';
        };
    });

    async function send() {
        const txt = inp.value.trim();
        if (!txt) return;

        // Disable input to prevent multiple queries
        inp.disabled = true;
        shadow.getElementById('send').disabled = true;

        // User Message — XSS SAFE: using textContent, not innerHTML
        const userMsg = document.createElement('div');
        userMsg.className = 'msg user';
        userMsg.textContent = txt;
        list.appendChild(userMsg);
        inp.value = '';
        list.scrollTop = list.scrollHeight;

        // Bot Bubble with Typing Animation
        const botMsg = document.createElement('div');
        botMsg.className = 'msg bot';
        botMsg.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
        list.appendChild(botMsg);
        list.scrollTop = list.scrollHeight;

        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: txt })
            });

            const data = await response.json();

            // XSS SAFE: Clear and use safe renderer
            botMsg.innerHTML = '';
            const rendered = sanitizeAndRender(data.answer || 'No response received.');
            botMsg.appendChild(rendered);

            // Add source tag safely
            if (data.sources && data.sources.length > 0) {
                const sourceTag = document.createElement('span');
                sourceTag.className = 'source-tag';
                sourceTag.textContent = 'From official BDU sources';
                botMsg.appendChild(sourceTag);
            }

            list.scrollTop = list.scrollHeight;

        } catch (e) {
            botMsg.innerHTML = '';
            botMsg.textContent = '⚠️ Connection Error. Ensure the server is running.';
        } finally {
            inp.disabled = false;
            shadow.getElementById('send').disabled = false;
            inp.focus();
        }
    }

    shadow.getElementById('send').onclick = send;
    inp.onkeypress = (e) => { if (e.key === 'Enter') send(); };
})();
