#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/tiny1c-oled-whitehot"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запусти установщик: sudo bash install.sh"
    exit 1
fi

echo "[1/5] Устанавливаем зависимости"
apt-get update
apt-get install -y python3 python3-numpy python3-pil python3-spidev \
    python3-gpiozero i2c-tools

echo "[2/5] Включаем SPI и I2C"
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_spi 0 || true
    raspi-config nonint do_i2c 0 || true
fi

echo "[3/5] Устанавливаем файлы"
install -d "$INSTALL_DIR/lib"
cp "$REPO_DIR/oled_display.py" "$INSTALL_DIR/"
cp "$REPO_DIR/init-camera.sh" "$INSTALL_DIR/"
cp -a "$REPO_DIR/lib/waveshare_OLED" "$INSTALL_DIR/lib/"
chmod +x "$INSTALL_DIR/init-camera.sh"

echo "[4/5] Создаём системный сервис"
cat > /etc/systemd/system/tiny1c-oled.service <<EOF
[Unit]
Description=Tiny1-C OLED White Hot Display
After=dev-i2c-1.device
Wants=dev-i2c-1.device

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStartPre=/bin/bash $INSTALL_DIR/init-camera.sh
ExecStart=/usr/bin/python3 $INSTALL_DIR/oled_display.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "[5/5] Включаем автозапуск"
systemctl daemon-reload
systemctl enable --now tiny1c-oled.service

echo
echo "Установка завершена!"
echo "Проверка: systemctl status tiny1c-oled.service"
