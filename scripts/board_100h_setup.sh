#!/bin/sh
set -eu

PCI_DEV="${PCI_DEV:-0002:21:00.0}"
RESOURCE_ROOT="/sys/bus/pci/devices/${PCI_DEV}"

if [ "$(id -u)" -ne 0 ]; then
    echo "请用 sudo 运行：sudo sh scripts/board_100h_setup.sh" >&2
    exit 1
fi

if [ -e "${RESOURCE_ROOT}/remove" ]; then
    echo 1 > "${RESOURCE_ROOT}/remove"
fi
sleep 0.2
echo 1 > /sys/bus/pci/rescan
sleep 0.3

if [ ! -d "${RESOURCE_ROOT}" ]; then
    echo "PCIe Endpoint 未重新枚举：${PCI_DEV}" >&2
    exit 2
fi

if [ -e "${RESOURCE_ROOT}/enable" ]; then
    echo 1 > "${RESOURCE_ROOT}/enable"
fi
setpci -s "${PCI_DEV}" COMMAND=0006

echo "[lspci]"
lspci -s "${PCI_DEV}" -vv | sed -n '1,30p'

echo "[BAR0 resource0]"
ls -l "${RESOURCE_ROOT}/resource0"

echo "[signature @ 0xf0200000]"
if command -v busybox >/dev/null 2>&1; then
    busybox devmem 0xf0200000 32 || true
else
    echo "busybox 不存在，跳过 devmem；后续可用 python3 scripts/fpga_ctl.py 检查签名"
fi

echo "PCIe 重枚举完成。PCB bitstream 正常时签名应为 0x50434250。"
