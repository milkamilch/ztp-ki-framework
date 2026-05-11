# GitHub Profile README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a terminal/hacker-style GitHub profile README for `milkamilch` with SVG typing animation, whoami block, currently-building section, tech stack badges, and GitHub stats cards.

**Architecture:** Single `README.md` in the special `milkamilch/milkamilch` repo. All dynamic content (animation, stats, badges) is served via external `<img>` tags — no CI, no JavaScript, no automation required. The file is pure GitHub Markdown.

**Tech Stack:** GitHub Markdown, [readme-typing-svg](https://readme-typing-svg.demolab.com), [github-readme-stats](https://github.com/anuraghazra/github-readme-stats), [Shields.io](https://shields.io)

---

## File Structure

```
milkamilch/milkamilch/
└── README.md      ← the entire profile, created from scratch
```

---

### Task 1: Create the profile repo

**Files:**
- Create: `README.md` (in repo `milkamilch/milkamilch` on GitHub)

- [ ] **Step 1: Create the special profile repo on GitHub**

  Go to https://github.com/new and create a repo with the name **`milkamilch`** (exactly your username).
  Check "Add a README file" to initialize it. This activates the GitHub profile README feature.

- [ ] **Step 2: Clone the repo locally**

  ```bash
  git clone https://github.com/milkamilch/milkamilch.git
  cd milkamilch
  ```

- [ ] **Step 3: Clear the default README content**

  Replace the auto-generated content with an empty file:

  ```bash
  echo "" > README.md
  ```

---

### Task 2: Add the typing animation header

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Verify the typing SVG URL returns a valid SVG**

  ```bash
  curl -s "https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=39FF14&center=true&vCenter=true&width=500&lines=Hi%2C+I'm+Lars+%F0%9F%91%BE;Developer+%C2%B7+Student+%C2%B7+Builder;ZTP+%C2%B7+Backend+%C2%B7+KI" | head -1
  ```

  Expected: output starts with `<svg` or `<?xml`

- [ ] **Step 2: Write the header section into README.md**

  ```markdown
  <div align="center">

  [![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=39FF14&center=true&vCenter=true&width=500&lines=Hi%2C+I'm+Lars+%F0%9F%91%BE;Developer+%C2%B7+Student+%C2%B7+Builder;ZTP+%C2%B7+Backend+%C2%B7+KI)](https://github.com/milkamilch)

  </div>
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "feat: add typing animation header"
  ```

---

### Task 3: Add the whoami block

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append the whoami section**

  Add this block directly after the header:

  ````markdown
  <br>

  ```bash
  $ whoami
  ```

  > 🎓 Wirtschaftsinformatik · Bachelorarbeit 2026  
  > 🔧 Backend-lastig — Java + Spring Boot · Python  
  > 🌍 Hamburg, Germany
  ````

  The `> ` lines render as a blockquote in GitHub — clean, indented, readable.

- [ ] **Step 2: Commit**

  ```bash
  git add README.md
  git commit -m "feat: add whoami block"
  ```

---

### Task 4: Add the currently-building section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append the currently-building section**

  ````markdown
  <br>

  ```bash
  $ cat current_project.txt
  ```

  **📡 [ZTP-KI-Framework](https://github.com/milkamilch/ZTP-KI-framework)**  
  Zero-Touch-Provisioning mit KI-Self-Healing für Bare-Metal-Server  
  `Python` · `Isolation Forest` · `Redfish` · `Ansible` · `Docker`
  ````

- [ ] **Step 2: Commit**

  ```bash
  git add README.md
  git commit -m "feat: add currently-building section"
  ```

---

### Task 5: Add tech stack badges

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Verify a badge URL returns an SVG**

  ```bash
  curl -s -o /dev/null -w "%{http_code}" \
    "https://img.shields.io/badge/Java_25-21262d?style=flat-square&logo=openjdk&logoColor=39ff14"
  ```

  Expected: `200`

- [ ] **Step 2: Append the tech stack section**

  ```markdown
  <br>

  ```bash
  $ ls tech_stack/
  ```

  ![Java](https://img.shields.io/badge/Java_25-21262d?style=flat-square&logo=openjdk&logoColor=39ff14)
  ![Spring Boot](https://img.shields.io/badge/Spring_Boot-21262d?style=flat-square&logo=springboot&logoColor=39ff14)
  ![Python](https://img.shields.io/badge/Python-21262d?style=flat-square&logo=python&logoColor=39ff14)
  ![React](https://img.shields.io/badge/React_19-21262d?style=flat-square&logo=react&logoColor=39ff14)
  ![TypeScript](https://img.shields.io/badge/TypeScript-21262d?style=flat-square&logo=typescript&logoColor=39ff14)
  ![Docker](https://img.shields.io/badge/Docker-21262d?style=flat-square&logo=docker&logoColor=39ff14)
  ![Ansible](https://img.shields.io/badge/Ansible-21262d?style=flat-square&logo=ansible&logoColor=39ff14)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-21262d?style=flat-square&logo=postgresql&logoColor=39ff14)
  ```

  Note: the triple-backtick block for `$ ls tech_stack/` is a separate fenced block above the badges — don't nest the badge lines inside it.

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "feat: add tech stack badges"
  ```

---

### Task 6: Add GitHub stats cards

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Verify stats URL returns content**

  ```bash
  curl -s -o /dev/null -w "%{http_code}" \
    "https://github-readme-stats.vercel.app/api?username=milkamilch&theme=chartreuse-dark&hide_border=true"
  ```

  Expected: `200` (returns an SVG card — may show zeros until you have public activity)

- [ ] **Step 2: Append the stats section**

  ```markdown
  <br>

  ```bash
  $ github-stats --user milkamilch
  ```

  <div align="center">

  ![GitHub Stats](https://github-readme-stats.vercel.app/api?username=milkamilch&theme=chartreuse-dark&hide_border=true&show_icons=true&icon_color=39ff14)
  ![Top Languages](https://github-readme-stats.vercel.app/api/top-langs/?username=milkamilch&theme=chartreuse-dark&hide_border=true&layout=compact)

  </div>
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "feat: add GitHub stats cards"
  ```

---

### Task 7: Final check and push

**Files:**
- Modify: `README.md` (cleanup only if needed)

- [ ] **Step 1: Review the complete README.md locally**

  ```bash
  cat README.md
  ```

  Confirm all sections are present in order: header → whoami → currently building → tech stack → stats.

- [ ] **Step 2: Push to GitHub**

  ```bash
  git push origin main
  ```

- [ ] **Step 3: Open your GitHub profile in the browser**

  Go to https://github.com/milkamilch and verify:
  - Typing animation plays in the header (allow a few seconds to load)
  - whoami blockquote renders correctly
  - Tech stack badges display with dark background + green icons
  - Stats cards load (may show placeholder until GitHub caches them — refresh after ~60s)

- [ ] **Step 4: Done**

  If any badge or card shows a broken image, re-check the URL in the relevant task step. Common issues:
  - Logo slug typo → check https://simpleicons.org for exact logo names
  - Stats card "not found" → repo must be public and username must match exactly `milkamilch`
