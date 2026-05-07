#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# ZTP-Framework — Management Node Setup
# Installiert und konfiguriert dnsmasq (DHCP + TFTP) sowie
# einen Nginx-Webserver für iPXE-Scripts und Autoinstall-Configs.
#
# Voraussetzung: Ubuntu 24.04 LTS, sudo-Rechte
# Ausführen:     sudo bash pxe/setup.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

MGMT_IP="192.168.100.1"
MGMT_IFACE="eth1"
TFTP_ROOT="/srv/tftp"
WWW_ROOT="/srv/www/pxe"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> ZTP Management Node Setup"
echo "    IP:        ${MGMT_IP}"
echo "    Interface: ${MGMT_IFACE}"
echo "    Repo:      ${REPO_DIR}"
echo

# ──────────────────────────────────────────
# 1. Pakete installieren
# ──────────────────────────────────────────
echo "==> [1/5] Pakete installieren ..."
apt-get update -q
apt-get install -y dnsmasq nginx curl wget

# ──────────────────────────────────────────
# 2. dnsmasq konfigurieren
# ──────────────────────────────────────────
echo "==> [2/5] dnsmasq konfigurieren ..."

# System-dnsmasq deaktivieren falls er für DNS läuft (z.B. systemd-resolved-Konflikt)
systemctl stop systemd-resolved 2>/dev/null || true
systemctl disable systemd-resolved 2>/dev/null || true

cp "${REPO_DIR}/pxe/dnsmasq.conf" /etc/dnsmasq.conf

# Interface und IP im Konfig ersetzen (falls abweichend)
sed -i "s/^interface=.*/interface=${MGMT_IFACE}/" /etc/dnsmasq.conf

# ──────────────────────────────────────────
# 3. TFTP-Root aufsetzen + iPXE-Binaries laden
# ──────────────────────────────────────────
echo "==> [3/5] TFTP-Root aufsetzen und iPXE-Binaries laden ..."
mkdir -p "${TFTP_ROOT}"

IPXE_BASE="https://boot.ipxe.org"
for binary in undionly.kpxe ipxe.efi; do
  if [[ ! -f "${TFTP_ROOT}/${binary}" ]]; then
    echo "    Lade ${binary} ..."
    curl -sSfL "${IPXE_BASE}/${binary}" -o "${TFTP_ROOT}/${binary}"
  else
    echo "    ${binary} bereits vorhanden, überspringe."
  fi
done

# ──────────────────────────────────────────
# 4. Nginx — iPXE-Scripts + Autoinstall-Configs servieren
# ──────────────────────────────────────────
echo "==> [4/5] Nginx konfigurieren ..."
mkdir -p "${WWW_ROOT}/ipxe"
mkdir -p "${WWW_ROOT}/autoinstall"
mkdir -p "${WWW_ROOT}/ansible"

# boot.ipxe servieren
cp "${REPO_DIR}/pxe/ipxe/boot.ipxe" "${WWW_ROOT}/boot.ipxe"
sed -i "s|http://192.168.100.1|http://${MGMT_IP}|g" "${WWW_ROOT}/boot.ipxe"

# Autoinstall-Template für neue Server bereitstellen
cp "${REPO_DIR}/pxe/kickstart/ubuntu-autoinstall.yaml" "${WWW_ROOT}/autoinstall/user-data.template"

# Nginx-Vhost
cat > /etc/nginx/sites-available/pxe <<NGINX
server {
    listen 80;
    server_name ${MGMT_IP};
    root ${WWW_ROOT};

    location /pxe/ {
        alias ${WWW_ROOT}/;
        autoindex on;
    }

    # Autoinstall-Configs: /pxe/autoinstall/<mac>/user-data
    location /pxe/autoinstall/ {
        alias ${WWW_ROOT}/autoinstall/;
        autoindex on;
    }

    # Ansible-Trigger-Script
    location /ansible/ {
        alias ${WWW_ROOT}/ansible/;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/pxe /etc/nginx/sites-enabled/pxe
rm -f /etc/nginx/sites-enabled/default

# Ansible-Trigger-Script (ruft Playbook auf dem Management Node auf)
cat > "${WWW_ROOT}/ansible/trigger.sh" <<'TRIGGER'
#!/bin/bash
# Wird auf dem neu installierten Server ausgeführt.
# Meldet dem Management Node, dass der Server bereit ist.
SERVER_IP=$(ip -4 -o addr show | awk 'NR==1{print $4}' | cut -d/ -f1)
curl -sf "http://192.168.100.1/ansible/ready?ip=${SERVER_IP}" || true
TRIGGER
chmod +x "${WWW_ROOT}/ansible/trigger.sh"

# ──────────────────────────────────────────
# 5. Dienste starten
# ──────────────────────────────────────────
echo "==> [5/5] Dienste starten ..."
nginx -t && systemctl restart nginx
systemctl enable dnsmasq && systemctl restart dnsmasq

echo
echo "✓ Setup abgeschlossen."
echo
echo "  TFTP-Root:   ${TFTP_ROOT}"
echo "  Web-Root:    ${WWW_ROOT}"
echo "  dnsmasq-Log: /var/log/dnsmasq.log"
echo
echo "  Nächster Schritt:"
echo "  Ubuntu-ISO nach ${WWW_ROOT}/ubuntu/ entpacken:"
echo "    mkdir -p ${WWW_ROOT}/ubuntu"
echo "    mount ubuntu-24.04-live-server-amd64.iso /mnt"
echo "    cp -r /mnt/. ${WWW_ROOT}/ubuntu/noble/"
echo
echo "  Server-spezifische Autoinstall-Config anlegen:"
echo "    mkdir -p ${WWW_ROOT}/autoinstall/<MAC-ADRESSE>"
echo "    cp ${WWW_ROOT}/autoinstall/user-data.template \\"
echo "       ${WWW_ROOT}/autoinstall/<MAC-ADRESSE>/user-data"
echo "    echo '' > ${WWW_ROOT}/autoinstall/<MAC-ADRESSE>/meta-data"
