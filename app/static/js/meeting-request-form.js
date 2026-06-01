document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("requestForm");
  if (!form) return;

  const fechaInput = document.getElementById("fecha");
  const horaInicioInput = document.getElementById("hora_inicio");
  const horaFinInput = document.getElementById("hora_fin");
  const zonaSelect = document.getElementById("zona_id");
  const zoneCards = Array.from(document.querySelectorAll("[data-zone-card]"));
  const participantCards = Array.from(document.querySelectorAll("[data-participant-card]"));
  const participantSearch = document.getElementById("participantSearch");
  const participantArea = document.getElementById("participantArea");
  const participantRole = document.getElementById("participantRole");
  const zoneSearch = document.getElementById("zoneSearch");
  const zoneArea = document.getElementById("zoneArea");
  const zoneAvailability = document.getElementById("zoneAvailability");
  const zoneCapacity = document.getElementById("zoneCapacity");
  const notice = document.getElementById("availabilityNotice");
  const selectedParticipants = document.getElementById("selectedParticipants");
  const selectedCount = document.getElementById("summaryParticipants");
  const summaryTitle = document.getElementById("summaryTitle");
  const summaryWhen = document.getElementById("summaryWhen");
  const summaryZone = document.getElementById("summaryZone");
  const summaryStatus = document.getElementById("summaryStatus");

  fechaInput.min = new Date().toISOString().split("T")[0];

  function setNotice(message, type = "warning") {
    if (!notice) return;
    notice.hidden = !message;
    notice.textContent = message || "";
    notice.className = `alert alert-${type}`;
  }

  function validDateTime() {
    if (!fechaInput.value || !horaInicioInput.value || !horaFinInput.value) {
      setNotice("Defina fecha y horario para validar salas y participantes.");
      return false;
    }
    if (horaFinInput.value <= horaInicioInput.value) {
      setNotice("La hora de fin debe ser mayor que la hora de inicio.", "danger");
      return false;
    }
    setNotice("");
    return true;
  }

  function updateZoneSelectLabel(card, available, reason) {
    const option = zonaSelect.querySelector(`option[value="${card.dataset.zoneId}"]`);
    if (!option) return;
    const base = option.dataset.originalName;
    option.disabled = !available;
    option.textContent = available ? base : `[Sala ocupada en ese horario] ${base}`;
    option.dataset.reason = reason || "";
  }

  function updateAvailability() {
    if (!validDateTime()) {
      updateSummary();
      return;
    }

    fetch(`/api/web/availability?fecha=${fechaInput.value}&hora_inicio=${horaInicioInput.value}&hora_fin=${horaFinInput.value}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          setNotice(`Error al validar disponibilidad: ${data.error}`, "danger");
          return;
        }

        zoneCards.forEach((card) => {
          const status = data.zonas.find((zone) => String(zone.id) === card.dataset.zoneId);
          if (!status) return;
          const available = Boolean(status.disponible);
          card.dataset.available = available ? "1" : "0";
          card.classList.toggle("is-disabled", !available);
          card.querySelector(".availability-badge").className = `badge availability-badge ${available ? "success" : "danger"}`;
          card.querySelector(".availability-badge").textContent = available ? "Disponible" : "Ocupada";
          card.querySelector(".select-card-reason").textContent = available ? "" : (status.motivo || "No disponible");
          const input = card.querySelector("input[type='radio']");
          input.disabled = !available;
          if (!available && input.checked) {
            input.checked = false;
            zonaSelect.value = "";
          }
          updateZoneSelectLabel(card, available, status.motivo);
        });

        const users = [];
        Object.values(data.usuarios_por_area || {}).forEach((items) => users.push(...items));
        participantCards.forEach((card) => {
          const status = users.find((user) => String(user.id) === card.dataset.userId);
          if (!status) return;
          const available = Boolean(status.disponible);
          card.dataset.available = available ? "1" : "0";
          card.classList.toggle("is-disabled", !available);
          card.querySelector(".availability-badge").className = `badge availability-badge ${available ? "success" : "danger"}`;
          card.querySelector(".availability-badge").textContent = available ? "Disponible" : "Ocupado";
          card.querySelector(".select-card-reason").textContent = available ? "" : (status.motivo || "No disponible");
          const input = card.querySelector("input[type='checkbox']");
          input.disabled = !available;
          if (!available) input.checked = false;
          card.classList.toggle("is-selected", input.checked);
        });

        applyParticipantFilters();
        applyZoneFilters();
        renderChips();
        updateSummary();
      })
      .catch(() => setNotice("No se pudo validar disponibilidad. Revise la conexión e intente nuevamente.", "danger"));
  }

  function applyParticipantFilters() {
    const needle = normalize(participantSearch.value);
    const area = participantArea.value;
    const role = participantRole.value;
    participantCards.forEach((card) => {
      const matchesSearch = !needle || normalize(`${card.dataset.name} ${card.dataset.email}`).includes(needle);
      const matchesArea = !area || card.dataset.area === area;
      const matchesRole = !role || card.dataset.role === role;
      card.hidden = !(matchesSearch && matchesArea && matchesRole);
    });
  }

  function applyZoneFilters() {
    const needle = normalize(zoneSearch.value);
    const area = zoneArea.value;
    const availability = zoneAvailability.value;
    const capacity = Number(zoneCapacity.value || 0);
    zoneCards.forEach((card) => {
      const matchesSearch = !needle || normalize(`${card.dataset.name} ${card.dataset.location}`).includes(needle);
      const matchesArea = !area || card.dataset.area === area;
      const matchesAvailability = !availability || card.dataset.available === availability;
      const matchesCapacity = !capacity || Number(card.dataset.capacity || 0) >= capacity;
      card.hidden = !(matchesSearch && matchesArea && matchesAvailability && matchesCapacity);
    });
  }

  function renderChips() {
    const selected = participantCards.filter((card) => card.querySelector("input").checked);
    selectedParticipants.innerHTML = "";
    if (!selected.length) {
      selectedParticipants.innerHTML = '<span class="muted">Sin participantes seleccionados.</span>';
    }
    selected.forEach((card) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = card.dataset.name;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", `Quitar ${card.dataset.name}`);
      remove.textContent = "x";
      remove.addEventListener("click", () => {
        card.querySelector("input").checked = false;
        card.classList.remove("is-selected");
        renderChips();
        updateSummary();
      });
      chip.append(remove);
      selectedParticipants.append(chip);
    });
  }

  function updateSummary() {
    const title = document.getElementById("titulo").value.trim();
    const zoneOption = zonaSelect.selectedOptions[0];
    const selected = participantCards.filter((card) => card.querySelector("input").checked);
    const selectedZoneCard = zoneCards.find((card) => card.querySelector("input").checked);
    const blockedParticipants = selected.filter((card) => card.dataset.available === "0").length;
    const zoneBlocked = selectedZoneCard && selectedZoneCard.dataset.available === "0";

    summaryTitle.textContent = title || "Sin título";
    summaryWhen.textContent = fechaInput.value && horaInicioInput.value && horaFinInput.value
      ? `${fechaInput.value} · ${horaInicioInput.value}-${horaFinInput.value}`
      : "Fecha y horario pendientes";
    summaryZone.textContent = zoneOption && zoneOption.value ? zoneOption.dataset.originalName : "Sin sala";
    selectedCount.textContent = selected.length.toString();

    if (!validDateTime()) {
      summaryStatus.textContent = "Pendiente";
      summaryStatus.className = "badge warning";
    } else if (zoneBlocked || blockedParticipants) {
      summaryStatus.textContent = "Con conflictos";
      summaryStatus.className = "badge danger";
    } else if (zoneOption && zoneOption.value && selected.length) {
      summaryStatus.textContent = "Disponible";
      summaryStatus.className = "badge success";
    } else {
      summaryStatus.textContent = "Incompleto";
      summaryStatus.className = "badge warning";
    }
  }

  zoneCards.forEach((card) => {
    const input = card.querySelector("input");
    input.addEventListener("change", () => {
      if (input.disabled) return;
      zoneCards.forEach((item) => item.classList.toggle("is-selected", item === card));
      zonaSelect.value = input.value;
      updateSummary();
    });
  });

  participantCards.forEach((card) => {
    const input = card.querySelector("input");
    input.addEventListener("change", () => {
      card.classList.toggle("is-selected", input.checked);
      renderChips();
      updateSummary();
    });
  });

  [fechaInput, horaInicioInput, horaFinInput].forEach((input) => input.addEventListener("change", updateAvailability));
  document.getElementById("titulo").addEventListener("input", updateSummary);
  [participantSearch, participantArea, participantRole].forEach((input) => input.addEventListener("input", applyParticipantFilters));
  [zoneSearch, zoneArea, zoneAvailability, zoneCapacity].forEach((input) => input.addEventListener("input", applyZoneFilters));

  form.addEventListener("submit", (event) => {
    if (!zonaSelect.value || !participantCards.some((card) => card.querySelector("input").checked)) {
      event.preventDefault();
      setNotice("Seleccione una sala disponible y al menos un participante.", "danger");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  updateAvailability();
  renderChips();
  updateSummary();
});
