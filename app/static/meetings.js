document.addEventListener("DOMContentLoaded", () => {
  initDateTimePickers();
  initLocationAutocomplete();
});

function initLocationAutocomplete() {
  const root = document.querySelector("[data-location-autocomplete-root]");
  if (!root) {
    return;
  }

  const input = root.querySelector("[data-location-autocomplete-input]");
  const rawInput = root.querySelector("[data-location-raw]");
  const latitudeInput = root.querySelector("[data-location-latitude]");
  const longitudeInput = root.querySelector("[data-location-longitude]");
  const suggestionsPanel = root.querySelector("[data-location-suggestions]");

  if (!input || !rawInput || !latitudeInput || !longitudeInput || !suggestionsPanel) {
    return;
  }

  const endpoint = input.dataset.autocompleteUrl;
  if (!endpoint) {
    return;
  }

  const minimumLength = 3;
  const debounceMs = 300;
  let debounceTimer = null;
  let requestSequence = 0;

  function hideSuggestions() {
    suggestionsPanel.hidden = true;
    suggestionsPanel.innerHTML = "";
  }

  function clearResolvedLocation() {
    latitudeInput.value = "";
    longitudeInput.value = "";
  }

  function showStatus(message) {
    suggestionsPanel.hidden = false;
    suggestionsPanel.innerHTML = `<div class="location-suggestion-status">${message}</div>`;
  }

  function renderSuggestions(items) {
    if (!items.length) {
      showStatus("No suggestions found.");
      return;
    }

    suggestionsPanel.hidden = false;
    suggestionsPanel.innerHTML = items
      .map(
        (item) => `
          <button
            type="button"
            class="location-suggestion"
            data-label="${escapeHtml(item.label)}"
            data-latitude="${item.latitude}"
            data-longitude="${item.longitude}"
          >
            <span>${escapeHtml(item.label)}</span>
            <span class="location-suggestion-meta">${Number(item.latitude).toFixed(5)}, ${Number(item.longitude).toFixed(5)}</span>
          </button>
        `,
      )
      .join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll("\"", "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function fetchSuggestions(query, sequence) {
    showStatus("Searching locations...");

    try {
      const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, {
        headers: { Accept: "application/json" },
      });
      if (sequence !== requestSequence) {
        return;
      }

      if (!response.ok) {
        showStatus("Suggestions unavailable right now.");
        return;
      }

      const payload = await response.json();
      renderSuggestions(payload.suggestions || []);
    } catch (_error) {
      if (sequence !== requestSequence) {
        return;
      }
      showStatus("Suggestions unavailable right now.");
    }
  }

  input.addEventListener("input", () => {
    rawInput.value = input.value.trim();
    clearResolvedLocation();

    window.clearTimeout(debounceTimer);

    const query = input.value.trim();
    if (query.length < minimumLength) {
      hideSuggestions();
      return;
    }

    debounceTimer = window.setTimeout(() => {
      requestSequence += 1;
      fetchSuggestions(query, requestSequence);
    }, debounceMs);
  });

  input.addEventListener("focus", () => {
    const query = input.value.trim();
    if (latitudeInput.value || longitudeInput.value || query.length < minimumLength) {
      return;
    }
    requestSequence += 1;
    fetchSuggestions(query, requestSequence);
  });

  suggestionsPanel.addEventListener("click", (event) => {
    const button = event.target.closest(".location-suggestion");
    if (!button) {
      return;
    }

    input.value = button.dataset.label || "";
    latitudeInput.value = button.dataset.latitude || "";
    longitudeInput.value = button.dataset.longitude || "";
    if (!rawInput.value) {
      rawInput.value = input.value.trim();
    }
    hideSuggestions();
  });

  input.addEventListener("blur", () => {
    window.setTimeout(() => {
      hideSuggestions();
    }, 150);
  });
}

function initDateTimePickers() {
  const pickerNodes = Array.from(document.querySelectorAll("[data-datetime-picker]"));
  if (!pickerNodes.length) {
    return;
  }

  const pickers = pickerNodes.map((node) => createDateTimePicker(node)).filter(Boolean);
  const pickerGroups = new Map();

  for (const picker of pickers) {
    if (!pickerGroups.has(picker.group)) {
      pickerGroups.set(picker.group, {});
    }
    pickerGroups.get(picker.group)[picker.role] = picker;
  }

  for (const picker of pickers) {
    syncNativeInput(picker);
  }

  for (const group of pickerGroups.values()) {
    if (group.start && group.end) {
      initializeRangeState(group.start, group.end);
      attachRangeBehavior(group.start, group.end);
      maybeAutoAdjustEnd(group.start, group.end);
    }
  }
}

function createDateTimePicker(node) {
  const nativeWrapper = node.querySelector("[data-datetime-native-wrapper]");
  const nativeInput = node.querySelector("[data-datetime-native]");
  const enhanced = node.querySelector("[data-datetime-enhanced]");
  const dateInput = node.querySelector("[data-datetime-date]");
  const hourSelect = node.querySelector("[data-datetime-hour]");
  const minuteSelect = node.querySelector("[data-datetime-minute]");
  const periodSelect = node.querySelector("[data-datetime-period]");

  if (!nativeWrapper || !nativeInput || !enhanced || !dateInput || !hourSelect || !minuteSelect || !periodSelect) {
    return null;
  }

  populateOptions(hourSelect, [
    ["1", "1"],
    ["2", "2"],
    ["3", "3"],
    ["4", "4"],
    ["5", "5"],
    ["6", "6"],
    ["7", "7"],
    ["8", "8"],
    ["9", "9"],
    ["10", "10"],
    ["11", "11"],
    ["12", "12"],
  ]);
  populateOptions(minuteSelect, [
    ["00", "00"],
    ["15", "15"],
    ["30", "30"],
    ["45", "45"],
  ]);
  populateOptions(periodSelect, [
    ["AM", "AM"],
    ["PM", "PM"],
  ]);

  const picker = {
    node,
    group: node.dataset.rangeGroup || "",
    role: node.dataset.rangeRole || "",
    nativeInput,
    dateInput,
    hourSelect,
    minuteSelect,
    periodSelect,
    lastAutoValue: null,
    userAdjusted: false,
    suppressManualTracking: false,
  };

  const initialDate = roundToQuarterHour(parseDateTimeValue(nativeInput.value));
  if (initialDate) {
    setPickerControls(picker, initialDate);
    nativeInput.value = formatDateTimeValue(initialDate);
  } else {
    hourSelect.value = "9";
    minuteSelect.value = "00";
    periodSelect.value = "AM";
  }

  enhanced.hidden = false;
  nativeWrapper.classList.add("datetime-native-hidden");
  dateInput.required = nativeInput.required;
  nativeInput.required = false;

  const onUserChange = () => {
    syncNativeInput(picker);
    if (picker.role === "end" && !picker.suppressManualTracking) {
      picker.userAdjusted = true;
    }
  };

  dateInput.addEventListener("change", onUserChange);
  hourSelect.addEventListener("change", onUserChange);
  minuteSelect.addEventListener("change", onUserChange);
  periodSelect.addEventListener("change", onUserChange);
  nativeInput.form?.addEventListener("submit", () => syncNativeInput(picker));

  return picker;
}

function initializeRangeState(startPicker, endPicker) {
  const startValue = getPickerDate(startPicker);
  const endValue = getPickerDate(endPicker);
  if (!endValue) {
    return;
  }

  endPicker.userAdjusted = true;
  if (startValue && endValue.getTime() - startValue.getTime() === 60 * 60 * 1000) {
    endPicker.lastAutoValue = formatDateTimeValue(endValue);
  }
}

function attachRangeBehavior(startPicker, endPicker) {
  const startInputs = [startPicker.dateInput, startPicker.hourSelect, startPicker.minuteSelect, startPicker.periodSelect];
  const endInputs = [endPicker.dateInput, endPicker.hourSelect, endPicker.minuteSelect, endPicker.periodSelect];

  for (const input of startInputs) {
    input.addEventListener("change", () => {
      syncNativeInput(startPicker);
      maybeAutoAdjustEnd(startPicker, endPicker);
    });
  }

  for (const input of endInputs) {
    input.addEventListener("change", () => {
      if (!endPicker.suppressManualTracking) {
        endPicker.userAdjusted = true;
      }
    });
  }
}

function maybeAutoAdjustEnd(startPicker, endPicker) {
  const startValue = getPickerDate(startPicker);
  if (!startValue) {
    return;
  }

  const currentEnd = getPickerDate(endPicker);
  const shouldAutofill =
    !currentEnd ||
    !endPicker.userAdjusted ||
    endPicker.lastAutoValue === formatDateTimeValue(currentEnd) ||
    currentEnd.getTime() <= startValue.getTime();

  if (!shouldAutofill) {
    return;
  }

  const nextHour = new Date(startValue.getTime() + 60 * 60 * 1000);
  endPicker.suppressManualTracking = true;
  setPickerValue(endPicker, nextHour, { autoGenerated: true });
  endPicker.suppressManualTracking = false;
}

function setPickerValue(picker, date, { autoGenerated = false } = {}) {
  const rounded = roundToQuarterHour(date);
  if (!rounded) {
    picker.nativeInput.value = "";
    return;
  }

  setPickerControls(picker, rounded);
  syncNativeInput(picker);

  if (autoGenerated) {
    picker.lastAutoValue = picker.nativeInput.value;
    picker.userAdjusted = false;
  }
}

function syncNativeInput(picker) {
  const date = getPickerDate(picker);
  picker.nativeInput.value = date ? formatDateTimeValue(date) : "";
}

function setPickerControls(picker, date) {
  picker.dateInput.value = formatDateValue(date);

  const hours24 = date.getHours();
  const period = hours24 >= 12 ? "PM" : "AM";
  const hours12 = hours24 % 12 || 12;

  picker.hourSelect.value = String(hours12);
  picker.minuteSelect.value = pad(date.getMinutes());
  picker.periodSelect.value = period;
}

function getPickerDate(picker) {
  const dateValue = picker.dateInput.value;
  if (!dateValue) {
    return null;
  }

  const hourValue = Number.parseInt(picker.hourSelect.value || "9", 10);
  const minuteValue = Number.parseInt(picker.minuteSelect.value || "0", 10);
  const periodValue = picker.periodSelect.value || "AM";

  let hours24 = hourValue % 12;
  if (periodValue === "PM") {
    hours24 += 12;
  }

  return new Date(`${dateValue}T${pad(hours24)}:${pad(minuteValue)}`);
}

function populateOptions(select, values) {
  select.innerHTML = values
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join("");
}

function parseDateTimeValue(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return null;
  }

  const normalized = raw.slice(0, 16);
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function roundToQuarterHour(date) {
  if (!date) {
    return null;
  }

  const rounded = new Date(date.getTime());
  rounded.setSeconds(0, 0);
  const minutes = rounded.getMinutes();
  const quarterMinutes = Math.round(minutes / 15) * 15;
  rounded.setMinutes(quarterMinutes);
  if (rounded.getMinutes() === 60) {
    rounded.setHours(rounded.getHours() + 1);
    rounded.setMinutes(0);
  }
  return rounded;
}

function formatDateValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateTimeValue(date) {
  return `${formatDateValue(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function pad(value) {
  return String(value).padStart(2, "0");
}
