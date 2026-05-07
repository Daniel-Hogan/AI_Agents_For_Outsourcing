(function () {
  var STORAGE_KEY = "schedulerai.assistant.threadId";

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
      pendingDraftId: null
    };

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
        candidateList.appendChild(label);
      });

      candidatesSection.hidden = false;
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
        state.isOpen = true;
        panel.hidden = false;
        panel.setAttribute("aria-hidden", "false");
        if (scrim) {
          scrim.hidden = false;
        }
        if (openButton) {
          openButton.setAttribute("aria-expanded", "true");
        }
        root.classList.add("is-open");
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
      panel.hidden = true;
      panel.setAttribute("aria-hidden", "true");
      if (scrim) {
        scrim.hidden = true;
      }
      if (openButton) {
        openButton.setAttribute("aria-expanded", "false");
        openButton.focus();
      }
      root.classList.remove("is-open");
    }

    if (openButton) {
      openButton.addEventListener("click", openChat);
    }

    if (newButton) {
      newButton.addEventListener("click", startNewThread);
    }

    if (closeButton) {
      closeButton.addEventListener("click", closeChat);
    }

    if (scrim) {
      scrim.addEventListener("click", closeChat);
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
    } else {
      setBusy(false);
    }
  }

  function initialize() {
    document.querySelectorAll("[data-assistant-chat]").forEach(function (root) {
      if (root.dataset.assistantChatEnhanced === "true") {
        return;
      }
      root.dataset.assistantChatEnhanced = "true";
      setupAssistantChat(root);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
