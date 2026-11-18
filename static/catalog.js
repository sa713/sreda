const sectionLinks = [...document.querySelectorAll(".sections-nav a")];

function updateCurrentSection() {
  const selected = sectionLinks.find((link) => link.hash === location.hash) ?? sectionLinks[0];

  for (const link of sectionLinks) {
    if (link === selected) {
      link.setAttribute("aria-current", "location");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

window.addEventListener("hashchange", updateCurrentSection);
updateCurrentSection();
