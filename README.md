# Whisper HUD

Herramienta de voz a texto para escritorios Hyprland/Wayland. Presiona `SUPER+R` para empezar a grabar y vuelve a presionarlo para transcribir: el texto resultante se escribe directamente en la ventana activa y se copia al portapapeles.

## Cómo funciona

```
SUPER+R (primera pulsación)
  └─► transcribe.sh
        ├─ inicia pw-record  →  graba audio en /tmp/whisper-recording.wav
        └─ lanza indicator.py  →  HUD flotante con barras animadas (cyan)

SUPER+R (segunda pulsación)
  └─► transcribe.sh
        ├─ detiene pw-record
        ├─ ejecuta whisper-cli  →  HUD en amarillo mientras procesa
        ├─ copia el resultado con wl-copy
        └─ escribe el texto con wtype
```

Presionar **ESC** mientras el HUD está visible cancela la grabación sin transcribir.

## Requisitos

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (compilado en `whisper.cpp/build/bin/whisper-cli`)
- PipeWire (`pw-record`)
- `wl-copy` (paquete `wl-clipboard`)
- `wtype`
- Python 3 con los paquetes: `PyGObject` (GTK4), `sounddevice`, `numpy`, `pycairo`

## Instalación

### 1. Compilar whisper.cpp

```bash
cd ~/.whisper/whisper.cpp
cmake -B build -DGGML_VULKAN=1
cmake --build build --config Release -j$(nproc)
```

### 2. Descargar un modelo

```bash
cd ~/.whisper/whisper.cpp
bash models/download-ggml-model.sh large-v3-turbo
```

| Modelo | Tamaño | Velocidad | Precisión |
|--------|--------|-----------|-----------|
| `tiny` | 75 MB | Muy rápida | Básica |
| `base` | 142 MB | Rápida | Buena |
| `small` | 466 MB | Media | Buena |
| `medium` | 1.5 GB | Lenta | Muy buena |
| `large-v3-turbo` | 1.6 GB | Media | Excelente |
| `large-v3` | 3.1 GB | Lenta | Excelente |

### 3. Instalar dependencias de Python

```bash
# Arch Linux
sudo pacman -S python-gobject python-sounddevice python-numpy python-cairo

# pip
pip install PyGObject sounddevice numpy pycairo
```

### 4. Configurar el keybinding en Hyprland

Añade a `~/.config/hypr/bindings.lua`:

```lua
hl.bind("SUPER + R", hl.dsp.exec_cmd("bash " .. os.getenv("HOME") .. "/.whisper/transcribe.sh"), { description = "Whisper: grabar/transcribir voz" })
```

Aplica los cambios con `hyprctl reload`.

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `transcribe.sh` | Script principal: alterna entre iniciar grabación y transcribir |
| `indicator.py` | HUD flotante GTK4 con ecualizador animado |
| `cancel.sh` | Cancela la grabación activa y limpia archivos temporales |

## Personalización

### Cambiar el modelo

Edita la variable `MODEL` en `transcribe.sh`:

```bash
MODEL="$HOME/.whisper/whisper.cpp/models/ggml-large-v3.bin"
```

### Cambiar el aspecto del HUD

Edita las constantes al inicio de `indicator.py`:

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `BG_COLOR` | `#0a1220` | Color de fondo |
| `ACCENT_RECORDING` | `#78dce8` | Color de barras al grabar |
| `ACCENT_TRANSCRIBING` | `#f2c063` | Color de barras al transcribir |
| `NUM_BARS` | `16` | Número de barras del ecualizador |
| `MAX_BAR_HEIGHT` | `28` | Altura máxima de las barras (px) |
| `WINDOW_WIDTH` | `220` | Ancho de la ventana (px) |
| `WINDOW_HEIGHT` | `44` | Alto de la ventana (px) |

Si cambias `WINDOW_WIDTH` o `WINDOW_HEIGHT`, actualiza también el `size` correspondiente en `~/.config/hypr/hyprland.lua`.

### Posición de la ventana

Edita `~/.config/hypr/hyprland.lua`:

```lua
o.window("whisper-indicator", {
  size = { 220, 44 },
  move = { "(monitor_w/2-window_w/2)", "(monitor_h-window_h-50)" },
})
```

Aplica con `hyprctl reload`.

## Solución de problemas

**El HUD no aparece**
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print('OK')"
```

**Las barras no se mueven**
```bash
python3 -c "import sounddevice; print('OK')"
# Si falla: sudo pacman -S python-sounddevice
```

**whisper-cli no transcribe nada**
```bash
~/.whisper/whisper.cpp/build/bin/whisper-cli --help
ls -lh ~/.whisper/whisper.cpp/models/
```

**Limpiar procesos colgados**
```bash
kill $(cat /tmp/whisper-recording.pid 2>/dev/null) 2>/dev/null
kill $(cat /tmp/whisper-indicator.pid 2>/dev/null) 2>/dev/null
rm -f /tmp/whisper-recording.{pid,wav} /tmp/whisper-state /tmp/whisper-indicator.pid
```
