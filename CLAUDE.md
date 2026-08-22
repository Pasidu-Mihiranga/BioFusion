# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BioFusion is a pneumonia detection clinical decision support system built for the BioFusion Hackathon 2026 (Team GMora). It uses a ResNet50 model fine-tuned on pediatric chest X-rays to classify images as NORMAL or PNEUMONIA, with Grad-CAM explainability overlays.

## Commands

### Run the Streamlit app locally
```bash
cd streamlit_app && streamlit run app.py
```

### Train the model
```bash
python train_model.py
```
Downloads the dataset via `kagglehub` (paultimothymooney/chest-xray-pneumonia). Outputs `pneumonia_resnet50_best.pth`.

### Install dependencies
```bash
pip install -r streamlit_app/requirements.txt
# For CPU-only PyTorch:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Deploy to VPS
```bash
bash deploy.sh
```
Deploys to `/var/www/biofusion-pneumonia` as a systemd service on port 8502, with nginx reverse proxy.

## Architecture

The app is a multi-page Streamlit application rooted in `streamlit_app/`.

- **`app.py`** — Landing page with metrics and feature overview. Entry point for Streamlit.
- **`pages/1_Live_Prediction.py`** — Upload chest X-ray, run inference, display Grad-CAM overlay and confidence scores.
- **`pages/2_Model_Insights.py`** — Model performance metrics (confusion matrix, ROC curve, training history).
- **`pages/3_Dataset_Explorer.py`** — Dataset statistics and exploration.
- **`utils/model.py`** — Model loading (ResNet50 with modified FC layer for binary classification) and inference.
- **`utils/gradcam.py`** — Grad-CAM implementation using hooks on `model.layer4[-1]`.
- **`utils/preprocessing.py`** — Image preprocessing with ImageNet normalization (224x224).
- **`train_model.py`** (root) — Standalone training script. Freezes ResNet50 backbone, trains only the FC layer. Uses early stopping (patience=3).

### Key design details

- `load_model(weights_path)` falls back to raw ImageNet weights ("demo mode") when `weights_path` is None or the file is missing. **Note:** the Live Prediction page calls `load_model()` with no argument, so the app currently always runs in demo mode even if `pneumonia_resnet50_best.pth` is present — wire the path through `get_model()` to use trained weights.
- The training script (`train_model.py`) freezes the entire ResNet50 backbone and trains only the new 2-class FC layer (`model.fc.parameters()`), so only ~4K params are trainable.
- Preprocessing and training both use ImageNet normalization at 224×224; grayscale X-rays are converted to RGB before inference (`preprocessing.py`).
- Grad-CAM hooks `model.layer4[-1]`; `create_gradcam_visualization` sets `requires_grad=True` and runs a backward pass, so it cannot be used inside a `torch.no_grad()` block (unlike `predict`).
- Pages import utils via `sys.path.insert` to add the parent directory. Public API is re-exported from `utils/__init__.py`.
- Each page duplicates its own CSS and top navigation bar inline (not shared via a component) and calls `st.set_page_config` itself. The model is cached with `@st.cache_resource`.
- UI palette: Sapphire Blue (`#2563eb`) primary, Emerald (`#10b981`) success, Amber (`#f59e0b`) warning. **No red** — this is an explicit design decision.
- Streamlit config lives in `streamlit_app/.streamlit/config.toml`.

### Deployment specifics

Production runs on the VPS at `159.65.1.78`, served at **https://brainstorm.pasidumihiranga.me**:

| Path | App | Port | Service |
|---|---|---|---|
| `/` | Kiosk (Flask + gunicorn) | 8503 | `biofusion-kiosk` |
| `/app` | Streamlit | 8502 | `biofusion-streamlit` |

The kiosk sits at the root because its templates hardcode absolute `/api/` and `/static/` paths; Streamlit is mounted at `/app` via `--server.baseUrlPath`, which rewrites its own URLs. Both apps share one virtualenv at `/var/www/biofusion/venv` (CPU-only PyTorch) and run as `www-data`.

On the VPS the kiosk sets `KIOSK_PUBLIC_BASE_URL` so QR codes and report links point at the public hostname instead of the LAN IP (`config.py` falls back to the LAN IP when unset, for local hardware use).

- **`deploy.sh`** (root) — idempotent deploy, runs *on the server*. Syncs `origin/main`, reinstalls deps only when a requirements file hash changed, installs the systemd units and nginx site, restarts both services, then health-checks them. Reinstalls the nginx site only when the repo's copy changed, so certbot's 443 block is not clobbered on routine deploys.
- **`deploy/`** — `biofusion-*.service` systemd units, `nginx-biofusion.conf`, and `ci-deploy-wrapper.sh`.
- **`.github/workflows/deploy.yml`** — CI (byte-compile, script/unit/nginx validation) on every push and PR; deploy on push to `main`.

CI authenticates with a dedicated SSH key pinned to a forced command (`/usr/local/bin/biofusion-deploy`) in root's `authorized_keys`, so the key can only trigger a deploy of `origin/main` — not run arbitrary commands. Repo secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_KNOWN_HOSTS`.

### Model weights

`*.pth` is gitignored, so weights are never in the repo. Both apps read them from a shared `models/` directory at the repo root (override with `BIOFUSION_MODELS_DIR`), which sits outside tracked files and survives the deploy's `git reset --hard`:

| File | Used for |
|---|---|
| `pneumonia_resnet50_best.pth` | Phone/camera photos of film — trained with phone-photo augmentation |
| `pneumonia_resnet50_combined_noPhone.pth` | Direct digital radiograph uploads |

The Live Prediction page picks between them from the existing `is_photo` flag and caches each with `@st.cache_resource` keyed by kind, so only the checkpoints actually used are resident (~100MB each on a <1GB box). The kiosk photographs film under a light box, so it always uses the phone-augmented checkpoint. Either app falls back to ImageNet **demo mode** when its checkpoint is absent.

**The mapping above is inferred from the filenames** — the checkpoints carry no embedded training metadata. If `combined_noPhone` turns out to be the phone-robust one, swap the two paths in `WEIGHTS` in `pages/1_Live_Prediction.py` and `MODEL_WEIGHTS` in `kiosk/server/config.py`.

Upload with:
```bash
scp -i ~/.ssh/<key> models/*.pth root@159.65.1.78:/var/www/biofusion/models/
```

The legacy root `nginx.conf` is the older single-app Streamlit reference config and is not what production uses.
