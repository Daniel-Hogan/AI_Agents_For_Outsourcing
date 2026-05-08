(function () {
  var STORAGE_KEY = "schedulerai.assistant.threadId";
  var OPEN_STORAGE_KEY = "schedulerai.assistant.isOpen";
  var SIZE_STORAGE_KEY = "schedulerai.assistant.size";
  var CLOSE_ANIMATION_MS = 180;
  var DEFAULT_PANEL_WIDTH = 420;
  var DEFAULT_PANEL_HEIGHT = 720;
  var MIN_PANEL_WIDTH = 360;
  var MIN_PANEL_HEIGHT = 500;

  function requestJson(url, options) {
    var requestOptions = options || {};
    var headers = new Headers(requestOptions.headers || {});
    headers.set("Accept", "application/json");

    if (requestOptions.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    return window.fetch(url, {
      method: requestOptions.method || "GET",
      headers: headers,
      body: requestOptions.body,
      credentials: "same-origin"
    }).then(function (response) {
      var contentType = response.headers.get("content-type") || "";
      var payloadPromise = contentType.indexOf("application/json") >= 0 ? response.json() : Promise.resolve(null);
      return payloadPromise.then(function (payload) {
        if (!response.ok) {
          var detail = payload && payload.detail;
          var message = typeof detail === "string" ? detail : "Assistant request failed";
          var error = new Error(message);
          error.response = response;
          error.payload = payload;
          throw error;
        }
        return payload;
      });
    });
  }

  function getStoredThreadId() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function setStoredThreadId(threadId) {
    try {
      if (threadId) {
        window.localStorage.setItem(STORAGE_KEY, String(threadId));
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch (error) {
    }
  }

  function getStoredOpenState() {
    try {
      return window.localStorage.getItem(OPEN_STORAGE_KEY) === "true";
    } catch (error) {
      return false;
    }
  }

  function setStoredOpenState(isOpen) {
    try {
      window.localStorage.setItem(OPEN_STORAGE_KEY, isOpen ? "true" : "false");
    } catch (error) {
    }
  }

  function getStoredPanelSize() {
    try {
      var parsed = JSON.parse(window.localStorage.getItem(SIZE_STORAGE_KEY) || "null");
      if (!parsed || typeof parsed.width !== "number" || typeof parsed.height !== "number") {
        return null;
      }
      return parsed;
    } catch (error) {
      return null;
    }
  }

  function setStoredPanelSize(size) {
    try {
      window.localStorage.setItem(SIZE_STORAGE_KEY, JSON.stringify(size));
    } catch (error) {
    }
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function formatDateTime(value) {
    if (!value) {
      return "";
    }

    var parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }

    return parsed.toLocaleString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit"
    });
  }

  function formatActionType(value) {
    if (value === "create_meeting") {
      return "Create meeting";
    }
    if (value === "update_meeting") {
      return "Update meeting";
    }
    if (value === "cancel_meeting") {
      return "Cancel meeting";
    }
    return "Meeting action";
  }

  function createEl(tagName, className, text) {
    var element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (text !== undefined && text !== null) {
      element.textContent = text;
    }
    return element;
  }

  function createDetailRow(label, value) {
    if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)) {
      return null;
    }

    var row = createEl("div", "assistant-chat-detail-row");
    row.appendChild(createEl("span", "assistant-chat-detail-label", label));
    row.appendChild(createEl("strong", "assistant-chat-detail-value", Array.isArray(value) ? value.join(", ") : String(value)));
    return row;
  }

  function draftTitle(draft) {
    var payload = draft && draft.payload ? draft.payload : {};
    if (draft.action_type === "cancel_meeting") {
      return "Cancel meeting #" + (draft.target_meeting_id || payload.meeting_id || draft.id);
    }
    return payload.title || ("Meeting #" + (draft.target_meeting_id || payload.meeting_id || draft.id));
  }

  function setupAssistantChat(root) {
    var mode = root.getAttribute("data-assistant-chat-mode") || "drawer";
    var isPage = mode === "page";
    var openButton = root.querySelector("[data-assistant-open]");
    var newButton = root.querySelector("[data-assistant-new]");
    var closeButton = root.querySelector("[data-assistant-close]");
    var scrim = root.querySelector("[data-assistant-scrim]");
    var panel = root.querySelector("[data-assistant-panel]");
    var resizeHandle = root.querySelector("[data-assistant-resize]");
    var status = root.querySelector("[data-assistant-status]");
    var messages = root.querySelector("[data-assistant-messages]");
    var form = root.querySelector("[data-assistant-form]");
    var input = root.querySelector("[data-assistant-input]");
    var sendButton = root.querySelector("[data-assistant-send]");
    var candidatesSection = root.querySelector("[data-assistant-candidates]");
    var candidateList = root.querySelector("[data-assistant-candidate-list]");
    var draftSection = root.querySelector("[data-assistant-draft]");
    var draftCard = root.querySelector("[data-assistant-draft-card]");
    var confirmButton = root.querySelector("[data-assistant-confirm]");
    var discardButton = root.querySelector("[data-assistant-discard]");

    if (!panel || !status || !messages || !form || !input || !sendButton || !candidatesSection || !candidateList || !draftSection || !draftCard || !confirmButton || !discardButton) {
      return;
    }

    var state = {
      threadId: getStoredThreadId(),
      initialized: false,
      isOpen: isPage,
      isBusy: false,
      selectedUserIds: [],
      pendingDraftId: null,
      closeTimer: null,
      resizeStart: null
    };

    function maxPanelWidth() {
      return Math.max(MIN_PANEL_WIDTH, window.innerWidth - 48);
    }

    function maxPanelHeight() {
      return Math.max(MIN_PANEL_HEIGHT, window.innerHeight - 96);
    }

    function applyPanelSize(size) {
      if (!size || window.innerWidth <= 640) {
        return;
      }

      var width = clamp(size.width || DEFAULT_PANEL_WIDTH, MIN_PANEL_WIDTH, maxPanelWidth());
      var height = clamp(size.height || DEFAULT_PANEL_HEIGHT, MIN_PANEL_HEIGHT, maxPanelHeight());
      panel.style.setProperty("--assistant-panel-width", width + "px");
      panel.style.setProperty("--assistant-panel-height", height + "px");
    }

    function loadPanelSize() {
      applyPanelSize(getStoredPanelSize() || { width: DEFAULT_PANEL_WIDTH, height: DEFAULT_PANEL_HEIGHT });
    }

    function setStatus(message, isError) {
      status.textContent = message;
      status.classList.toggle("is-error", Boolean(isError));
    }

    function setBusy(isBusy) {
      state.isBusy = isBusy;
      sendButton.disabled = isBusy;
      confirmButton.disabled = isBusy || !state.pendingDraftId;
      discardButton.disabled = isBusy || !state.pendingDraftId;
      root.classList.toggle("is-loading", isBusy);
    }

    function scrollMessages() {
      messages.scrollTop = messages.scrollHeight;
    }

    function renderWelcome() {
      messages.innerHTML = "";
      appendMessage("assistant", "Hi, I can help draft meetings from plain English. Try something like: Schedule a remote planning meeting next Monday at 7 PM with Ben and Alan.");
    }

    function appendMessage(role, content, createdAt) {
      if (!content) {
        return;
      }

      var article = createEl("article", "assistant-chat-message assistant-chat-message-" + role);
      var label = createEl("span", "assistant-chat-message-label", role === "user" ? "You" : "Scheduler AI");
      var bubble = createEl("div", "assistant-chat-message-bubble", content);
      article.appendChild(label);
      article.appendChild(bubble);

      if (createdAt) {
        article.appendChild(createEl("time", "assistant-chat-message-time", formatDateTime(createdAt)));
      }

      messages.appendChild(article);
      scrollMessages();
    }

    function createInlineSection(className, titleText, helperText) {
      var section = createEl("section", className);
      var head = createEl("div", "assistant-chat-section-head");
      head.appendChild(createEl("h3", "", titleText));
      head.appendChild(createEl("p", "", helperText));
      section.appendChild(head);
      return section;
    }

    function resetResponseExtras() {
      state.selectedUserIds = [];
      candidateList.innerHTML = "";
      candidatesSection.hidden = true;
      state.pendingDraftId = null;
      draftCard.innerHTML = "";
      draftSection.hidden = true;
      setBusy(state.isBusy);
    }

    function renderCandidates(candidates) {
      candidateList.innerHTML = "";
      state.selectedUserIds = [];

      if (!candidates || !candidates.length) {
        candidatesSection.hidden = true;
        return;
      }

      candidates.forEach(function (candidate) {
        candidateList.appendChild(createCandidateOption(candidate));
      });

      candidatesSection.hidden = false;
      var inline = createInlineSection("assistant-chat-candidates assistant-chat-inline-card", "Who did you mean?", "Select the right people, then send a short follow-up.");
      var inlineList = createEl("div", "assistant-chat-candidate-list");
      candidates.forEach(function (candidate) {
        inlineList.appendChild(createCandidateOption(candidate));
      });
      inline.appendChild(inlineList);
      messages.appendChild(inline);
      scrollMessages();
    }

    function createCandidateOption(candidate) {
      var label = document.createElement("label");
      label.className = "assistant-chat-candidate";

      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = String(candidate.user_id);
      checkbox.addEventListener("change", function () {
        var userId = Number(candidate.user_id);
        if (checkbox.checked) {
          if (state.selectedUserIds.indexOf(userId) === -1) {
            state.selectedUserIds.push(userId);
          }
        } else {
          state.selectedUserIds = state.selectedUserIds.filter(function (value) {
            return value !== userId;
          });
        }
      });

      var copy = createEl("span", "assistant-chat-candidate-copy");
      copy.appendChild(createEl("strong", "", candidate.display_name || candidate.email));
      copy.appendChild(createEl("small", "", candidate.email));

      label.appendChild(checkbox);
      label.appendChild(copy);
      return label;
    }

    function renderDraft(draft) {
      state.pendingDraftId = draft && draft.id ? draft.id : null;
      draftCard.innerHTML = "";

      if (!draft) {
        draftSection.hidden = true;
        setBusy(state.isBusy);
        return;
      }

      var payload = draft.payload || {};
      var title = createEl("h4", "", draftTitle(draft));
      var action = createEl("p", "assistant-chat-draft-type", formatActionType(draft.action_type));
      var rows = createEl("div", "assistant-chat-detail-grid");
      var detailRows = [
        createDetailRow("Starts", formatDateTime(payload.start_time)),
        createDetailRow("Ends", formatDateTime(payload.end_time)),
        createDetailRow("Location", payload.location),
        createDetailRow("Type", payload.meeting_type === "virtual" ? "Remote" : "In person"),
        createDetailRow("Attendees", payload.attendee_emails || []),
        createDetailRow("Meeting ID", payload.meeting_id || draft.target_meeting_id)
      ];

      draftCard.appendChild(action);
      draftCard.appendChild(title);
      detailRows.forEach(function (row) {
        if (row) {
          rows.appendChild(row);
        }
      });
      draftCard.appendChild(rows);

      draftSection.hidden = false;
      var inline = createInlineSection("assistant-chat-draft assistant-chat-inline-card", "Draft ready", "Review this before anything is saved.");
      var inlineCard = draftCard.cloneNode(true);
      var inlineActions = createEl("div", "assistant-chat-draft-actions");
      var inlineConfirm = createEl("button", "btn btn-primary btn-inline", "Confirm");
      var inlineDiscard = createEl("button", "btn btn-soft btn-inline", "Discard");
      inlineConfirm.type = "button";
      inlineDiscard.type = "button";
      inlineConfirm.addEventListener("click", confirmDraft);
      inlineDiscard.addEventListener("click", discardDraft);
      inlineActions.appendChild(inlineConfirm);
      inlineActions.appendChild(inlineDiscard);
      inline.appendChild(inlineCard);
      inline.appendChild(inlineActions);
      messages.appendChild(inline);
      scrollMessages();
      setBusy(state.isBusy);
    }

    function renderCompletedAction(action) {
      if (!action) {
        return;
      }

      var meetingId = action.id || action.meeting_id;
      var wrapper = createEl("div", "assistant-chat-complete");
      wrapper.appendChild(createEl("strong", "", "Calendar updated"));
      wrapper.appendChild(createEl("p", "", action.title ? action.title : "Your meeting action is complete."));
      if (meetingId) {
        var link = document.createElement("a");
        link.href = "/meetings/" + meetingId;
        link.className = "btn btn-soft btn-inline";
        link.textContent = "Open meeting";
        wrapper.appendChild(link);
      }
      messages.appendChild(wrapper);
      scrollMessages();
    }

    function renderThreadDetail(detail) {
      var threadMessages = detail && detail.messages ? detail.messages : [];
      messages.innerHTML = "";

      if (!threadMessages.length) {
        renderWelcome();
      } else {
        threadMessages.forEach(function (message) {
          if (message.role === "user" || message.role === "assistant") {
            appendMessage(message.role, message.content, message.created_at);
          }
        });
      }

      renderCandidates([]);
      renderDraft(detail ? detail.pending_draft : null);
      setStatus("Ready when you are.");
    }

    function loadThread(threadId) {
      return requestJson("/api/assistant/threads/" + threadId).then(function (detail) {
        state.threadId = detail.id;
        setStoredThreadId(detail.id);
        renderThreadDetail(detail);
        return detail;
      });
    }

    function createThread() {
      return requestJson("/api/assistant/threads", {
        method: "POST",
        body: JSON.stringify({ title: "AI scheduling chat" })
      }).then(function (thread) {
        state.threadId = thread.id;
        setStoredThreadId(thread.id);
        renderWelcome();
        renderDraft(thread.pending_draft || null);
        setStatus("Ready when you are.");
        return thread;
      });
    }

    function startNewThread() {
      if (state.isBusy) {
        return;
      }

      setBusy(true);
      setStatus("Starting a fresh scheduling chat...");
      resetResponseExtras();
      createThread().then(function () {
        state.initialized = true;
        input.focus();
      }).catch(function (error) {
        setStatus(error.message || "Could not start a new chat.", true);
      }).finally(function () {
        setBusy(false);
      });
    }

    function ensureThread() {
      if (state.initialized && state.threadId) {
        return Promise.resolve(state.threadId);
      }

      setBusy(true);
      setStatus("Loading your scheduling chat...");

      var storedThreadId = state.threadId;
      var loadStored = storedThreadId ? loadThread(storedThreadId).catch(function () {
        setStoredThreadId(null);
        state.threadId = null;
        return null;
      }) : Promise.resolve(null);

      return loadStored.then(function (loaded) {
        if (loaded) {
          return loaded;
        }

        return requestJson("/api/assistant/threads").then(function (threads) {
          if (threads && threads.length) {
            return loadThread(threads[0].id);
          }
          return createThread();
        });
      }).then(function (thread) {
        state.initialized = true;
        return thread;
      }).catch(function (error) {
        setStatus(error.message || "Assistant is unavailable right now.", true);
        throw error;
      }).finally(function () {
        setBusy(false);
      });
    }

    function renderAssistantResponse(payload) {
      resetResponseExtras();
      if (payload.assistant_message && payload.assistant_message.content) {
        appendMessage("assistant", payload.assistant_message.content, payload.assistant_message.created_at);
      }

      if (payload.pending_questions && payload.pending_questions.length) {
        payload.pending_questions.forEach(function (question) {
          appendMessage("assistant", question);
        });
      }

      renderCandidates(payload.candidate_invitees || []);
      renderDraft(payload.pending_draft || null);
      renderCompletedAction(payload.completed_action || null);
      setStatus("Ready when you are.");
    }

    function sendMessage(message) {
      return ensureThread().then(function () {
        appendMessage("user", message);
        setBusy(true);
        setStatus("Thinking through your schedule...");
        return requestJson("/api/assistant/threads/" + state.threadId + "/messages", {
          method: "POST",
          body: JSON.stringify({
            message: message,
            selected_user_ids: state.selectedUserIds
          })
        });
      }).then(function (payload) {
        renderAssistantResponse(payload);
      }).catch(function (error) {
        setStatus(error.message || "Assistant is unavailable right now.", true);
        appendMessage("assistant", "I could not complete that request. Please try again in a moment.");
      }).finally(function () {
        setBusy(false);
        input.focus();
      });
    }

    function confirmDraft() {
      if (!state.pendingDraftId || state.isBusy) {
        return;
      }

      setBusy(true);
      setStatus("Confirming your draft...");
      requestJson("/api/assistant/threads/" + state.threadId + "/confirm", {
        method: "POST",
        body: JSON.stringify({ draft_action_id: state.pendingDraftId })
      }).then(function (payload) {
        renderAssistantResponse(payload);
      }).catch(function (error) {
        setStatus(error.message || "Could not confirm that draft.", true);
      }).finally(function () {
        setBusy(false);
      });
    }

    function discardDraft() {
      if (!state.pendingDraftId || state.isBusy) {
        return;
      }

      setBusy(true);
      setStatus("Discarding your draft...");
      requestJson("/api/assistant/threads/" + state.threadId + "/discard", {
        method: "POST",
        body: JSON.stringify({ draft_action_id: state.pendingDraftId })
      }).then(function (payload) {
        renderAssistantResponse(payload);
      }).catch(function (error) {
        setStatus(error.message || "Could not discard that draft.", true);
      }).finally(function () {
        setBusy(false);
      });
    }

    function openChat() {
      if (!isPage) {
        if (state.closeTimer) {
          window.clearTimeout(state.closeTimer);
          state.closeTimer = null;
        }
      state.isOpen = true;
      panel.hidden = false;
      panel.setAttribute("aria-hidden", "false");
      document.body.classList.add("assistant-widget-open");
        if (scrim) {
          scrim.hidden = false;
        }
        if (openButton) {
          openButton.setAttribute("aria-expanded", "true");
        }
        window.requestAnimationFrame(function () {
          root.classList.add("is-open");
        });
        setStoredOpenState(true);
      }

      ensureThread().then(function () {
        input.focus();
      }).catch(function () {
      });
    }

    function closeChat() {
      if (isPage) {
        return;
      }

      state.isOpen = false;
      panel.setAttribute("aria-hidden", "true");
      root.classList.remove("is-open");
      document.body.classList.remove("assistant-widget-open");
      if (openButton) {
        openButton.setAttribute("aria-expanded", "false");
        openButton.focus();
      }
      setStoredOpenState(false);

      if (state.closeTimer) {
        window.clearTimeout(state.closeTimer);
      }
      state.closeTimer = window.setTimeout(function () {
        panel.hidden = true;
        if (scrim) {
          scrim.hidden = true;
        }
        state.closeTimer = null;
      }, CLOSE_ANIMATION_MS);
    }

    if (openButton) {
      openButton.addEventListener("click", openChat);
    }

    if (newButton) {
      newButton.addEventListener("click", startNewThread);
    }

    root.querySelectorAll("[data-assistant-suggestion]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (state.isBusy) {
          return;
        }
        input.value = button.getAttribute("data-assistant-suggestion") || button.textContent || "";
        form.requestSubmit();
      });
    });

    if (closeButton) {
      closeButton.addEventListener("click", closeChat);
    }

    if (scrim) {
      scrim.addEventListener("click", closeChat);
    }

    if (resizeHandle) {
      resizeHandle.addEventListener("pointerdown", function (event) {
        if (window.innerWidth <= 640) {
          return;
        }
        event.preventDefault();
        resizeHandle.setPointerCapture(event.pointerId);
        var rect = panel.getBoundingClientRect();
        state.resizeStart = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          width: rect.width,
          height: rect.height
        };
        root.classList.add("is-resizing");
      });

      resizeHandle.addEventListener("pointermove", function (event) {
        if (!state.resizeStart || state.resizeStart.pointerId !== event.pointerId) {
          return;
        }
        var nextWidth = clamp(state.resizeStart.width + (state.resizeStart.startX - event.clientX), MIN_PANEL_WIDTH, maxPanelWidth());
        var nextHeight = clamp(state.resizeStart.height + (event.clientY - state.resizeStart.startY), MIN_PANEL_HEIGHT, maxPanelHeight());
        applyPanelSize({ width: nextWidth, height: nextHeight });
      });

      resizeHandle.addEventListener("pointerup", function (event) {
        if (!state.resizeStart || state.resizeStart.pointerId !== event.pointerId) {
          return;
        }
        var rect = panel.getBoundingClientRect();
        setStoredPanelSize({ width: Math.round(rect.width), height: Math.round(rect.height) });
        state.resizeStart = null;
        root.classList.remove("is-resizing");
      });

      resizeHandle.addEventListener("pointercancel", function () {
        state.resizeStart = null;
        root.classList.remove("is-resizing");
      });
    }

    confirmButton.addEventListener("click", confirmDraft);
    discardButton.addEventListener("click", discardDraft);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (state.isBusy) {
        return;
      }

      var message = input.value.trim();
      if (!message && state.selectedUserIds.length) {
        message = "Use the selected invitees.";
      }
      if (!message) {
        input.focus();
        return;
      }

      input.value = "";
      sendMessage(message);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.isOpen && !isPage) {
        closeChat();
      }
    });

    if (isPage) {
      renderWelcome();
      ensureThread().catch(function () {
      });
    } else if (getStoredOpenState()) {
      loadPanelSize();
      openChat();
    } else {
      loadPanelSize();
      setBusy(false);
    }

    window.addEventListener("resize", loadPanelSize);

    return {
      open: openChat,
      close: closeChat
    };
  }

  function initialize() {
    var firstController = null;
    document.querySelectorAll("[data-assistant-chat]").forEach(function (root) {
      if (root.dataset.assistantChatEnhanced === "true") {
        return;
      }
      root.dataset.assistantChatEnhanced = "true";
      var controller = setupAssistantChat(root);
      if (!firstController && controller) {
        firstController = controller;
      }
    });

    document.addEventListener("click", function (event) {
      var opener = event.target.closest("[data-assistant-open-any]");
      if (!opener || !firstController) {
        return;
      }
      event.preventDefault();
      firstController.open();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
