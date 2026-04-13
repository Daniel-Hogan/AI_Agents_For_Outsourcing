document.addEventListener("DOMContentLoaded", () => {
  initCalendarModal();
});

function initCalendarModal() {
  const modal = document.querySelector("[data-calendar-modal]");
  if (!modal) {
    return;
  }

  const titleNode = modal.querySelector("[data-calendar-modal-title]");
  const dateNode = modal.querySelector("[data-calendar-modal-date]");
  const timeNode = modal.querySelector("[data-calendar-modal-time]");
  const locationNode = modal.querySelector("[data-calendar-modal-location]");
  const organizerNode = modal.querySelector("[data-calendar-modal-organizer]");
  const statusNode = modal.querySelector("[data-calendar-modal-status]");
  const travelNode = modal.querySelector("[data-calendar-modal-travel]");
  const warningNode = modal.querySelector("[data-calendar-modal-warning]");
  const warningBadgeNode = modal.querySelector("[data-calendar-modal-warning-badge]");
  const warningMessageNode = modal.querySelector("[data-calendar-modal-warning-message]");
  const detailLink = modal.querySelector("[data-calendar-modal-link]");

  if (
    !titleNode ||
    !dateNode ||
    !timeNode ||
    !locationNode ||
    !organizerNode ||
    !statusNode ||
    !travelNode ||
    !warningNode ||
    !warningBadgeNode ||
    !warningMessageNode ||
    !detailLink
  ) {
    return;
  }

  const openButtons = Array.from(document.querySelectorAll("[data-calendar-open]"));
  const closeButtons = Array.from(modal.querySelectorAll("[data-calendar-close]"));

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("calendar-modal-open");
  }

  function openModal(button) {
    titleNode.textContent = button.dataset.title || "Meeting";
    dateNode.textContent = button.dataset.dateLabel || "";
    timeNode.textContent = button.dataset.timeRange || "";
    locationNode.textContent = button.dataset.location || "No location provided";
    organizerNode.textContent = button.dataset.organizer || "";
    statusNode.textContent = button.dataset.status || "";
    travelNode.textContent = button.dataset.travel || "Travel info unavailable.";
    detailLink.href = button.dataset.detailUrl || "#";

    const severity = button.dataset.warningSeverity || "none";
    const warningMessage = button.dataset.warningMessage || "No active travel warning for this meeting.";
    warningNode.className = "calendar-modal-warning";
    if (severity && severity !== "none") {
      warningNode.classList.add(`calendar-modal-warning-${severity}`);
      warningBadgeNode.textContent = severity.charAt(0).toUpperCase() + severity.slice(1);
    } else {
      warningNode.classList.add("calendar-modal-warning-clear");
      warningBadgeNode.textContent = "Clear";
    }
    warningMessageNode.textContent = warningMessage;

    modal.hidden = false;
    document.body.classList.add("calendar-modal-open");
  }

  for (const button of openButtons) {
    button.addEventListener("click", () => openModal(button));
  }

  for (const button of closeButtons) {
    button.addEventListener("click", closeModal);
  }

  closeModal();

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
}
