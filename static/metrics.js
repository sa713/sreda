const catalogCards = new Map(
  [...document.querySelectorAll(".card[data-material]")].map((card) => [card.dataset.material, card]),
);
const currentMaterial = document.querySelector(".material[data-material]")?.dataset.material;
const numbers = new Intl.NumberFormat("ru");
const writeHeaders = { "X-Sreda-Request": "1" };
const pending = new Set();
let voteRevision = 0;

function showVote(button, { helpful, voted }) {
  button.querySelector(".helpful-count").textContent = numbers.format(helpful);
  button.setAttribute("aria-pressed", String(voted));
}

async function refreshMetrics() {
  const notice = document.querySelector(".metrics-notice");
  const revision = voteRevision;
  try {
    const response = await fetch("/api/metrics");
    if (!response.ok) throw new Error("Metrics request failed");
    const metrics = await response.json();

    for (const [slug, card] of catalogCards) {
      const stats = metrics[slug];
      if (!stats) continue;
      card.querySelector(".view-count").textContent = numbers.format(stats.views);

      if (revision !== voteRevision || pending.has(slug)) continue;
      const button = card.querySelector(".helpful-button");
      showVote(button, stats);
      button.disabled = false;
    }
    notice.textContent = "";
  } catch {
    notice.textContent = "Счётчики временно недоступны.";
  }
}

async function vote(slug, button, feedback) {
  if (pending.has(slug)) return;
  pending.add(slug);
  button.setAttribute("aria-disabled", "true");
  feedback.textContent = "";

  try {
    const method = button.getAttribute("aria-pressed") === "true" ? "DELETE" : "PUT";
    const response = await fetch(`/api/metrics/${slug}/helpful`, { method, headers: writeHeaders });
    if (!response.ok) throw new Error("Vote request failed");
    const stats = await response.json();
    voteRevision++;
    showVote(button, stats);
  } catch {
    feedback.textContent = "Не удалось сохранить отметку. Попробуйте ещё раз.";
  } finally {
    button.removeAttribute("aria-disabled");
    pending.delete(slug);
  }
}

for (const [slug, card] of catalogCards) {
  const button = card.querySelector(".helpful-button");
  const feedback = card.querySelector(".card-feedback");
  button.addEventListener("click", () => vote(slug, button, feedback));
}

if (catalogCards.size) {
  window.addEventListener("pageshow", refreshMetrics);
}

if (currentMaterial) {
  window.addEventListener("pageshow", () => {
    fetch(`/api/metrics/${currentMaterial}/view`, {
      method: "POST",
      headers: writeHeaders,
      keepalive: true,
    }).catch(() => {});
  });
}
