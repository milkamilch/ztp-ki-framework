# GitHub Profile README — Design Spec

**Datum:** 2026-05-11  
**GitHub-User:** milkamilch

---

## Ziel

Ein GitHub-Profil-README im Terminal/Hacker-Stil mit grüner Akzentfarbe, das Lars als Backend-Developer und Bacheloranden vorstellt. Kein CI-Overhead — rein statisches Markdown mit externen Badge- und Stats-Diensten.

---

## Struktur (von oben nach unten)

### 1. Header — Typing Animation

- SVG-Typing-Animation via [readme-typing-svg](https://readme-typing-svg.demolab.com/)
- Text rotiert zwischen: `"Hi, I'm Lars 👾"`, `"Developer · Student · Builder"`, `"ZTP · Backend · KI"`
- Zentriert, Schriftgröße groß, Farbe `#39ff14` (Matrix Green)

### 2. whoami-Block

Terminal-Style mit grüner Prompt-Zeile und Border-Left:

```
$ whoami
🎓 Wirtschaftsinformatik @ Hochschule · Bachelorarbeit 2026
🔧 Backend-lastig · Java + Spring Boot · Python
🌍 Hamburg, Germany
```

### 3. Currently Building

Hervorgehobene Box mit aktuellem Hauptprojekt:

```
$ cat current_project.txt
📡 ZTP-KI-Framework
Zero-Touch-Provisioning mit KI-Self-Healing für Bare-Metal-Server
Python · Isolation Forest · Redfish · Ansible · Docker
```

Nach Abschluss der Bachelorarbeit auf PersonalOs (AI Study Assistant) aktualisieren.

### 4. Tech Stack Badges

Shields.io-Badges (Stil: `flat-square`, Farbe: `#21262d` + `#39ff14` Logo-Farbe) für:

- Java 25
- Spring Boot
- Python
- React 19
- TypeScript
- Docker
- Ansible
- PostgreSQL

### 5. GitHub Stats Cards

Zwei nebeneinanderliegende Karten via [github-readme-stats](https://github.com/anuraghazra/github-readme-stats):

- **Stats-Card:** `?username=milkamilch&theme=chartreuse-dark&hide_border=true`
- **Top-Languages-Card:** `?username=milkamilch&theme=chartreuse-dark&hide_border=true&layout=compact`

---

## Technische Entscheidungen

| Entscheidung | Wahl | Begründung |
|---|---|---|
| Animierter Header | readme-typing-svg | Kein CI, funktioniert als img-Tag in Markdown |
| Stats | github-readme-stats (anuraghazra) | Etabliert, zuverlässig, viele Themes |
| Badges | Shields.io | Flexibel, kein Repo-Zugriff nötig |
| CI/Automation | Keins | YAGNI — Profil wird manuell gepflegt |

---

## Out of Scope

- Kontakt/Social-Links (bewusst weggelassen)
- GitHub Actions Automation
- Contribution Snake / Activity Graph
- Besuchercount-Badge

---

## Dateien

| Datei | Beschreibung |
|---|---|
| `README.md` | Profil-README im Repo `milkamilch/milkamilch` |
