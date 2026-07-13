// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  CONFIGURATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const API = "http://localhost:8000";
let busy = false;
let sessions = [];
try { sessions = JSON.parse(localStorage.getItem('Manlayag_sessions') || '[]'); } catch { sessions = []; }
let currentSession = null;
let typingTimeout = null;

const $ = id => document.getElementById(id);

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  STATUS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async function checkStatus() {
    try {
        const res = await fetch(`${API}/api/status`);
        if (res.ok) {
            const d = await res.json();
            const docs = d.documents || 0;
            const vecs = d.vectors || 0;
            $('statusDot').className = 'status-dot ok';
            $('statusText').textContent = `Connected · ${docs} doc${docs !== 1 ? 's' : ''} · ${vecs} vectors`;
        } else {
            throw new Error();
        }
    } catch {
        $('statusDot').className = 'status-dot err';
        $('statusText').textContent = 'Cannot connect to server — make sure app.py is running';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  TYPING INDICATOR WITH TIMEOUT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function showTyping() {
    const wrap = $('typingWrap');
    wrap.classList.add('active');
    $('messages').scrollTop = $('messages').scrollHeight;
    
    if (typingTimeout) clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        hideTyping();
        addMessage('⚠️ Request timed out. Please try again.', false);
        busy = false;
        $('sendBtn').disabled = false;
    }, 30000);
}

function hideTyping() {
    const wrap = $('typingWrap');
    wrap.classList.remove('active');
    if (typingTimeout) {
        clearTimeout(typingTimeout);
        typingTimeout = null;
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  CLEAN CONTENT - REMOVE SOURCE REFERENCES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function cleanContent(text) {
    if (!text) return '';
    
    // Remove any "Source:" lines
    let cleaned = text.replace(/Source:.*$/gm, '');
    
    // Remove any bullet points that look like lesson titles
    cleaned = cleaned.replace(/^[\s]*[-•*]\s*[^\n]*$/gm, '');
    
    // Remove any "[Source: ...]" patterns
    cleaned = cleaned.replace(/\[Source:.*?\]/g, '');
    
    // Remove any extra whitespace
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
    
    // If the content contains "does not contain enough information", 
    // make sure it's the only thing displayed
    if (cleaned.toLowerCase().includes('does not contain enough information')) {
        cleaned = 'The lesson does not contain enough information to answer this question.';
    }
    
    return cleaned.trim();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  ADD MESSAGE - FIXED: NO SOURCE DISPLAY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function addMessage(text, isUser, refs = [], isError = false) {
    hideWelcome();
    const msgs = $('messages');

    // --- FIX: Clean the text to remove any source references ---
    const cleanedText = cleanContent(text);

    const row = document.createElement('div');
    row.className = `msg-row ${isUser ? 'user' : 'ai'}`;

    const av = document.createElement('div');
    av.className = `avatar ${isUser ? 'user-av' : 'ai-av'}`;
    av.textContent = isUser ? 'U' : 'S';

    const bub = document.createElement('div');
    bub.className = 'bubble';
    
    if (isError) {
        bub.style.background = '#fef2f2';
        bub.style.border = '1px solid #fca5a5';
        bub.style.color = '#dc2626';
    }
    
    bub.innerHTML = cleanedText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');

    // --- FIX: Completely remove source tags display ---
    // No source tags will be shown

    row.appendChild(av);
    row.appendChild(bub);
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  SEND MESSAGE
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function sendMessage() {
    const input = $('chatInput');
    const text = input.value.trim();
    if (!text || busy) return;
    input.value = '';
    input.style.height = 'auto';
    ask(text);
}

async function ask(question) {
    if (busy) return;
    busy = true;
    $('sendBtn').disabled = true;
    setSuggestions([]);

    addMessage(question, true);
    showTyping();

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);

        const res = await fetch(`${API}/api/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question,
                course_id: 'ALL',
                lesson_id: 'ALL',
                user_id: 'student001'
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        hideTyping();

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            addMessage(`❌ Error: ${err.error || err.message || 'Server error. Check terminal.'}`, false, [], true);
            restoreSuggestions();
        } else {
            const d = await res.json();
            
            // --- FIX: Clean the answer before displaying ---
            const cleanAnswer = cleanContent(d.answer);
            
            // --- FIX: Don't pass references to avoid display ---
            addMessage(cleanAnswer, false, []);  // Empty references array
            
            setSuggestions(d.suggestions || []);
            setTopic(d.topic || question.slice(0, 60));
            
            // --- FIX: Save without references ---
            saveSession(question, cleanAnswer, []);
            checkStatus();
        }
    } catch (err) {
        hideTyping();
        if (err.name === 'AbortError') {
            addMessage('⏱️ Request timed out. Please try again.', false, [], true);
        } else {
            addMessage('❌ Cannot reach the server. Make sure Python is running.', false, [], true);
        }
        restoreSuggestions();
    }

    busy = false;
    $('sendBtn').disabled = false;
    $('chatInput').focus();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  REST OF YOUR EXISTING FUNCTIONS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ── Session recents ───────────────────────────────────────
function saveSession(question, answer, refs = []) {
    const label = question.slice(0, 44) + (question.length > 44 ? '…' : '');
    if (!currentSession) {
        currentSession = { id: Date.now(), label, messages: [] };
        sessions.unshift(currentSession);
    }
    currentSession.messages.push({ q: question, a: answer, refs: [] }); // Always empty refs
    localStorage.setItem('surodrag_sessions', JSON.stringify(sessions));
    renderRecents();
}

function loadSession(session) {
    if (busy) return;
    currentSession = session;
    renderRecents();
    
    $('messages').innerHTML = '';
    setTopic(session.label);
    
    session.messages.forEach(msg => {
        addMessage(msg.q, true);
        // Clean answer when loading from session
        const cleanAnswer = cleanContent(msg.a);
        addMessage(cleanAnswer, false, []); // Always empty refs
    });
}

function renderRecents() {
    const el = $('chatRecents');
    const emp = $('recentsEmpty');
    if (!sessions.length) { if (emp) emp.style.display = ''; return; }
    if (el) el.innerHTML = '';
    sessions.forEach((s, i) => {
        const item = document.createElement('div');
        item.className = 'recent-item' + (s === currentSession ? ' active' : '');
        item.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            ${s.label}`;
        item.onclick = () => { loadSession(sessions[i]); };
        if (el) el.appendChild(item);
    });
}

// Add missing functions if not present
function hideWelcome() {
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.style.display = 'none';
}

function setSuggestions(suggestions) {
    const el = $('suggestionsRow');
    if (!el) return;
    el.innerHTML = '';
    if (!suggestions || !suggestions.length) {
        el.classList.remove('show');
        return;
    }
    suggestions.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'suggestion-chip';
        btn.textContent = s;
        btn.onclick = () => {
            $('chatInput').value = s;
            sendMessage();
        };
        el.appendChild(btn);
    });
    el.classList.add('show');
}

function restoreSuggestions() {
    const suggestionsEl = $('suggestionsRow');
    if (suggestionsEl) {
        suggestionsEl.innerHTML = '';
        suggestionsEl.classList.remove('show');
    }
}

function setTopic(topic) {
    const el = $('currentTopic');
    if (el) el.textContent = topic;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  EXPORT CHAT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function exportChat() {
    const messages = document.querySelectorAll('.msg-row');
    if (!messages.length) {
        alert('No messages to export.');
        return;
    }

    let exportText = '🧠 SurodRAG Assistant - Caraga State University\n';
    exportText += '='.repeat(40) + '\n';
    exportText += `📅 ${new Date().toLocaleString()}\n`;
    exportText += '='.repeat(40) + '\n\n';
    
    messages.forEach(msg => {
        const isUser = msg.classList.contains('user');
        const bubble = msg.querySelector('.bubble');
        const text = bubble ? bubble.textContent.trim() : '';
        const sender = isUser ? 'You' : 'SurodRAG';
        exportText += `[${sender}]: ${text}\n\n`;
    });

    const blob = new Blob([exportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Manlayag_chat_${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  TOAST NOTIFICATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function showToast(message) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.style.cssText = `
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: #1a1a2e;
            color: white;
            padding: 12px 24px;
            border-radius: 12px;
            font-size: 14px;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            pointer-events: none;
        `;
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.opacity = '1';
    setTimeout(() => {
        toast.style.opacity = '0';
    }, 3000);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  INIT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    setInterval(checkStatus, 30000);
    renderRecents();
    
    // Enter key to send
    $('chatInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    $('chatInput').addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
});