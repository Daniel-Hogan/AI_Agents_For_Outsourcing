document.addEventListener("DOMContentLoaded", () => {
  initAvailabilityTimePickers();
});

function initAvailabilityTimePickers() {
  const pickerNodes = Array.from(document.querySelectorAll("[data-time-picker]"));
  if (!pickerNodes.length) {
    return;
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function populateOptions(select, options, placeholder) {
    const values = placeholder ? [["", placeholder], ...options] : options;
    select.innerHTML = values.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  }

  function parseTimeValue(value) {
    const raw = String(value || "").trim();
    if (!raw) {
      return null;
    }

    const match = /^(\d{2}):(\d{2})/.exec(raw);
    if (!match) {
      return null;
    }

    const hours24 = Number.parseInt(match[1], 10);
    const minutes = Number.parseInt(match[2], 10);
    if (!Number.isFinite(hours24) || !Number.isFinite(minutes)) {
      return null;
    }

    const period = hours24 >= 12 ? "PM" : "AM";
    const hours12 = hours24 % 12 || 12;
    return {
      hour: String(hours12),
      minute: pad(minutes),
      period,
    };
  }

  function syncNativeInput(picker) {
    const { hourSelect, minuteSelect, periodSelect, nativeInput } = picker;
    if (!hourSelect.value || !minuteSelect.value || !periodSelect.value) {
      nativeInput.value = "";
      return;
    }

    let hours24 = Number.parseInt(hourSelect.value, 10) % 12;
    if (periodSelect.value === "PM") {
      hours24 += 12;
    }

    nativeInput.value = `${pad(hours24)}:${minuteSelect.value}`;
  }

  function setPickerFromValue(picker, value) {
    const parsed = parseTimeValue(value);
    if (!parsed) {
      picker.hourSelect.value = "";
      picker.minuteSelect.value = "";
      picker.periodSelect.value = "";
      picker.nativeInput.value = "";
      return;
    }

    picker.hourSelect.value = parsed.hour;
    picker.minuteSelect.value = parsed.minute;
    picker.periodSelect.value = parsed.period;
    syncNativeInput(picker);
  }

  const pickers = pickerNodes
    .map((node) => {
      const nativeWrapper = node.querySelector("[data-time-native-wrapper]");
      const nativeInput = node.querySelector("[data-time-native]");
      const enhanced = node.querySelector("[data-time-enhanced]");
      const hourSelect = node.querySelector("[data-time-hour]");
      const minuteSelect = node.querySelector("[data-time-minute]");
      const periodSelect = node.querySelector("[data-time-period]");

      if (!nativeWrapper || !nativeInput || !enhanced || !hourSelect || !minuteSelect || !periodSelect) {
        return null;
      }

      populateOptions(
        hourSelect,
        [
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
        ],
        "Hour",
      );
      populateOptions(
        minuteSelect,
        [
          ["00", "00"],
          ["15", "15"],
          ["30", "30"],
          ["45", "45"],
        ],
        "Min",
      );
      populateOptions(
        periodSelect,
        [
          ["AM", "AM"],
          ["PM", "PM"],
        ],
        "AM/PM",
      );

      setPickerFromValue(
        {
          nativeInput,
          hourSelect,
          minuteSelect,
          periodSelect,
        },
        nativeInput.value,
      );

      nativeWrapper.classList.add("availability-native-hidden");
      enhanced.hidden = false;
      nativeInput.required = false;
      hourSelect.required = true;
      minuteSelect.required = true;
      periodSelect.required = true;

      const picker = {
        node,
        nativeInput,
        hourSelect,
        minuteSelect,
        periodSelect,
      };

      const sync = () => syncNativeInput(picker);
      hourSelect.addEventListener("change", sync);
      minuteSelect.addEventListener("change", sync);
      periodSelect.addEventListener("change", sync);
      nativeInput.form?.addEventListener("submit", sync);

      node.addEventListener("click", (event) => {
        const target = event.target;
        if (target instanceof HTMLSelectElement) {
          return;
        }

        const firstEmptySelect = [hourSelect, minuteSelect, periodSelect].find((select) => !select.value);
        (firstEmptySelect || hourSelect).focus();
      });

      return picker;
    })
    .filter(Boolean);

  if (!pickers.length) {
    return;
  }
}
