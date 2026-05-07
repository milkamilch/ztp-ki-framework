# ZTP-KI-Framework

**Zero-Touch-Provisioning-Framework mit KI-gestützter Fehlererkennung und Self-Healing für physische Serverhardware**

Bachelorarbeit · Wirtschaftsinformatik · 2026

---

## Forschungsfrage

> Wie kann ein Zero-Touch-Provisioning-Framework für physische Serverhardware konzipiert werden, das durch den Einsatz von KI-gestützter Fehlererkennung und Self-Healing-Mechanismen eine vollautomatisierte Inbetriebnahme ermöglicht – und ab welchem Skalierungsniveau ist ein solches Framework für KMU bzw. Enterprise-Rechenzentren wirtschaftlich vorteilhaft?

---

## Überblick

Dieses Repository enthält den Proof-of-Concept (PoC) zur Bachelorarbeit. Ziel ist ein **modulares, stack-unabhängiges Framework**, das physische Bare-Metal-Server ohne manuelle Eingriffe in Betrieb nimmt und Fehler im Provisionierungsprozess automatisch erkennt und behebt.

### Was dieses Framework macht

1. **PXE-Boot-Automatisierung** — Server bootet per Netzwerk, erhält IP via DHCP (dnsmasq), lädt iPXE-Image
2. **Vollautomatische OS-Installation** — Kickstart/Preseed installiert Ubuntu Server ohne Interaktion
3. **Post-Install-Konfiguration** — Ansible-Playbooks konfigurieren Pakete, Dienste, Benutzer und registrieren den Server in Netbox
4. **KI-Self-Healing-Layer** — Python-Dienst überwacht den gesamten Prozess über Redfish/IPMI in Echtzeit und greift bei Anomalien automatisch ein

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│               VERSIONIERUNG & KONFIGURATION             │
│  Git/GitHub (IaC)  │  Docker  │  Ubuntu 24.04 LTS       │
└────────────────────┬────────────────────────────────────┘
                     │ Configs · Playbooks · Python-Code
┌────────────────────▼────────────────────────────────────┐
│                  MANAGEMENT NODE                        │
│  dnsmasq     │  Netbox (CMDB)  │  Ansible  │  Prometheus │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│  KI-SELF-HEALING LAYER (Python)                         │
│  Collector → Log-Parser → Anomalie-Detektor → Decision  │
│  (Redfish)   (Drain3)     (Isolation Forest)  (Retry/   │
│                                                Reboot/  │
│                                                Rollback) │
└────────────────────┬────────────────────────────────────┘
                     │ ① DHCP+iPXE  ② Kickstart  ④ Ansible
┌────────────────────▼────────────────────────────────────┐
│                  BARE-METAL SERVER                      │
│  BMC/iDRAC/iLO  │  NIC/PXE-Boot  │  OS-Install  │ Post │
│  Redfish · IPMI │  iPXE-Bootldr  │  Kickstart   │ Config│
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| OS (Management Node) | Ubuntu Server 24.04 LTS |
| DHCP/TFTP/PXE | dnsmasq + iPXE |
| OS-Installation | Kickstart (RHEL/Ubuntu) / Preseed |
| Konfigurationsmanagement | Ansible |
| CMDB / Source of Truth | Netbox |
| Monitoring | Prometheus + Grafana |
| Containerisierung | Docker / Docker Compose |
| Hardware-API | Redfish (python-redfish) + IPMI (ipmitool) |
| Log-Parsing | Drain3-Algorithmus |
| Anomalieerkennung | Isolation Forest (scikit-learn) + regelbasiert |
| Sprache (KI-Layer) | Python 3.12 |
| Versionierung | Git / GitHub |

---

## Repository-Struktur

```
ztp-ki-framework/
├── pxe/                    # PXE-Boot-Konfiguration
│   ├── dnsmasq.conf        # DHCP + TFTP
│   └── kickstart/          # Unattended OS-Installation
├── ansible/                # Konfigurationsmanagement
│   ├── inventory/          # Hosts
│   └── playbooks/          # Post-Install + Self-Healing-Aktionen
├── ki/                     # KI-Self-Healing-Layer (Python)
│   ├── collector/          # Redfish/IPMI-Datenabfrage
│   ├── parser/             # Drain3 Log-Parsing
│   ├── detector/           # Anomalieerkennung (Isolation Forest)
│   ├── decision/           # Entscheidungslogik (Retry/Reboot/Rollback)
│   └── requirements.txt
├── netbox/                 # Netbox-Konfiguration (Docker)
├── monitoring/             # Prometheus + Grafana
│   ├── prometheus/
│   └── grafana/dashboards/
├── docker-compose.yml      # Management-Node-Dienste
└── docs/                   # Architektur-Dokumentation
```

---

## Ablauf (Happy Path)

```
Server einschalten
      │
      ▼
① PXE-Boot: dnsmasq vergibt IP, liefert iPXE-Image
      │
      ▼
② OS-Installation: Kickstart installiert Ubuntu vollautomatisch
      │
      ▼
③ KI überwacht: Redfish/IPMI → Drain3 → Isolation Forest
      │
      ├── Anomalie erkannt → Entscheidungslogik → Retry / Reboot / Rollback
      │
      ▼
④ Post-Config: Ansible konfiguriert Server, Netbox registriert ihn
```

---

## Scope (Bachelorarbeit)

| In Scope | Out of Scope |
|---|---|
| Konzept & Architekturdesign | Vollständige Produktivsystem-Implementierung |
| PoC auf eigener Serverhardware | Multi-Rack-Rollout im echten RZ |
| Regelbasiert + Isolation Forest | Deep-Learning-Modelle |
| Skalierungsvergleich KMU vs. Enterprise | Hersteller-spezifische Implementierungen |

---

## Methodik

- **Design Science Research** (Hevner et al. 2004, Peffers et al. 2007) — Leitrahmen
- **Systematische Literaturrecherche** nach vom Brocke et al. (2015)
- **Nutzwertanalyse** — wirtschaftlicher Skalierungsvergleich KMU vs. Enterprise

---

## Status

> **Work in Progress** — Bachelorarbeit in Bearbeitung (2026)
