document.addEventListener("DOMContentLoaded", () => {
  initDateTimePickers();
  initLocationAutocomplete();
  initRecommendationQuickControls();
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
  node._dateTimePicker = picker;

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
    emitPickerChange(picker);
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
    emitPickerChange(picker);
    return;
  }

  setPickerControls(picker, rounded);
  syncNativeInput(picker);
  emitPickerChange(picker);

  if (autoGenerated) {
    picker.lastAutoValue = picker.nativeInput.value;
    picker.userAdjusted = false;
  }
}

function syncNativeInput(picker) {
  const date = getPickerDate(picker);
  picker.nativeInput.value = date ? formatDateTimeValue(date) : "";
}

function emitPickerChange(picker) {
  picker.node.dispatchEvent(
    new CustomEvent("datetimepicker:change", {
      detail: { value: picker.nativeInput.value },
    }),
  );
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

function initRecommendationQuickControls() {
  const root = document.querySelector("[data-recommendation-sliders]");
  if (!root) {
    return;
  }

  const recommendationStartPicker = document.querySelector(
    '[data-datetime-picker][data-range-group="recommendation"][data-range-role="start"]',
  )?._dateTimePicker;
  const recommendationEndPicker = document.querySelector(
    '[data-datetime-picker][data-range-group="recommendation"][data-range-role="end"]',
  )?._dateTimePicker;
  const meetingStartPicker = document.querySelector(
    '[data-datetime-picker][data-range-group="meeting"][data-range-role="start"]',
  )?._dateTimePicker;
  const durationInput = document.querySelector('input[name="recommendation_duration_minutes"]');
  const startOffsetInput = root.querySelector("[data-window-start-offset]");
  const endOffsetInput = root.querySelector("[data-window-end-offset]");
  const windowFill = root.querySelector("[data-window-slider-fill]");
  const windowRangeLabel = root.querySelector("[data-window-range-label]");
  const windowSpanLabel = root.querySelector("[data-window-span-label]");
  const durationRange = root.querySelector("[data-duration-range]");
  const durationLabel = root.querySelector("[data-duration-slider-label]");

  if (
    !recommendationStartPicker ||
    !recommendationEndPicker ||
    !durationInput ||
    !startOffsetInput ||
    !endOffsetInput ||
    !windowFill ||
    !windowRangeLabel ||
    !windowSpanLabel ||
    !durationRange ||
    !durationLabel
  ) {
    return;
  }

  const minimumOffset = Number.parseInt(startOffsetInput.min || "0", 10);
  const maximumOffset = Number.parseInt(startOffsetInput.max || "14", 10);
  const dayMs = 24 * 60 * 60 * 1000;
  let syncingFromSlider = false;

  function stripTime(date) {
    const copy = new Date(date.getTime());
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function pluralize(value, singular, plural = `${singular}s`) {
    return `${value} ${value === 1 ? singular : plural}`;
  }

  function formatSummaryDate(date) {
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function getAnchorDate() {
    const selectedDayInput = document.querySelector('input[name="day"]');
    const meetingStartDate = meetingStartPicker ? getPickerDate(meetingStartPicker) : null;
    const recommendationStartDate = getPickerDate(recommendationStartPicker);

    if (meetingStartDate) {
      return stripTime(meetingStartDate);
    }
    if (recommendationStartDate) {
      return stripTime(recommendationStartDate);
    }
    if (selectedDayInput?.value) {
      return stripTime(new Date(`${selectedDayInput.value}T09:00`));
    }
    return stripTime(new Date());
  }

  function buildDateFromAnchor(anchorDate, offsetDays, templateDate, fallbackHour) {
    const nextDate = new Date(anchorDate.getTime() + offsetDays * dayMs);
    const baseTemplate = templateDate || new Date(anchorDate.getTime());
    const baseHours = Number.isFinite(baseTemplate.getHours()) ? baseTemplate.getHours() : fallbackHour;
    const baseMinutes = Number.isFinite(baseTemplate.getMinutes()) ? baseTemplate.getMinutes() : 0;
    nextDate.setHours(baseHours, baseMinutes, 0, 0);
    return roundToQuarterHour(nextDate);
  }

  function getOffsetFromAnchor(date, anchorDate) {
    return clamp(Math.round((stripTime(date).getTime() - anchorDate.getTime()) / dayMs), minimumOffset, maximumOffset);
  }

  function updateWindowFill() {
    const startOffset = Number.parseInt(startOffsetInput.value || "0", 10);
    const endOffset = Number.parseInt(endOffsetInput.value || "0", 10);
    const startPercent = ((startOffset - minimumOffset) / (maximumOffset - minimumOffset)) * 100;
    const endPercent = ((endOffset - minimumOffset) / (maximumOffset - minimumOffset)) * 100;
    windowFill.style.left = `${startPercent}%`;
    windowFill.style.width = `${Math.max(0, endPercent - startPercent)}%`;
  }

  function renderWindowSummary(anchorDate, startDate, endDate) {
    const spanDays = Math.max(0, Math.round((stripTime(endDate).getTime() - stripTime(startDate).getTime()) / dayMs));
    windowRangeLabel.textContent = `${formatSummaryDate(startDate)} - ${formatSummaryDate(endDate)}`;
    windowSpanLabel.textContent = `${pluralize(spanDays, "day")} span from ${formatSummaryDate(anchorDate)}`;
  }

  function renderDurationSummary(durationMinutes) {
    const numericDuration = Number.isFinite(durationMinutes) ? durationMinutes : 60;
    const customOutsideQuickRange = numericDuration < 15 || numericDuration > 120 || numericDuration % 15 !== 0;
    durationLabel.textContent = customOutsideQuickRange
      ? `${numericDuration} min meeting (custom below)`
      : `${numericDuration} min meeting`;
  }

  function syncWindowSliderFromInputs() {
    if (syncingFromSlider) {
      return;
    }

    const anchorDate = getAnchorDate();
    const startDate = getPickerDate(recommendationStartPicker) || buildDateFromAnchor(anchorDate, minimumOffset, null, 9);
    const endDate = getPickerDate(recommendationEndPicker) || buildDateFromAnchor(anchorDate, minimumOffset + 1, null, 10);

    let startOffset = getOffsetFromAnchor(startDate, anchorDate);
    let endOffset = getOffsetFromAnchor(endDate, anchorDate);
    if (endOffset < startOffset) {
      endOffset = startOffset;
    }

    startOffsetInput.value = String(startOffset);
    endOffsetInput.value = String(endOffset);
    updateWindowFill();
    renderWindowSummary(anchorDate, startDate, endDate);
  }

  function syncWindowInputsFromSlider(activeInput) {
    syncingFromSlider = true;

    let startOffset = Number.parseInt(startOffsetInput.value || "0", 10);
    let endOffset = Number.parseInt(endOffsetInput.value || "0", 10);
    if (startOffset > endOffset) {
      if (activeInput === startOffsetInput) {
        endOffset = startOffset;
        endOffsetInput.value = String(endOffset);
      } else {
        startOffset = endOffset;
        startOffsetInput.value = String(startOffset);
      }
    }

    const anchorDate = getAnchorDate();
    const currentStartDate = getPickerDate(recommendationStartPicker);
    const currentEndDate = getPickerDate(recommendationEndPicker);
    const startDate = buildDateFromAnchor(anchorDate, startOffset, currentStartDate, 9);
    let endDate = buildDateFromAnchor(anchorDate, endOffset, currentEndDate, 10);

    if (endDate.getTime() <= startDate.getTime()) {
      endDate = roundToQuarterHour(new Date(startDate.getTime() + 60 * 60 * 1000));
    }

    setPickerValue(recommendationStartPicker, startDate);
    setPickerValue(recommendationEndPicker, endDate);
    updateWindowFill();
    renderWindowSummary(anchorDate, startDate, endDate);

    syncingFromSlider = false;
  }

  function syncDurationSliderFromInput() {
    const rawDuration = Number.parseInt(durationInput.value || durationRange.value || "60", 10);
    const safeDuration = Number.isFinite(rawDuration) ? rawDuration : 60;
    const sliderValue = clamp(Math.round(safeDuration / 15) * 15, 15, 120);
    durationRange.value = String(sliderValue);
    renderDurationSummary(safeDuration);
  }

  function syncDurationInputFromSlider() {
    durationInput.value = durationRange.value;
    renderDurationSummary(Number.parseInt(durationRange.value || "60", 10));
  }

  startOffsetInput.addEventListener("input", () => syncWindowInputsFromSlider(startOffsetInput));
  endOffsetInput.addEventListener("input", () => syncWindowInputsFromSlider(endOffsetInput));
  durationRange.addEventListener("input", syncDurationInputFromSlider);
  durationInput.addEventListener("input", syncDurationSliderFromInput);

  recommendationStartPicker.node.addEventListener("datetimepicker:change", syncWindowSliderFromInputs);
  recommendationEndPicker.node.addEventListener("datetimepicker:change", syncWindowSliderFromInputs);
  if (meetingStartPicker) {
    meetingStartPicker.node.addEventListener("datetimepicker:change", syncWindowSliderFromInputs);
  }

  syncWindowSliderFromInputs();
  syncDurationSliderFromInput();
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
