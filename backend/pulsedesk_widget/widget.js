/*!
 * PulseDesk Widget v0.2.0 (ITHR-hosted)
 * Embed with:
 *   <script src="https://YOUR-HOST/api/pulsedesk/widget.js"
 *           data-key="WIDGET_KEY" async></script>
 *
 * Adapted from the original standalone PulseDesk MVP to run on the ITHR
 * FastAPI backend — HTTP-only, no Socket.io. Same UX: floating bubble,
 * voice mode (Web Speech API), page context, callback capture. The AI is
 * powered by the ITHR tutor engine (Emergent LLM key), so the widget
 * "knows" about the courses, credentials, and enterprise offering.
 */
(function () {
  var CURRENT_SCRIPT = document.currentScript;
  var WIDGET_KEY = CURRENT_SCRIPT.getAttribute("data-key");
  var API_BASE = CURRENT_SCRIPT.getAttribute("data-api") || new URL(CURRENT_SCRIPT.src).origin;

  if (!WIDGET_KEY) {
    console.error("[PulseDesk] Missing data-key attribute on the widget <script> tag.");
    return;
  }

  var VISITOR_ID_KEY = "pulsedesk_visitor_id";
  var visitorId = null;
  try {
    visitorId = window.localStorage.getItem(VISITOR_ID_KEY);
    if (!visitorId) {
      visitorId = "v_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      window.localStorage.setItem(VISITOR_ID_KEY, visitorId);
    }
  } catch (e) {
    visitorId = "v_" + Math.random().toString(36).slice(2);
  }

  var state = {
    open: false,
    conversationId: null,
    config: null,
    voiceReplies: false,
    listening: false,
    sending: false,
  };

  // ---- Page-context reader (unchanged from PulseDesk MVP) ----
  function getPageContext() {
    var parts = [];
    if (document.title) parts.push("Page title: " + document.title);
    var tagged = document.querySelectorAll("[data-pulsedesk-context]");
    if (tagged.length) {
      tagged.forEach(function (el) {
        parts.push(el.innerText || el.textContent || "");
      });
    } else {
      var h1 = document.querySelector("h1");
      if (h1) parts.push(h1.innerText || h1.textContent || "");
    }
    return parts.join("\n\n").trim().slice(0, 3000);
  }

  // ---- Styles ----
  var style = document.createElement("style");
  style.textContent =
    "#pd-bubble{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;" +
    "background:var(--pd-color,#16335E);box-shadow:0 6px 20px rgba(0,0,0,.25);cursor:pointer;z-index:999999;" +
    "display:flex;align-items:center;justify-content:center;transition:transform .15s ease;}" +
    "#pd-bubble:hover{transform:scale(1.06);}" +
    "#pd-bubble svg{width:28px;height:28px;fill:#fff;}" +
    "#pd-panel{position:fixed;bottom:96px;right:24px;width:360px;max-width:92vw;height:520px;max-height:75vh;" +
    "background:#fff;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.3);z-index:999999;display:none;" +
    "flex-direction:column;overflow:hidden;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}" +
    "#pd-panel.pd-open{display:flex;}" +
    "#pd-header{background:var(--pd-color,#16335E);color:#fff;padding:14px 16px;font-weight:600;font-size:14px;" +
    "display:flex;justify-content:space-between;align-items:center;}" +
    "#pd-close{cursor:pointer;opacity:.8;font-size:20px;line-height:1;padding:0 4px;}" +
    "#pd-messages{flex:1;overflow-y:auto;padding:14px;background:#f7f8fa;}" +
    ".pd-msg{max-width:82%;margin:8px 0;padding:9px 13px;border-radius:12px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word;}" +
    ".pd-msg.visitor{margin-left:auto;background:var(--pd-color,#16335E);color:#fff;border-bottom-right-radius:3px;}" +
    ".pd-msg.ai,.pd-msg.agent{margin-right:auto;background:#fff;color:#1a1a1a;border:1px solid #e5e7eb;border-bottom-left-radius:3px;}" +
    ".pd-msg.system{margin:6px auto;background:#f3f4f6;color:#6b7280;font-size:11px;text-align:center;font-style:italic;max-width:90%;border-radius:8px;padding:6px 10px;}" +
    ".pd-msg .pd-tag{display:block;font-size:10px;opacity:.7;margin-bottom:3px;text-transform:uppercase;letter-spacing:.04em;font-weight:600;}" +
    "#pd-typing{font-size:11px;color:#666;padding:0 14px 6px;display:none;}" +
    "#pd-typing.pd-on{display:block;}" +
    "#pd-typing::after{content:'';display:inline-block;width:14px;text-align:left;animation:pd-dots 1.2s infinite steps(4);}" +
    "@keyframes pd-dots{0%{content:'';}25%{content:'.';}50%{content:'..';}75%{content:'...';}}" +
    "#pd-inputbar{display:flex;border-top:1px solid #e5e7eb;padding:10px;gap:8px;align-items:center;}" +
    "#pd-input{flex:1;border:1px solid #e5e7eb;border-radius:20px;padding:9px 14px;font-size:13px;outline:none;}" +
    "#pd-input:focus{border-color:var(--pd-color,#16335E);}" +
    "#pd-send{background:var(--pd-color,#16335E);color:#fff;border:none;border-radius:20px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .15s;}" +
    "#pd-send:disabled{opacity:.5;cursor:not-allowed;}" +
    "#pd-callback{font-size:11px;color:var(--pd-color,#16335E);text-decoration:underline;cursor:pointer;text-align:center;padding:6px 0;background:#fff;border-top:1px solid #f3f4f6;}" +
    "#pd-voice-toggle{cursor:pointer;font-size:16px;opacity:.85;margin-right:10px;user-select:none;}" +
    "#pd-mic{background:#fff;border:1px solid #e5e7eb;border-radius:50%;width:34px;height:34px;flex:0 0 34px;" +
    "cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px;padding:0;}" +
    "#pd-mic.pd-listening{background:#ffe6e6;border-color:#ff4d4f;animation:pd-pulse 1.1s infinite;}" +
    "@keyframes pd-pulse{0%{box-shadow:0 0 0 0 rgba(255,77,79,.4);}70%{box-shadow:0 0 0 8px rgba(255,77,79,0);}100%{box-shadow:0 0 0 0 rgba(255,77,79,0);}}" +
    "#pd-voice-status{font-size:11px;color:#ff4d4f;padding:0 14px 4px;display:none;text-align:center;}" +
    "#pd-voice-status.pd-on{display:block;}";
  document.head.appendChild(style);

  // ---- DOM ----
  var bubble = document.createElement("div");
  bubble.id = "pd-bubble";
  bubble.setAttribute("data-testid", "pulsedesk-bubble");
  bubble.setAttribute("role", "button");
  bubble.setAttribute("aria-label", "Open chat");
  bubble.innerHTML =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>';
  document.body.appendChild(bubble);

  var panel = document.createElement("div");
  panel.id = "pd-panel";
  panel.setAttribute("data-testid", "pulsedesk-panel");
  panel.innerHTML =
    '<div id="pd-header"><span id="pd-header-title">Chat</span>' +
    '<span><span id="pd-voice-toggle" data-testid="pulsedesk-voice-toggle" title="Turn on spoken replies">&#128264;</span>' +
    '<span id="pd-close" data-testid="pulsedesk-close">&times;</span></span></div>' +
    '<div id="pd-messages" data-testid="pulsedesk-messages"></div>' +
    '<div id="pd-typing">Assistant is typing</div>' +
    '<div id="pd-voice-status">Listening…</div>' +
    '<div id="pd-callback" data-testid="pulsedesk-callback">Prefer a call? Request a callback</div>' +
    '<div id="pd-inputbar"><button id="pd-mic" data-testid="pulsedesk-mic" title="Speak instead of typing">&#127908;</button>' +
    '<input id="pd-input" data-testid="pulsedesk-input" type="text" placeholder="Type or tap the mic to speak…" />' +
    '<button id="pd-send" data-testid="pulsedesk-send">Send</button></div>';
  document.body.appendChild(panel);

  var messagesEl = panel.querySelector("#pd-messages");
  var typingEl = panel.querySelector("#pd-typing");
  var inputEl = panel.querySelector("#pd-input");
  var sendBtn = panel.querySelector("#pd-send");

  function appendMessage(m) {
    var div = document.createElement("div");
    div.className = "pd-msg " + (m.sender_type || m.senderType || "visitor");
    var kind = m.sender_type || m.senderType;
    var tag = kind === "ai" ? "AI Assistant" : kind === "agent" ? "Team" : "";
    div.innerHTML = (tag ? '<span class="pd-tag">' + tag + "</span>" : "") + escapeHtml(m.text);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setTyping(on) {
    typingEl.classList.toggle("pd-on", !!on);
  }

  // ---- HTTP helpers ----

  function apiPost(path, body) {
    return fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error(t || ("HTTP " + r.status)); });
      return r.json();
    });
  }

  function apiGet(path) {
    return fetch(API_BASE + path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  // ---- Interactions ----

  bubble.addEventListener("click", function () {
    state.open = !state.open;
    panel.classList.toggle("pd-open", state.open);
    if (state.open) {
      inputEl.focus();
      if (!state.conversationId) join();
    }
  });
  panel.querySelector("#pd-close").addEventListener("click", function () {
    state.open = false;
    panel.classList.remove("pd-open");
  });

  panel.querySelector("#pd-callback").addEventListener("click", function () {
    var phone = window.prompt("What's the best number to reach you on?");
    if (!phone || !phone.trim()) return;
    apiPost("/api/pulsedesk/visitor/callback", {
      widget_key: WIDGET_KEY,
      visitor_id: visitorId,
      phone_number: phone.trim(),
    }).then(function () {
      appendMessage({ sender_type: "system", text: "Callback requested — someone will call " + phone + " shortly." });
    }).catch(function (err) {
      console.error("[PulseDesk] callback failed:", err.message);
      appendMessage({ sender_type: "system", text: "Couldn't record the callback — please email us instead." });
    });
  });

  function sendMessage() {
    var text = inputEl.value.trim();
    if (!text || state.sending) return;
    state.sending = true;
    sendBtn.disabled = true;

    // Optimistic visitor render
    appendMessage({ sender_type: "visitor", text: text });
    inputEl.value = "";
    setTyping(true);

    apiPost("/api/pulsedesk/visitor/message", {
      widget_key: WIDGET_KEY,
      visitor_id: visitorId,
      text: text,
      page_context: getPageContext(),
    }).then(function (res) {
      setTyping(false);
      if (res.ai_message) {
        appendMessage(res.ai_message);
        if (state.voiceReplies) speak(res.ai_message.text);
      }
      // If a human owns the conversation, the visitor's message is queued
      // and no AI reply comes back — show a system hint so the visitor
      // knows their message landed.
      if (!res.ai_message && res.status === "agent") {
        appendMessage({ sender_type: "system", text: "Message received — a team member will reply shortly." });
      }
    }).catch(function (err) {
      setTyping(false);
      console.error("[PulseDesk] send failed:", err.message);
      appendMessage({ sender_type: "system", text: "Couldn't reach the assistant — please try again in a moment." });
    }).finally(function () {
      state.sending = false;
      sendBtn.disabled = false;
    });
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // ---- Voice: speech-to-text ----
  var micBtn = panel.querySelector("#pd-mic");
  var voiceStatusEl = panel.querySelector("#pd-voice-status");
  var SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognizer = null;
  if (!SpeechRecognitionImpl) {
    micBtn.title = "Voice input isn't supported in this browser — try Chrome or Edge";
    micBtn.style.opacity = "0.4";
  } else {
    recognizer = new SpeechRecognitionImpl();
    recognizer.continuous = false;
    recognizer.interimResults = false;
    recognizer.maxAlternatives = 1;
    recognizer.onstart = function () {
      state.listening = true;
      micBtn.classList.add("pd-listening");
      voiceStatusEl.classList.add("pd-on");
    };
    recognizer.onend = function () {
      state.listening = false;
      micBtn.classList.remove("pd-listening");
      voiceStatusEl.classList.remove("pd-on");
    };
    recognizer.onerror = function (e) {
      console.warn("[PulseDesk] speech recognition error:", e.error);
    };
    recognizer.onresult = function (e) {
      inputEl.value = e.results[0][0].transcript;
      sendMessage();
    };
  }
  micBtn.addEventListener("click", function () {
    if (!recognizer) return;
    if (state.listening) recognizer.stop();
    else {
      try {
        recognizer.lang = document.documentElement.lang || "en-US";
        recognizer.start();
      } catch (_e) { /* already started */ }
    }
  });

  // ---- Voice: text-to-speech ----
  var voiceToggleEl = panel.querySelector("#pd-voice-toggle");
  function updateVoiceToggleUi() {
    voiceToggleEl.style.opacity = state.voiceReplies ? "1" : "0.5";
    voiceToggleEl.title = state.voiceReplies ? "Spoken replies: on (tap to turn off)" : "Turn on spoken replies";
  }
  updateVoiceToggleUi();
  voiceToggleEl.addEventListener("click", function () {
    state.voiceReplies = !state.voiceReplies;
    updateVoiceToggleUi();
    if (!state.voiceReplies && window.speechSynthesis) window.speechSynthesis.cancel();
  });
  function speak(text) {
    if (!state.voiceReplies || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    var utter = new SpeechSynthesisUtterance(text);
    utter.lang = document.documentElement.lang || "en-US";
    utter.onend = function () {
      if (state.voiceReplies && recognizer && !state.listening) {
        try { recognizer.start(); } catch (_e) { /* ignore */ }
      }
    };
    window.speechSynthesis.speak(utter);
  }

  // ---- Boot: fetch config, then join ----
  apiGet("/api/pulsedesk/config/" + encodeURIComponent(WIDGET_KEY))
    .then(function (config) {
      state.config = config;
      panel.style.setProperty("--pd-color", config.primaryColor || "#16335E");
      bubble.style.setProperty("--pd-color", config.primaryColor || "#16335E");
      panel.querySelector("#pd-header-title").textContent = config.name || "Chat with us";
    })
    .catch(function (err) {
      console.error("[PulseDesk] failed to load widget config:", err.message);
    });

  function join() {
    apiPost("/api/pulsedesk/visitor/join", {
      widget_key: WIDGET_KEY,
      visitor_id: visitorId,
      visitor_meta: { url: location.href },
      page_context: getPageContext(),
    }).then(function (data) {
      state.conversationId = data.conversation_id;
      if (data.messages && data.messages.length) {
        data.messages.forEach(appendMessage);
      } else if (data.greeting) {
        appendMessage({ sender_type: "ai", text: data.greeting });
      }
    }).catch(function (err) {
      console.error("[PulseDesk] join failed:", err.message);
      appendMessage({ sender_type: "system", text: "Couldn't reach the assistant — please try again in a moment." });
    });
  }
})();
