#!/usr/bin/env bash
# Тихий запуск Windows-эталонов через wine на macOS/Linux: глушит баннеры
# wine/MoltenVK. Сравнивается только stdout, поэтому stderr можно отбросить.
# На Windows-стенде .exe запускается нативно и эта обёртка не используется.
export WINEDEBUG=-all
export MVK_CONFIG_LOG_LEVEL=0
export WINEDLLOVERRIDES="winevulkan=d;winemenubuilder.exe=d"
exec wine "$@" 2>/dev/null
